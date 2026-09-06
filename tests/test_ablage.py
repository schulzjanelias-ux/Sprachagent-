"""EPIC 07 · Datenmodell und Ablage.

Schwerpunkte: Idempotenz bei wiederholtem Versand (Briefing §21 L),
verlustfreie Mengen, Versionierung statt Loeschen (D-13) und die Bruecke
zum Excel-Befueller.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.ablage import (
    AblageFehler, anwesenheiten_setzen, bericht_anlegen, bericht_ueber_uuid,
    berichte_fuer_export, bestaetigen, dialogschritt_anhaengen, eigene_berichte,
    exportlauf_protokollieren, korrigieren, positionen_setzen,
)
from app.datenbank import einrichten
from app.dienste.berichte import Leistung, Zeitfenster
from app.modelle import (
    Berichtsstatus, Mitarbeiter, Position, Projekt, Rolle, Sprecher, Zeitquelle,
)
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def sitzung(tmp_path):
    maschine = einrichten(tmp_path / "test.db")
    macher = sessionmaker(bind=maschine, expire_on_commit=False, future=True)
    with macher() as offen:
        offen.add_all([
            Mitarbeiter(anmeldename="ahrens", anzeigename="M. Ahrens",
                        excel_name="Ahrens", passwort_hash="x",
                        regelbeginn=time(7, 0)),
            Mitarbeiter(anmeldename="boettger", anzeigename="K. Böttger",
                        excel_name="Böttger", passwort_hash="x",
                        rolle=Rolle.bauleiter),
            Projekt(name="Musterstraße 12", mappe_pfad="/tmp/m.xlsx",
                    baubeginn=date(2026, 9, 1), bauende=date(2027, 6, 30)),
        ])
        offen.commit()
        yield offen


@pytest.fixture
def stammdaten(sitzung: Session):
    from sqlalchemy import select
    return (
        sitzung.scalar(select(Mitarbeiter).where(Mitarbeiter.anmeldename == "ahrens")),
        sitzung.scalar(select(Projekt)),
    )


def _bericht(sitzung, stammdaten, uuid="uuid-1", datum=date(2026, 9, 10)):
    mitarbeiter, projekt = stammdaten
    bericht, neu = bericht_anlegen(
        sitzung, client_uuid=uuid, mitarbeiter=mitarbeiter, projekt=projekt,
        datum=datum, rohtranskript="Heute 65 Quadratmeter gespachtelt.")
    positionen_setzen(sitzung, bericht, [
        Leistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²"),
        Leistung("Schleifarbeiten", menge=Decimal("40.5"), einheit="m²",
                 geschaetzt=True)])
    anwesenheiten_setzen(sitzung, bericht,
                         [Zeitfenster("Trockenbau", time(7, 0), time(16, 30))])
    return bericht, neu


# --- Idempotenz (Briefing §21 L) ------------------------------------------

def test_derselbe_versand_erzeugt_keinen_zweiten_bericht(sitzung, stammdaten):
    """Bei schlechtem Netz geht die Antwort verloren und das Handy sendet
    erneut. Ohne Idempotenz stuenden die Stunden doppelt in der Mappe."""
    erster, neu_erst = _bericht(sitzung, stammdaten)
    sitzung.commit()

    mitarbeiter, projekt = stammdaten
    zweiter, neu_zweit = bericht_anlegen(
        sitzung, client_uuid="uuid-1", mitarbeiter=mitarbeiter, projekt=projekt,
        datum=date(2026, 9, 10))

    assert neu_erst is True and neu_zweit is False
    assert zweiter.id == erster.id
    assert len(zweiter.positionen) == 2, "Positionen wurden nicht verdoppelt"


def test_uuid_ist_auf_datenbankebene_eindeutig(sitzung, stammdaten):
    """Auch bei einem Fehler in der Anwendungslogik greift die Datenbank."""
    from app.modelle import Bericht
    mitarbeiter, projekt = stammdaten
    sitzung.add_all([
        Bericht(client_uuid="doppelt", mitarbeiter_id=mitarbeiter.id,
                projekt_id=projekt.id, datum=date(2026, 9, 10)),
        Bericht(client_uuid="doppelt", mitarbeiter_id=mitarbeiter.id,
                projekt_id=projekt.id, datum=date(2026, 9, 11)),
    ])
    with pytest.raises(IntegrityError):
        sitzung.commit()
    sitzung.rollback()


# --- Mengen verlustfrei ----------------------------------------------------

@pytest.mark.parametrize("wert", ["65", "12.5", "0.1", "1250.75", "0.3333"])
def test_mengen_bleiben_exakt(sitzung, stammdaten, wert):
    """SQLite kennt kein Decimal. Ueber float gingen 0.1 und 12,5 kaputt -
    bei abrechnungsnahen Werten nicht hinnehmbar."""
    bericht, _ = _bericht(sitzung, stammdaten)
    positionen_setzen(sitzung, bericht,
                      [Leistung("Test", menge=Decimal(wert), einheit="m²")])
    sitzung.commit()
    sitzung.expunge_all()

    geladen = bericht_ueber_uuid(sitzung, "uuid-1")
    gelesen = geladen.positionen[0].menge
    assert isinstance(gelesen, Decimal)
    assert gelesen == Decimal(wert)
    assert str(gelesen) == wert


def test_fehlende_menge_bleibt_none(sitzung, stammdaten):
    bericht, _ = _bericht(sitzung, stammdaten)
    positionen_setzen(sitzung, bericht, [Leistung("Aufgeräumt")])
    sitzung.commit()
    assert bericht.positionen[0].menge is None
    assert bericht.positionen[0].einheit_code is None


# --- Fremdschluessel -------------------------------------------------------

def test_fremdschluessel_werden_geprueft(sitzung):
    """SQLite prueft ohne PRAGMA foreign_keys=ON gar nichts."""
    sitzung.add(Position(bericht_id=9999, taetigkeit="Waise"))
    with pytest.raises(IntegrityError):
        sitzung.commit()
    sitzung.rollback()


# --- Bestaetigung und Versionierung ---------------------------------------

def test_bestaetigen_setzt_status_und_zeitpunkt(sitzung, stammdaten):
    bericht, _ = _bericht(sitzung, stammdaten)
    bestaetigen(sitzung, bericht)
    assert bericht.status == Berichtsstatus.bestaetigt
    assert bericht.bestaetigt_am is not None


def test_ohne_arbeitszeit_keine_bestaetigung(sitzung, stammdaten):
    """D-03: Ohne Anfang und Ende entsteht in der Mappe keine Stundenzahl."""
    mitarbeiter, projekt = stammdaten
    bericht, _ = bericht_anlegen(sitzung, client_uuid="ohne-zeit",
                                 mitarbeiter=mitarbeiter, projekt=projekt,
                                 datum=date(2026, 9, 10))
    with pytest.raises(AblageFehler, match="Stundenzahl"):
        bestaetigen(sitzung, bericht)


def test_korrektur_erzeugt_neue_version_und_loescht_nichts(sitzung, stammdaten):
    """D-13: Nach einem Export muss nachvollziehbar bleiben, was in der
    Mappe gelandet ist."""
    original, _ = _bericht(sitzung, stammdaten)
    bestaetigen(sitzung, original)
    sitzung.commit()

    neu = korrigieren(sitzung, original, client_uuid="uuid-2")
    sitzung.commit()

    assert original.status == Berichtsstatus.storniert
    assert neu.version == 2 and neu.ersetzt_bericht_id == original.id
    assert len(neu.positionen) == 2 and len(neu.anwesenheiten) == 1
    assert bericht_ueber_uuid(sitzung, "uuid-1") is not None, "nichts hart geloescht"


def test_stornierter_bericht_ist_endgueltig(sitzung, stammdaten):
    original, _ = _bericht(sitzung, stammdaten)
    korrigieren(sitzung, original, client_uuid="uuid-2")
    with pytest.raises(AblageFehler, match="storniert"):
        korrigieren(sitzung, original, client_uuid="uuid-3")


def test_eigene_berichte_zeigen_keine_stornierten(sitzung, stammdaten):
    mitarbeiter, _ = stammdaten
    original, _ = _bericht(sitzung, stammdaten)
    korrigieren(sitzung, original, client_uuid="uuid-2")
    sitzung.commit()

    sichtbar = eigene_berichte(sitzung, mitarbeiter.id)
    assert [b.client_uuid for b in sichtbar] == ["uuid-2"]


# --- Bruecke zum Excel-Weg -------------------------------------------------

def test_export_liefert_werteobjekte_fuer_den_befueller(sitzung, stammdaten):
    """Der Befueller haengt bewusst nicht an SQLAlchemy."""
    _, projekt = stammdaten
    bericht, _ = _bericht(sitzung, stammdaten)
    bestaetigen(sitzung, bericht)
    sitzung.commit()

    ausgabe = berichte_fuer_export(sitzung, projekt.id)
    assert len(ausgabe) == 1
    eintrag = ausgabe[0]
    assert eintrag.mitarbeiter == "Ahrens"          # excel_name, nicht Anmeldename
    assert eintrag.datum == date(2026, 9, 10)
    assert eintrag.zeitfenster[0].gewerk == "Trockenbau"
    assert eintrag.leistungen[0].menge == Decimal("65")
    assert eintrag.leistungen[1].geschaetzt is True


def test_nur_bestaetigte_berichte_werden_exportiert(sitzung, stammdaten):
    """Briefing §12: Erst die Bestaetigung macht den Datensatz gueltig."""
    _, projekt = stammdaten
    _bericht(sitzung, stammdaten)                   # bleibt Entwurf
    sitzung.commit()
    assert berichte_fuer_export(sitzung, projekt.id) == []


def test_bereits_exportierte_berichte_werden_uebersprungen(sitzung, stammdaten):
    """M-6: Zwei Laeufe fuer denselben Zeitraum duerfen die Stunden nicht
    verdoppeln."""
    _, projekt = stammdaten
    bericht, _ = _bericht(sitzung, stammdaten)
    bestaetigen(sitzung, bericht)
    sitzung.commit()

    assert len(berichte_fuer_export(sitzung, projekt.id)) == 1
    exportlauf_protokollieren(sitzung, projekt_id=projekt.id,
                              ziel_datei="/tmp/befuellt.xlsx",
                              zuordnungen=[("uuid-1", 86, 1)])
    sitzung.commit()

    assert berichte_fuer_export(sitzung, projekt.id) == []
    assert len(berichte_fuer_export(sitzung, projekt.id,
                                    ohne_bereits_exportierte=False)) == 1


def test_zeitraum_wird_beachtet(sitzung, stammdaten):
    mitarbeiter, projekt = stammdaten
    for tag, uuid in ((date(2026, 9, 10), "a"), (date(2026, 9, 20), "b")):
        bericht, _ = _bericht(sitzung, stammdaten, uuid=uuid, datum=tag)
        bestaetigen(sitzung, bericht)
    sitzung.commit()

    gefiltert = berichte_fuer_export(sitzung, projekt.id, von=date(2026, 9, 15))
    assert [b.bericht_id for b in gefiltert] == ["b"]


def test_export_auf_unbekannten_bericht_scheitert(sitzung, stammdaten):
    _, projekt = stammdaten
    with pytest.raises(AblageFehler, match="keinen Datensatz"):
        exportlauf_protokollieren(sitzung, projekt_id=projekt.id,
                                  ziel_datei="/tmp/x.xlsx",
                                  zuordnungen=[("gibt-es-nicht", 86, 1)])


# --- Dialogschritte --------------------------------------------------------

def test_dialogschritte_bleiben_in_der_reihenfolge(sitzung, stammdaten):
    bericht, _ = _bericht(sitzung, stammdaten)
    dialogschritt_anhaengen(sitzung, bericht, Sprecher.mitarbeiter, "Erste Aufnahme", 12.0)
    dialogschritt_anhaengen(sitzung, bericht, Sprecher.system, "Wie viel gespachtelt?")
    dialogschritt_anhaengen(sitzung, bericht, Sprecher.mitarbeiter, "65 Quadratmeter", 3.0)
    sitzung.commit()

    assert [s.sprecher for s in bericht.dialogschritte] == [
        Sprecher.mitarbeiter, Sprecher.system, Sprecher.mitarbeiter]


def test_abgeleitete_zeiten_bleiben_unterscheidbar(sitzung, stammdaten):
    """D-03: Aus einer Dauer errechnete Zeiten muessen im Nachhinein als
    solche erkennbar sein."""
    bericht, _ = _bericht(sitzung, stammdaten)
    anwesenheiten_setzen(sitzung, bericht,
                         [Zeitfenster("Trockenbau", time(7, 0), time(15, 0))],
                         quelle=Zeitquelle.abgeleitet)
    sitzung.commit()
    assert bericht.anwesenheiten[0].quelle == Zeitquelle.abgeleitet


def test_ein_bericht_darf_mehrere_zeilen_belegen(sitzung, stammdaten):
    """Zwei Gewerke an einem Tag = zwei Zeilen in der Mappe. Der Bericht
    erscheint dann zweimal im selben Exportlauf."""
    _, projekt = stammdaten
    bericht, _ = _bericht(sitzung, stammdaten)
    anwesenheiten_setzen(sitzung, bericht, [
        Zeitfenster("Trockenbau", time(7, 0), time(12, 0)),
        Zeitfenster("Maler", time(12, 30), time(16, 0))])
    bestaetigen(sitzung, bericht)
    sitzung.commit()

    lauf = exportlauf_protokollieren(
        sitzung, projekt_id=projekt.id, ziel_datei="/tmp/x.xlsx",
        zuordnungen=[("uuid-1", 87, 2), ("uuid-1", 88, 3)])
    sitzung.commit()
    assert len(lauf.zuordnungen) == 2


def test_dieselbe_zielzeile_zweimal_wird_abgewiesen(sitzung, stammdaten):
    """Zwei Berichte duerfen nicht in dieselbe Zeile geschrieben werden."""
    _, projekt = stammdaten
    erster, _ = _bericht(sitzung, stammdaten, uuid="uuid-1")
    zweiter, _ = _bericht(sitzung, stammdaten, uuid="uuid-2")
    bestaetigen(sitzung, erster)
    bestaetigen(sitzung, zweiter)
    sitzung.commit()

    with pytest.raises(IntegrityError):
        exportlauf_protokollieren(
            sitzung, projekt_id=projekt.id, ziel_datei="/tmp/x.xlsx",
            zuordnungen=[("uuid-1", 86, 1), ("uuid-2", 86, 1)])
    sitzung.rollback()
