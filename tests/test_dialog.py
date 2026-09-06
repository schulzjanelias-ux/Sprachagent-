"""EPIC 05 · Vollstaendigkeitspruefung und Rueckfragedialog (D-12).

Deckt aus der Testmatrix (Briefing §21) ab: C (fehlende Menge), D (fehlende
Einheit), E (fehlendes Bauvorhaben bzw. Gewerk), F (unsichere Erkennung),
G (Korrektur) und K (fehlerhafte API-Antwort im zweiten Zug).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from app.dienste.dialog import RUNDEN_MAX, Dialogstand, fortsetzen, starten
from app.dienste.einheiten import codes
from app.dienste.strukturierung.basis import (
    Entwurf, EntwurfLeistung, Kontext, RohArbeitszeit, RohLeistung, Rohentwurf,
    StrukturierungsFehler,
)
from app.dienste.vollstaendigkeit import (
    Lueckenart, luecken_finden, rueckfrage_formulieren,
)

GEWERKE = ("Bauleitung", "Rückbau", "Maurer", "Trockenbau", "Elektro",
           "Sanitär/Heizung", "Fliesen", "Maler", "Bodenleger", "Tischler",
           "Reinigung", "Sonstiges")


@pytest.fixture
def kontext():
    return Kontext(heute=date(2026, 9, 10), gewerke=GEWERKE, einheiten=codes(),
                   bauvorhaben="Musterstraße 12", regelbeginn=time(7, 0))


class Drehbuch:
    """Strukturierer mit fest hinterlegten Antworten.

    Bildet ab, was das echte Modell liefern wuerde, ohne einen API-Aufruf -
    so ist der Dialog vollstaendig pruefbar.
    """

    name = "drehbuch"

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.nummer = 0

    def strukturiere(self, transkript, kontext):
        antwort = self.antworten[min(self.nummer, len(self.antworten) - 1)]
        self.nummer += 1
        if isinstance(antwort, Exception):
            raise antwort
        return antwort


def leistung(taetigkeit, menge=None, einheit=None, konfidenz=0.9, beschreibung=None):
    return RohLeistung(taetigkeit=taetigkeit, beschreibung=beschreibung,
                       menge_wortlaut=menge, einheit_wortlaut=einheit,
                       konfidenz=konfidenz)


def roh(leistungen=(), gewerk="Trockenbau", datum=None, beginn="7 Uhr",
        ende="16:30", dauer=None, bemerkung=None, unklarheiten=()):
    return Rohentwurf(
        datum_wortlaut=datum, gewerk=gewerk, leistungen=list(leistungen),
        arbeitszeit=RohArbeitszeit(beginn_wortlaut=beginn, ende_wortlaut=ende,
                                   dauer_wortlaut=dauer),
        bemerkung=bemerkung, unklarheiten=list(unklarheiten))


def entwurf(leistungen=(), gewerk="Trockenbau", beginn=time(7, 0),
            ende=time(16, 30), **weitere):
    return Entwurf(datum=date(2026, 9, 10), transkript="…", gewerk=gewerk,
                   leistungen=list(leistungen), beginn=beginn, ende=ende, **weitere)


# --- Das Szenario aus dem Briefing ----------------------------------------

def test_szenario_aus_briefing_paragraf_drei(kontext):
    """Zwei Taetigkeiten ohne Mengen -> EINE Frage -> vollstaendiger Bericht."""
    drehbuch = Drehbuch(
        roh([leistung("Spachtelarbeiten", beschreibung="Wände im Wohnzimmer"),
             leistung("Schleifarbeiten")]),
        roh([leistung("gespachtelt", "ungefähr 65", "Quadratmeter"),
             leistung("geschliffen", "40", "Quadratmeter")],
            gewerk=None, beginn=None, ende=None),
    )

    stand = starten("Heute gespachtelt und geschliffen, von 7 bis halb fünf.",
                    kontext, drehbuch)
    assert len(stand.luecken) == 2
    assert all(l.art == Lueckenart.menge for l in stand.luecken)
    assert stand.rueckfrage == (
        "Wie viel habt ihr bei Spachtelarbeiten und Schleifarbeiten geschafft?")

    stand = fortsetzen(stand, "Ungefähr 65 Quadratmeter gespachtelt und "
                              "40 Quadratmeter geschliffen.", kontext, drehbuch)
    assert stand.vollstaendig
    assert [(p.taetigkeit, p.menge, p.einheit) for p in stand.entwurf.leistungen] == [
        ("Spachtelarbeiten", Decimal("65"), "m²"),
        ("Schleifarbeiten", Decimal("40"), "m²")]
    assert stand.entwurf.leistungen[0].geschaetzt is True


def test_eine_frage_statt_vier(kontext):
    """D-12: Fehlen Menge und Einheit zu zwei Positionen, entsteht EINE Frage."""
    ergebnis = luecken_finden(
        entwurf([EntwurfLeistung("Spachtelarbeiten"), EntwurfLeistung("Schleifarbeiten")]),
        kontext)
    frage = rueckfrage_formulieren(ergebnis, entwurf(
        [EntwurfLeistung("Spachtelarbeiten"), EntwurfLeistung("Schleifarbeiten")]), kontext)
    assert frage.count("?") == 1


# --- Lueckenerkennung ------------------------------------------------------

def test_vollstaendiger_bericht_erzeugt_keine_frage(kontext):
    ergebnis = luecken_finden(entwurf(
        [EntwurfLeistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²")]),
        kontext)
    assert ergebnis.vollstaendig
    assert rueckfrage_formulieren(ergebnis, entwurf(), kontext) is None


def test_fehlendes_gewerk_wird_erkannt(kontext):
    ergebnis = luecken_finden(entwurf(
        [EntwurfLeistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²")],
        gewerk=None), kontext)
    assert [l.art for l in ergebnis.luecken] == [Lueckenart.gewerk]


def test_fehlende_zeit_wird_erkannt(kontext):
    """D-03: Ohne Anfang und Ende entsteht in der Mappe keine Stundenzahl."""
    ergebnis = luecken_finden(entwurf(
        [EntwurfLeistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²")],
        beginn=None, ende=None), kontext)
    assert [l.art for l in ergebnis.luecken] == [Lueckenart.zeit]


def test_einheit_wird_nur_mit_menge_nachgefragt(kontext):
    """Eine Einheit ohne Menge ist wertlos - dann fehlt die Menge, nicht die
    Einheit."""
    ohne_beides = luecken_finden(entwurf([EntwurfLeistung("Spachtelarbeiten")]), kontext)
    assert [l.art for l in ohne_beides.luecken] == [Lueckenart.menge]

    nur_einheit = luecken_finden(entwurf(
        [EntwurfLeistung("Türen grundieren", menge=Decimal("8"))]), kontext)
    assert [l.art for l in nur_einheit.luecken] == [Lueckenart.einheit]


def test_einheitenfrage_nennt_die_menge_mit(kontext):
    """Die Frage muss ohne Rueckblick verstaendlich sein."""
    stand_entwurf = entwurf([EntwurfLeistung("Türen grundieren", menge=Decimal("8"))])
    frage = rueckfrage_formulieren(luecken_finden(stand_entwurf, kontext),
                                   stand_entwurf, kontext)
    assert "8 was bei Türen grundieren" in frage


def test_ganze_zahlen_behalten_ihre_null(kontext):
    """Ein rstrip("0") hatte hier aus 40 eine 4 gemacht."""
    stand_entwurf = entwurf([EntwurfLeistung("Schleifen", menge=Decimal("40"))])
    frage = rueckfrage_formulieren(luecken_finden(stand_entwurf, kontext),
                                   stand_entwurf, kontext)
    assert "40 was bei" in frage


# --- Hinweise blockieren nicht (Briefing §8) ------------------------------

def test_hinweise_blockieren_die_bestaetigung_nicht(kontext):
    ergebnis = luecken_finden(entwurf(
        [EntwurfLeistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²",
                         geschaetzt=True, konfidenz=0.3)],
        datum_abgeleitet=True, zeit_abgeleitet=True), kontext)
    assert ergebnis.vollstaendig
    assert any("geschätzt" in h for h in ergebnis.hinweise)
    assert any("unsicher" in h for h in ergebnis.hinweise)
    assert any("errechnet" in h for h in ergebnis.hinweise)


# --- Einarbeiten der Antwort ----------------------------------------------

def test_zuordnung_ueber_den_namen(kontext):
    """gespachtelt trifft Spachtelarbeiten, auch in umgekehrter Reihenfolge."""
    drehbuch = Drehbuch(
        roh([leistung("Spachtelarbeiten"), leistung("Türen grundieren")]),
        roh([leistung("Türen grundiert", "8", "Stück"),
             leistung("gespachtelt", "65", "Quadratmeter")],
            gewerk=None, beginn=None, ende=None),
    )
    stand = fortsetzen(starten("…", kontext, drehbuch), "…", kontext, drehbuch)
    mengen = {p.taetigkeit: p.menge for p in stand.entwurf.leistungen}
    assert mengen == {"Spachtelarbeiten": Decimal("65"),
                      "Türen grundieren": Decimal("8")}


def test_zuordnung_der_reihe_nach_wenn_die_anzahl_aufgeht(kontext):
    drehbuch = Drehbuch(
        roh([leistung("Erste Arbeit"), leistung("Zweite Arbeit")]),
        roh([leistung("das eine", "10", "m²"), leistung("das andere", "20", "m²")],
            gewerk=None, beginn=None, ende=None),
    )
    stand = fortsetzen(starten("…", kontext, drehbuch), "…", kontext, drehbuch)
    assert [p.menge for p in stand.entwurf.leistungen] == [Decimal("10"), Decimal("20")]


def test_bei_mehrdeutigkeit_wird_nichts_geraten(kontext):
    """Briefing §8: niemals halluzinieren. Zwei offene Positionen, aber nur
    eine Menge in der Antwort - das bleibt offen."""
    drehbuch = Drehbuch(
        roh([leistung("Erste Arbeit"), leistung("Zweite Arbeit")]),
        roh([leistung("irgendwas", "10", "m²")], gewerk=None, beginn=None, ende=None),
    )
    stand = fortsetzen(starten("…", kontext, drehbuch), "…", kontext, drehbuch)
    assert [p.menge for p in stand.entwurf.leistungen] == [None, None]
    assert not stand.vollstaendig


def test_bestaetigte_angaben_werden_nicht_ueberschrieben(kontext):
    """Eine unglueckliche zweite Aufnahme darf die erste nicht entwerten."""
    drehbuch = Drehbuch(
        roh([leistung("Spachtelarbeiten", "65", "Quadratmeter"),
             leistung("Schleifarbeiten")]),
        roh([leistung("gespachtelt", "999", "Stück"),
             leistung("geschliffen", "40", "Quadratmeter")],
            gewerk="Maler", beginn="5 Uhr", ende="6 Uhr"),
    )
    stand = starten("…", kontext, drehbuch)
    stand = fortsetzen(stand, "…", kontext, drehbuch)

    erste = stand.entwurf.leistungen[0]
    assert erste.menge == Decimal("65") and erste.einheit == "m²"
    assert stand.entwurf.gewerk == "Trockenbau"
    assert stand.entwurf.beginn == time(7, 0)


# --- Rundenbegrenzung ------------------------------------------------------

def test_nach_zwei_runden_endet_der_dialog(kontext):
    """D-12: Der Mitarbeiter wird nicht in einer Schleife festgehalten."""
    hartnaeckig = Drehbuch(roh([leistung("Unklare Arbeit")], beginn=None, ende=None))

    stand = starten("…", kontext, hartnaeckig)
    assert stand.weitere_runde_moeglich and stand.rueckfrage

    for _ in range(RUNDEN_MAX):
        stand = fortsetzen(stand, "…", kontext, hartnaeckig)

    assert stand.runde == RUNDEN_MAX
    assert not stand.weitere_runde_moeglich
    assert stand.manuell_ergaenzen
    assert stand.rueckfrage is None, "keine weitere Frage nach der letzten Runde"
    assert stand.luecken, "die offenen Stellen bleiben markiert"


def test_fortsetzen_nach_dem_ende_aendert_nichts(kontext):
    hartnaeckig = Drehbuch(roh([leistung("Unklar")], beginn=None, ende=None))
    stand = starten("…", kontext, hartnaeckig)
    for _ in range(RUNDEN_MAX):
        stand = fortsetzen(stand, "…", kontext, hartnaeckig)
    unveraendert = fortsetzen(stand, "noch was", kontext, hartnaeckig)
    assert unveraendert.runde == stand.runde


# --- K · Fehler im zweiten Zug --------------------------------------------

def test_misslungene_antwort_entwertet_den_entwurf_nicht(kontext):
    """Briefing §28: Der bisherige Stand darf nicht verlorengehen."""
    drehbuch = Drehbuch(
        roh([leistung("Spachtelarbeiten", "65", "Quadratmeter"),
             leistung("Schleifarbeiten")]),
        StrukturierungsFehler("Anbieter nicht erreichbar"),
    )
    stand = starten("…", kontext, drehbuch)
    nachher = fortsetzen(stand, "unverständlich", kontext, drehbuch)

    assert nachher.entwurf.leistungen[0].menge == Decimal("65")
    assert any("von Hand" in h for h in nachher.hinweise)
    assert nachher.runde == 1


# --- Zusammenfassung (Briefing §12) ---------------------------------------

def test_zusammenfassung_im_briefing_format(kontext):
    stand = Dialogstand(entwurf=entwurf([
        EntwurfLeistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²"),
        EntwurfLeistung("Schleifarbeiten", menge=Decimal("40"), einheit="m²")]))
    text = stand.zusammenfassung()
    assert "10.09.2026" in text
    assert "Trockenbau" in text
    assert "07:00 bis 16:30" in text
    assert "Spachtelarbeiten  65 m²" in text
    assert "Schleifarbeiten  40 m²" in text


def test_zusammenfassung_zeigt_fehlende_einheit_als_fragezeichen(kontext):
    stand = Dialogstand(entwurf=entwurf(
        [EntwurfLeistung("Türen grundieren", menge=Decimal("8"))]))
    assert "8 ?" in stand.zusammenfassung()
