"""Lesen und Schreiben von Berichten (EPIC 07).

Hier liegt die Idempotenz: Jeder Bericht traegt eine vom Handy erzeugte UUID.
Geht bei schlechtem Netz die Antwort verloren und das Geraet sendet erneut,
liefert der zweite Aufruf denselben Bericht zurueck, statt die Stunden zu
verdoppeln (ARCHITECTURE §4). Ohne das waere die geforderte automatische
Wiederholung (Briefing §21 L) gefaehrlich.

Ausserdem die Bruecke zum Excel-Weg: berichte_fuer_export gibt Werteobjekte
zurueck, keine Datenbankzeilen - der Befueller bleibt von SQLAlchemy
unabhaengig.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.dienste import berichte as werte
from app.modelle import (
    Anwesenheit, Bericht, Berichtsstatus, Dialogschritt, Exportlauf,
    Exportzuordnung, Mitarbeiter, Position, Projekt, Sprecher, Zeitquelle,
)


class AblageFehler(ValueError):
    """Der Vorgang ist fachlich nicht zulaessig."""


# --- Schreiben -------------------------------------------------------------

def bericht_anlegen(
    sitzung: Session, *, client_uuid: str, mitarbeiter: Mitarbeiter,
    projekt: Projekt, datum: date, rohtranskript: str | None = None,
    bemerkung: str | None = None,
    status: Berichtsstatus = Berichtsstatus.entwurf,
) -> tuple[Bericht, bool]:
    """Bericht anlegen oder den vorhandenen zurueckgeben.

    Rueckgabe: (Bericht, neu_angelegt). Der zweite Wert erlaubt es dem
    Aufrufer, einen wiederholten Versand als solchen zu erkennen, statt ihn
    als Fehler zu behandeln.
    """
    vorhanden = sitzung.scalar(
        select(Bericht).where(Bericht.client_uuid == client_uuid))
    if vorhanden is not None:
        return vorhanden, False

    bericht = Bericht(
        client_uuid=client_uuid, mitarbeiter_id=mitarbeiter.id,
        projekt_id=projekt.id, datum=datum, status=status,
        rohtranskript=rohtranskript, bemerkung=bemerkung)
    sitzung.add(bericht)
    sitzung.flush()
    return bericht, True


def positionen_setzen(sitzung: Session, bericht: Bericht,
                      positionen: list[werte.Leistung]) -> None:
    """Ersetzt alle Positionen. Beim Korrigieren ist das der uebliche Weg."""
    bericht.positionen.clear()
    sitzung.flush()
    for reihenfolge, leistung in enumerate(positionen):
        bericht.positionen.append(Position(
            taetigkeit=leistung.taetigkeit, beschreibung=leistung.beschreibung,
            menge=leistung.menge, einheit_code=leistung.einheit,
            geschaetzt=leistung.geschaetzt, reihenfolge=reihenfolge))
    sitzung.flush()


def anwesenheiten_setzen(sitzung: Session, bericht: Bericht,
                         fenster: list[werte.Zeitfenster],
                         quelle: Zeitquelle = Zeitquelle.gesprochen) -> None:
    bericht.anwesenheiten.clear()
    sitzung.flush()
    for eintrag in fenster:
        bericht.anwesenheiten.append(Anwesenheit(
            gewerk=eintrag.gewerk, beginn=eintrag.beginn, ende=eintrag.ende,
            quelle=quelle))
    sitzung.flush()


def dialogschritt_anhaengen(sitzung: Session, bericht: Bericht, sprecher: Sprecher,
                            text: str, audio_dauer: float | None = None) -> None:
    bericht.dialogschritte.append(Dialogschritt(
        sprecher=sprecher, text=text, audio_dauer=audio_dauer))
    sitzung.flush()


def bestaetigen(sitzung: Session, bericht: Bericht) -> Bericht:
    """Erst hiermit wird der Bericht ein gueltiger Datensatz (Briefing §12)."""
    if bericht.status == Berichtsstatus.storniert:
        raise AblageFehler("Ein stornierter Bericht kann nicht bestaetigt werden.")
    if not bericht.anwesenheiten:
        raise AblageFehler(
            "Ohne Arbeitsanfang und -ende entsteht in der Mappe keine "
            "Stundenzahl. Der Bericht kann so nicht bestaetigt werden (D-03).")
    bericht.status = Berichtsstatus.bestaetigt
    bericht.bestaetigt_am = datetime.now()
    sitzung.flush()
    return bericht


def korrigieren(sitzung: Session, bericht: Bericht, *, client_uuid: str) -> Bericht:
    """Neue Version anlegen, alte stornieren - nie hart loeschen (D-13).

    Sobald exportiert wurde, muss nachvollziehbar bleiben, was in der Mappe
    gelandet ist.
    """
    if bericht.status == Berichtsstatus.storniert:
        raise AblageFehler("Dieser Bericht ist bereits storniert.")

    neu = Bericht(
        client_uuid=client_uuid, mitarbeiter_id=bericht.mitarbeiter_id,
        projekt_id=bericht.projekt_id, datum=bericht.datum,
        status=Berichtsstatus.entwurf, rohtranskript=bericht.rohtranskript,
        bemerkung=bericht.bemerkung, version=bericht.version + 1,
        ersetzt_bericht_id=bericht.id)
    sitzung.add(neu)
    sitzung.flush()

    for position in bericht.positionen:
        neu.positionen.append(Position(
            taetigkeit=position.taetigkeit, beschreibung=position.beschreibung,
            menge=position.menge, einheit_code=position.einheit_code,
            geschaetzt=position.geschaetzt, konfidenz=position.konfidenz,
            reihenfolge=position.reihenfolge))
    for anwesenheit in bericht.anwesenheiten:
        neu.anwesenheiten.append(Anwesenheit(
            gewerk=anwesenheit.gewerk, beginn=anwesenheit.beginn,
            ende=anwesenheit.ende, quelle=anwesenheit.quelle))

    bericht.status = Berichtsstatus.storniert
    sitzung.flush()
    return neu


# --- Lesen -----------------------------------------------------------------

def bericht_ueber_uuid(sitzung: Session, client_uuid: str) -> Bericht | None:
    return sitzung.scalar(select(Bericht).where(Bericht.client_uuid == client_uuid))


def eigene_berichte(sitzung: Session, mitarbeiter_id: int,
                    anzahl: int = 20) -> list[Bericht]:
    """Die letzten Berichte eines Mitarbeiters - seine Empfangsbestaetigung."""
    return list(sitzung.scalars(
        select(Bericht)
        .where(Bericht.mitarbeiter_id == mitarbeiter_id,
               Bericht.status != Berichtsstatus.storniert)
        .options(selectinload(Bericht.positionen), selectinload(Bericht.anwesenheiten))
        .order_by(Bericht.datum.desc(), Bericht.id.desc())
        .limit(anzahl)))


def berichte_fuer_export(sitzung: Session, projekt_id: int, von: date | None = None,
                         bis: date | None = None,
                         ohne_bereits_exportierte: bool = True) -> list[werte.Tagesbericht]:
    """Bestaetigte Berichte als Werteobjekte fuer den Excel-Befueller.

    `ohne_bereits_exportierte` schuetzt davor, dass zwei Laeufe fuer denselben
    Zeitraum die Stunden doppelt in die Mappe schreiben (M-6).
    """
    abfrage = (select(Bericht)
               .where(Bericht.projekt_id == projekt_id,
                      Bericht.status == Berichtsstatus.bestaetigt)
               .options(selectinload(Bericht.positionen),
                        selectinload(Bericht.anwesenheiten),
                        selectinload(Bericht.mitarbeiter))
               .order_by(Bericht.datum, Bericht.id))
    if von:
        abfrage = abfrage.where(Bericht.datum >= von)
    if bis:
        abfrage = abfrage.where(Bericht.datum <= bis)

    if ohne_bereits_exportierte:
        bereits = select(Exportzuordnung.bericht_id)
        abfrage = abfrage.where(Bericht.id.not_in(bereits))

    return [_als_werteobjekt(bericht) for bericht in sitzung.scalars(abfrage)]


def _als_werteobjekt(bericht: Bericht) -> werte.Tagesbericht:
    return werte.Tagesbericht(
        bericht_id=bericht.client_uuid,
        datum=bericht.datum,
        mitarbeiter=bericht.mitarbeiter.excel_name,
        zeitfenster=tuple(
            werte.Zeitfenster(gewerk=a.gewerk, beginn=a.beginn, ende=a.ende)
            for a in bericht.anwesenheiten),
        leistungen=tuple(
            werte.Leistung(taetigkeit=p.taetigkeit, beschreibung=p.beschreibung,
                           menge=p.menge, einheit=p.einheit_code,
                           geschaetzt=p.geschaetzt)
            for p in bericht.positionen),
        bemerkung=bericht.bemerkung,
        transkript=bericht.rohtranskript,
    )


# --- Exportprotokoll -------------------------------------------------------

def exportlauf_protokollieren(sitzung: Session, *, projekt_id: int, ziel_datei: str,
                              zuordnungen: list[tuple[str, int, int]],
                              von: date | None = None,
                              bis: date | None = None) -> Exportlauf:
    """Festhalten, welcher Bericht in welche Zeile ging (M-6).

    `zuordnungen` sind Tripel aus (client_uuid, ziel_zeile, ziel_slot) - genau
    das, was der Befueller zurueckgibt.
    """
    lauf = Exportlauf(projekt_id=projekt_id, ziel_datei=ziel_datei, von=von, bis=bis)
    sitzung.add(lauf)
    sitzung.flush()

    for client_uuid, zeile, slot in zuordnungen:
        bericht = bericht_ueber_uuid(sitzung, client_uuid)
        if bericht is None:
            raise AblageFehler(
                f"Zum Bericht {client_uuid!r} gibt es keinen Datensatz.")
        lauf.zuordnungen.append(Exportzuordnung(
            bericht_id=bericht.id, ziel_zeile=zeile, ziel_slot=slot))
    sitzung.flush()
    return lauf
