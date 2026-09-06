"""EPIC 03/04 · Transkription und Strukturierung.

Deckt aus der Testmatrix (Briefing §21) ab: A (korrekte Eingabe),
B (mehrere Leistungen), C (fehlende Menge), D (fehlende Einheit),
F (unsichere Erkennung), K (fehlerhafte API-Antwort), L (Netzwerkfehler).

Der Claude-Adapter wird mit einem eingespeisten Klienten geprueft. Der echte
Aufruf ist damit **nicht** abgedeckt - dafuer braucht es einen Schluessel und
den Realitaetstest mit echten Aufnahmen.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.dienste.einheiten import codes
from app.dienste.strukturierung import Kontext, StrukturierungsFehler, entwurf_erzeugen
from app.dienste.strukturierung.attrappe import AttrappenStrukturierer
from app.dienste.strukturierung.basis import (
    RohArbeitszeit, RohLeistung, Rohentwurf,
)
from app.dienste.strukturierung.normalisierung import normalisieren
from app.dienste.transkription import transkribierer_erzeugen, vokabular_zusammenstellen
from app.dienste.transkription.attrappe import AttrappenTranskribierer
from app.dienste.transkription.basis import TranskriptionsFehler

GEWERKE = ("Bauleitung", "Rückbau", "Maurer", "Trockenbau", "Elektro",
           "Sanitär/Heizung", "Fliesen", "Maler", "Bodenleger", "Tischler",
           "Reinigung", "Sonstiges")


@pytest.fixture
def kontext():
    return Kontext(heute=date(2026, 9, 10), gewerke=GEWERKE, einheiten=codes(),
                   bauvorhaben="Musterstraße 12", regelbeginn=time(7, 0))


def roh(leistungen=(), datum=None, gewerk="Trockenbau", beginn=None, ende=None,
        dauer=None, bemerkung=None, unklarheiten=()) -> Rohentwurf:
    return Rohentwurf(
        datum_wortlaut=datum, gewerk=gewerk, leistungen=list(leistungen),
        arbeitszeit=RohArbeitszeit(beginn_wortlaut=beginn, ende_wortlaut=ende,
                                   dauer_wortlaut=dauer),
        bemerkung=bemerkung, unklarheiten=list(unklarheiten))


# --- Transkription ---------------------------------------------------------

def test_attrappe_liefert_reproduzierbaren_text():
    t = AttrappenTranskribierer()
    assert t.transkribiere(b"x" * 100, "audio/mp4").text == \
           t.transkribiere(b"x" * 100, "audio/mp4").text


def test_leere_aufnahme_wird_abgewiesen():
    with pytest.raises(TranskriptionsFehler, match="leer"):
        AttrappenTranskribierer().transkribiere(b"", "audio/mp4")


def test_anbieterwechsel_ueber_die_konfiguration():
    from app.config import Einstellungen
    assert transkribierer_erzeugen(
        Einstellungen(transkription_anbieter="attrappe")).name == "attrappe"
    with pytest.raises(TranskriptionsFehler, match="Unbekannter"):
        transkribierer_erzeugen(Einstellungen(transkription_anbieter="quatsch"))


def test_vokabular_enthaelt_gewerke_mitarbeiter_einheiten():
    """Kostet nichts und verbessert genau die schwierigen Begriffe."""
    vokabular = vokabular_zusammenstellen(("Trockenbau",), ("Ahrens", "Ahrens"), ("m²",))
    assert vokabular == ("Trockenbau", "Ahrens", "m²")      # ohne Dubletten


# --- A und B · korrekte Eingabe, mehrere Leistungen -----------------------

def test_beispiel_aus_dem_briefing(kontext):
    """§3: 65 m² gespachtelt, 40 m² geschliffen -> zwei getrennte Positionen."""
    entwurf = entwurf_erzeugen(
        "Heute 65 Quadratmeter gespachtelt und 40 Quadratmeter geschliffen.",
        kontext, AttrappenStrukturierer())

    assert entwurf.datum == date(2026, 9, 10)
    assert entwurf.gewerk == "Trockenbau"
    assert len(entwurf.leistungen) == 2
    assert [(l.menge, l.einheit) for l in entwurf.leistungen] == \
           [(Decimal("65"), "m²"), (Decimal("40"), "m²")]


def test_drei_leistungen_bleiben_drei(kontext):
    """§6: niemals zu einem Textblock zusammenfassen."""
    entwurf = normalisieren(roh(leistungen=[
        RohLeistung(taetigkeit="Spachtelarbeiten", beschreibung=None,
                    menge_wortlaut="50", einheit_wortlaut="Quadratmeter", konfidenz=0.9),
        RohLeistung(taetigkeit="Schleifarbeiten", beschreibung=None,
                    menge_wortlaut="35", einheit_wortlaut="qm", konfidenz=0.9),
        RohLeistung(taetigkeit="Türen grundieren", beschreibung=None,
                    menge_wortlaut="8", einheit_wortlaut="Stück", konfidenz=0.9),
    ]), kontext, "…")
    assert len(entwurf.leistungen) == 3
    assert entwurf.leistungen[2].einheit == "Stück"


# --- C und D · fehlende Menge, fehlende Einheit ---------------------------

def test_fehlende_menge_bleibt_leer_und_wird_nicht_geraten(kontext):
    entwurf = normalisieren(roh(leistungen=[
        RohLeistung(taetigkeit="Spachtelarbeiten", beschreibung=None,
                    menge_wortlaut=None, einheit_wortlaut=None, konfidenz=0.9),
    ]), kontext, "…")
    assert entwurf.leistungen[0].menge is None
    assert entwurf.leistungen[0].einheit is None


def test_unbekannte_einheit_erzeugt_eine_unklarheit(kontext):
    entwurf = normalisieren(roh(leistungen=[
        RohLeistung(taetigkeit="Schutt entsorgt", beschreibung=None,
                    menge_wortlaut="5", einheit_wortlaut="Eimer", konfidenz=0.7),
    ]), kontext, "…")
    position = entwurf.leistungen[0]
    assert position.menge == Decimal("5") and position.einheit is None
    assert position.einheit_unbekannt
    assert any("Eimer" in u for u in entwurf.unklarheiten)


def test_unlesbare_menge_erzeugt_eine_unklarheit(kontext):
    entwurf = normalisieren(roh(leistungen=[
        RohLeistung(taetigkeit="Wände gestrichen", beschreibung=None,
                    menge_wortlaut="ein paar", einheit_wortlaut="m²", konfidenz=0.5),
    ]), kontext, "…")
    assert entwurf.leistungen[0].menge is None
    assert entwurf.leistungen[0].menge_unklar
    assert any("ein paar" in u for u in entwurf.unklarheiten)


# --- F · unsichere Erkennung ----------------------------------------------

def test_unbekanntes_gewerk_wird_verworfen_nicht_zurechtgebogen(kontext):
    """D-05: kein Fuzzy-Matching. Ein falscher Name faellt in der Mappe
    lautlos aus der Auswertung."""
    entwurf = normalisieren(roh(gewerk="Dachdecker"), kontext, "…")
    assert entwurf.gewerk is None
    assert any("Dachdecker" in u for u in entwurf.unklarheiten)


def test_konfidenz_wird_durchgereicht(kontext):
    entwurf = normalisieren(roh(leistungen=[
        RohLeistung(taetigkeit="Unklar", beschreibung=None, menge_wortlaut=None,
                    einheit_wortlaut=None, konfidenz=0.3)]), kontext, "…")
    assert entwurf.leistungen[0].konfidenz == 0.3


def test_datum_in_der_zukunft_wird_zurueckgesetzt(kontext):
    """Mit Jahresangabe ist die Zukunft eindeutig - und unzulaessig."""
    entwurf = normalisieren(roh(datum="14.12.2026"), kontext, "…")
    assert entwurf.datum == kontext.heute
    assert entwurf.datum_abgeleitet
    assert any("Zukunft" in u for u in entwurf.unklarheiten)


def test_weit_entferntes_datum_ohne_jahr_wird_zur_rueckfrage(kontext):
    """Wer im September "14.12." sagt, meint kaum den vorletzten Dezember.
    Lieber nachfragen als still ein neun Monate altes Datum erzeugen."""
    entwurf = normalisieren(roh(datum="14.12."), kontext, "…")
    assert entwurf.datum == kontext.heute
    assert entwurf.datum_abgeleitet
    assert any("nicht eindeutig" in u for u in entwurf.unklarheiten)


# --- D-03 · nur eine Dauer genannt ----------------------------------------

def test_dauer_wird_mit_regelbeginn_ergaenzt_und_markiert(kontext):
    """Die Mappe rechnet aus Anfang und Ende. Eine blosse Dauer erzeugt dort
    keinen Wert - also ergaenzen, aber sichtbar als Annahme."""
    entwurf = normalisieren(roh(dauer="acht"), kontext, "…")
    assert (entwurf.beginn, entwurf.ende) == (time(7, 0), time(15, 0))
    assert entwurf.zeit_abgeleitet
    assert any("Dauer" in u for u in entwurf.unklarheiten)


def test_ohne_regelbeginn_wird_nichts_erfunden():
    kontext = Kontext(heute=date(2026, 9, 10), gewerke=GEWERKE, einheiten=codes(),
                      regelbeginn=None)
    entwurf = normalisieren(roh(dauer="acht"), kontext, "…")
    assert entwurf.beginn is None and entwurf.ende is None
    assert not entwurf.zeit_abgeleitet
    assert any("Anfang und Ende" in u for u in entwurf.unklarheiten)


def test_genannte_zeiten_werden_nicht_als_abgeleitet_markiert(kontext):
    entwurf = normalisieren(roh(beginn="7 Uhr", ende="16:30"), kontext, "…")
    assert (entwurf.beginn, entwurf.ende) == (time(7, 0), time(16, 30))
    assert not entwurf.zeit_abgeleitet


# --- K und L · fehlerhafte Antwort, Netzwerkfehler ------------------------

class FakeAntwort(SimpleNamespace):
    pass


def _claude_mit_antwort(antwort):
    from app.dienste.strukturierung.claude import ClaudeStrukturierer

    class FakeNachrichten:
        def __init__(self):
            self.aufrufe = []

        def create(self, **argumente):
            self.aufrufe.append(argumente)
            if isinstance(antwort, Exception):
                raise antwort
            return antwort

    nachrichten = FakeNachrichten()
    klient = SimpleNamespace(beta=SimpleNamespace(messages=nachrichten))
    return ClaudeStrukturierer(klient=klient), nachrichten


def test_claude_aufruf_traegt_modell_schema_und_ersatzmodelle(kontext):
    gueltig = ('{"datum_wortlaut": null, "gewerk": "Trockenbau", "leistungen": [], '
               '"arbeitszeit": {"beginn_wortlaut": null, "ende_wortlaut": null, '
               '"dauer_wortlaut": null}, "bemerkung": null, "unklarheiten": []}')
    strukturierer, nachrichten = _claude_mit_antwort(FakeAntwort(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=gueltig)]))

    ergebnis = strukturierer.strukturiere("Heute gespachtelt.", kontext)
    assert ergebnis.gewerk == "Trockenbau"

    aufruf = nachrichten.aufrufe[0]
    assert aufruf["model"] == "claude-opus-5"
    assert aufruf["output_config"]["effort"] == "low"
    assert aufruf["output_config"]["format"]["type"] == "json_schema"
    assert aufruf["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert aufruf["fallbacks"] == "default"
    # Gewerke und Einheiten muessen im Prompt stehen, sonst raet das Modell
    inhalt = aufruf["messages"][0]["content"]
    assert "Trockenbau" in inhalt and "m²" in inhalt and "10.09.2026" in inhalt


def test_ablehnung_fuehrt_nicht_in_eine_sackgasse(kontext):
    """stop_reason wird vor dem Inhalt geprueft (§27)."""
    strukturierer, _ = _claude_mit_antwort(FakeAntwort(
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="other"),
        content=[]))
    with pytest.raises(StrukturierungsFehler, match="von Hand"):
        strukturierer.strukturiere("Heute gespachtelt.", kontext)


def test_ungueltiges_json_wird_nicht_teilweise_uebernommen(kontext):
    strukturierer, _ = _claude_mit_antwort(FakeAntwort(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="{kaputt")]))
    with pytest.raises(StrukturierungsFehler, match="unvollstaendig"):
        strukturierer.strukturiere("Heute gespachtelt.", kontext)


def test_schemaverletzung_wird_abgewiesen(kontext):
    """Auch bei striktem Schema wird serverseitig nachgeprueft."""
    strukturierer, _ = _claude_mit_antwort(FakeAntwort(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text='{"gewerk": "Trockenbau"}')]))
    with pytest.raises(StrukturierungsFehler):
        strukturierer.strukturiere("Heute gespachtelt.", kontext)


def test_netzwerkfehler_ergibt_deutsche_meldung(kontext):
    strukturierer, _ = _claude_mit_antwort(ConnectionError("kein Netz"))
    with pytest.raises(StrukturierungsFehler, match="nicht erreichbar"):
        strukturierer.strukturiere("Heute gespachtelt.", kontext)


def test_leeres_transkript_wird_abgewiesen(kontext):
    strukturierer, _ = _claude_mit_antwort(FakeAntwort(stop_reason="end_turn", content=[]))
    with pytest.raises(StrukturierungsFehler, match="leer"):
        strukturierer.strukturiere("   ", kontext)


# --- Attrappe: keine plausibel aussehenden Fehlgriffe ---------------------

def test_attrappe_erfindet_keine_leistung_aus_einer_hausnummer(kontext):
    """Ohne Einheitenpruefung machte das Muster aus "Musterstraße 12. Wir
    haben …" die Leistung "Haben 12 Wir" - schlimmer als kein Ergebnis,
    weil es plausibel aussieht."""
    entwurf = entwurf_erzeugen(
        "Heute waren wir auf der Baustelle in der Musterstraße 12. "
        "Wir haben die Wände gespachtelt.",
        kontext, AttrappenStrukturierer())
    assert entwurf.leistungen == []
    assert any("keine Leistungsposition" in u for u in entwurf.unklarheiten)


def test_attrappe_liest_ausgeschriebene_uhrzeiten(kontext):
    entwurf = entwurf_erzeugen(
        "Gestern 65 Quadratmeter gespachtelt, von 7 Uhr bis halb fünf.",
        kontext, AttrappenStrukturierer())
    assert (entwurf.beginn, entwurf.ende) == (time(7, 0), time(16, 30))
