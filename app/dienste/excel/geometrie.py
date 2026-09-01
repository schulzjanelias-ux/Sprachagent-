"""Adressierung im Blatt 'Zeiterfassung' der Bauablaufmappe.

Die Mappe erzeugt ihr Kalendergeruest selbst: Spalte K fuellt sich ueber
WORKDAY.INTL(Baubeginn-1; n; "0000001") - die Maske schliesst nur den Sonntag
aus. Die App legt daher niemals Zeilen an, sie befuellt vorhandene.

    Tagesblock n beginnt in Zeile  6 + (n-1) * 10
    Mitarbeiterzeile fuer Slot s   blockstart + (s-1),  s = 1..10
    Leistungstext und Bemerkung    ausschliesslich in blockstart
                                   (Spalten I und J sind ueber den Block
                                   verbunden und nur oben beschreibbar)

Vollstaendige Herleitung in docs/EXCEL-MAPPING.md §5.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta

ERSTE_DATENZEILE = 6
ZEILEN_JE_TAG = 10
SLOTS_JE_TAG = ZEILEN_JE_TAG          # 5 sichtbar + 5 aufklappbar
TAGESBLOECKE_MAX = 366
LETZTE_DATENZEILE = ERSTE_DATENZEILE + TAGESBLOECKE_MAX * ZEILEN_JE_TAG - 1  # 3665

SONNTAG = 6                            # date.weekday(): Montag=0 … Sonntag=6

SPALTE_MITARBEITER = "D"
SPALTE_GEWERK = "E"
SPALTE_ANFANG = "F"
SPALTE_ENDE = "G"
SPALTE_LEISTUNGEN = "I"
SPALTE_BEMERKUNG = "J"


class GeometrieFehler(ValueError):
    """Das Datum hat in dieser Mappe keinen Platz."""


@dataclass(frozen=True)
class Zielzellen:
    """Wohin ein Bericht geschrieben wird. Rein rechnerisch, ohne Dateizugriff."""

    datum: date
    tagesindex: int          # 1-basiert, Position im Kalendergeruest
    blockstart: int          # Zeile, in der der Tagesblock beginnt
    slot: int                # 1..10
    zeile: int               # Zeile der Mitarbeiterdaten

    @property
    def mitarbeiter(self) -> str:
        return f"{SPALTE_MITARBEITER}{self.zeile}"

    @property
    def gewerk(self) -> str:
        return f"{SPALTE_GEWERK}{self.zeile}"

    @property
    def anfang(self) -> str:
        return f"{SPALTE_ANFANG}{self.zeile}"

    @property
    def ende(self) -> str:
        return f"{SPALTE_ENDE}{self.zeile}"

    @property
    def leistungen(self) -> str:
        """Verbundene Zelle - nur im Blockanfang beschreibbar."""
        return f"{SPALTE_LEISTUNGEN}{self.blockstart}"

    @property
    def bemerkung(self) -> str:
        return f"{SPALTE_BEMERKUNG}{self.blockstart}"


def ist_erfassungstag(tag: date, feiertage: frozenset[date] | set[date] = frozenset()) -> bool:
    """Kann an diesem Tag ueberhaupt erfasst werden?

    Sonntage haben im Geruest keine Zeile, Feiertage sind per Datenvalidierung
    gesperrt (docs/EXCEL-MAPPING.md §4).
    """
    return tag.weekday() != SONNTAG and tag not in feiertage


def tagesindex(baubeginn: date, tag: date) -> int:
    """Position von `tag` in der sonntagsfreien Folge ab `baubeginn` (1-basiert).

    Gegenstueck zu WORKDAY.INTL(baubeginn-1; n; "0000001").
    """
    if tag < baubeginn:
        raise GeometrieFehler(
            f"{tag:%d.%m.%Y} liegt vor dem Baubeginn {baubeginn:%d.%m.%Y}.")
    if tag.weekday() == SONNTAG:
        raise GeometrieFehler(
            f"{tag:%d.%m.%Y} ist ein Sonntag. Die Mappe hat dafuer keine Zeile.")

    tage_gesamt = (tag - baubeginn).days + 1
    # Sonntage im Intervall [baubeginn, tag] zaehlen
    erster_sonntag_versatz = (SONNTAG - baubeginn.weekday()) % 7
    sonntage = 0 if erster_sonntag_versatz >= tage_gesamt else \
        (tage_gesamt - erster_sonntag_versatz - 1) // 7 + 1
    return tage_gesamt - sonntage


def datum_zu_zeile(baubeginn: date, tag: date, slot: int = 1) -> Zielzellen:
    """Zielzellen fuer einen Tag und einen Mitarbeiter-Slot."""
    if not 1 <= slot <= SLOTS_JE_TAG:
        raise GeometrieFehler(
            f"Slot {slot} liegt ausserhalb von 1..{SLOTS_JE_TAG}. "
            f"Die Mappe fasst hoechstens {SLOTS_JE_TAG} Mitarbeiter je Tag.")

    index = tagesindex(baubeginn, tag)
    if index > TAGESBLOECKE_MAX:
        raise GeometrieFehler(
            f"{tag:%d.%m.%Y} ist Erfassungstag {index}. Die Mappe reicht nur "
            f"bis {TAGESBLOECKE_MAX}. Sie muss verlaengert werden (R-07).")

    blockstart = ERSTE_DATENZEILE + (index - 1) * ZEILEN_JE_TAG
    return Zielzellen(datum=tag, tagesindex=index, blockstart=blockstart,
                      slot=slot, zeile=blockstart + slot - 1)


def zeile_zu_datum(baubeginn: date, zeile: int) -> date:
    """Umkehrung: zu welchem Kalendertag gehoert eine Zeile?

    Dient der Gegenprobe beim Export und macht Fehler in der Adressierung
    sichtbar, statt sie in die Mappe zu schreiben.
    """
    if not ERSTE_DATENZEILE <= zeile <= LETZTE_DATENZEILE:
        raise GeometrieFehler(
            f"Zeile {zeile} liegt ausserhalb des Datenbereichs "
            f"{ERSTE_DATENZEILE}..{LETZTE_DATENZEILE}.")

    index = (zeile - ERSTE_DATENZEILE) // ZEILEN_JE_TAG + 1
    tag, verbleibend = baubeginn, index - 1
    if tag.weekday() == SONNTAG:
        tag += timedelta(days=1)
    while verbleibend:
        tag += timedelta(days=1)
        if tag.weekday() != SONNTAG:
            verbleibend -= 1
    return tag


def uhrzeit_zu_excel(zeitpunkt: time) -> float:
    """Uhrzeit als Bruchteil eines Tages, wie Excel sie in F und G erwartet.

    Die Datenvalidierung verlangt 0 <= x < 1 (docs/EXCEL-MAPPING.md §4).
    Sekunden werden verworfen; das Zellformat ist hh:mm.
    """
    return (zeitpunkt.hour * 60 + zeitpunkt.minute) / 1440


def arbeitsstunden(anfang: time, ende: time) -> float:
    """Was Excel in Spalte H rechnen wird: ROUND(MOD(G-F;1)*24;2).

    Nur zur Vorschau und Pruefung - geschrieben wird H niemals (D-03).
    MOD bildet Nachtschichten korrekt ab.
    """
    differenz = (uhrzeit_zu_excel(ende) - uhrzeit_zu_excel(anfang)) % 1
    return round(differenz * 24, 2)
