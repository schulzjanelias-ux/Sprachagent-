"""Relative Datums- und Zeitangaben aus dem Transkript aufloesen.

Briefing §9: Das Datum kommt normalerweise automatisch aus dem Zeitpunkt der
Erfassung; der Mitarbeiter soll es aber korrigieren koennen, wenn er einen
Bericht nachtraeglich erstellt.

Bewusst im Code und nicht im Sprachmodell: "gestern" haengt vom Erfassungstag
ab, und ein Modell, das rechnet, kann sich verrechnen, ohne dass es auffaellt.
So ist es ohne API-Aufruf testbar.
"""
from __future__ import annotations

import re
from datetime import date, time, timedelta

WOCHENTAGE = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
    "freitag": 4, "samstag": 5, "sonnabend": 5, "sonntag": 6,
}

# 14.3. | 14.03. | 14.3.2026 | 14.03.2026
DATUMSMUSTER = re.compile(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})?")
# 7 Uhr | 07:00 | 7.30 Uhr | halb acht
UHRZEITMUSTER = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:uhr)?\b")

# Wie weit darf ein Datum ohne Jahresangabe ins Vorjahr zurueckfallen?
RUECKFALL_TAGE_MAX = 100


def aufloesen(wortlaut: str | None, heute: date) -> date | None:
    """Wortlaut -> Datum. None, wenn nichts Eindeutiges erkennbar ist.

        "heute" / None        -> heute
        "gestern"             -> heute - 1
        "vorgestern"          -> heute - 2
        "letzten Freitag"     -> der letzte zurueckliegende Freitag
        "am Montag"           -> der letzte zurueckliegende Montag
        "14.3."               -> 14. Maerz, Jahr aus dem Kontext
        "nächste Woche"       -> None (in die Zukunft wird nicht erfasst)
    """
    if wortlaut is None:
        return heute

    text = " ".join(wortlaut.strip().lower().split())
    if not text or text in ("heute", "heute abend", "am heutigen tag"):
        return heute
    if text in ("gestern", "gestern abend"):
        return heute - timedelta(days=1)
    if text in ("vorgestern",):
        return heute - timedelta(days=2)

    if treffer := DATUMSMUSTER.search(text):
        tag, monat, jahr = treffer.groups()
        return _aus_teilen(int(tag), int(monat), jahr, heute)

    for name, nummer in WOCHENTAGE.items():
        if re.search(rf"(?<![a-zäöüß]){name}(?![a-zäöüß])", text):
            return _letzter_wochentag(nummer, heute)

    return None


def _aus_teilen(tag: int, monat: int, jahr: str | None, heute: date) -> date | None:
    if jahr:
        jahreszahl = int(jahr)
        if jahreszahl < 100:
            jahreszahl += 2000
    else:
        jahreszahl = heute.year
    try:
        ergebnis = date(jahreszahl, monat, tag)
    except ValueError:
        return None

    # Ohne Jahresangabe kurz nach dem Jahreswechsel meint "28.12." das Vorjahr.
    # Der Rueckfall gilt aber nur fuer die juengste Vergangenheit: Wer im
    # September "14.12." sagt, meint kaum den vorletzten Dezember - eher hat
    # die Spracherkennung sich verhoert. Dann lieber None und nachfragen,
    # als still ein neun Monate altes Datum zu erzeugen (Briefing §8).
    if not jahr and ergebnis > heute:
        try:
            vorjahr = date(jahreszahl - 1, monat, tag)
        except ValueError:
            return None
        return vorjahr if (heute - vorjahr).days <= RUECKFALL_TAGE_MAX else None
    return ergebnis


def _letzter_wochentag(wochentag: int, heute: date) -> date:
    """Der juengste zurueckliegende Tag mit diesem Wochentag.

    "am Freitag" am Montag gesagt meint den vergangenen Freitag, nicht den
    kommenden - es geht immer um bereits geleistete Arbeit.
    """
    versatz = (heute.weekday() - wochentag) % 7
    return heute - timedelta(days=versatz or 7)


def uhrzeit_aufloesen(wortlaut: str | None) -> time | None:
    """Uhrzeit aus dem Wortlaut.

        "7 Uhr" -> 07:00      "16:30" -> 16:30      "halb acht" -> 07:30
    """
    if not wortlaut or not wortlaut.strip():
        return None
    text = " ".join(wortlaut.strip().lower().split())

    if treffer := re.search(r"halb\s+(\w+)", text):
        stunde = _stundenwort(treffer.group(1))
        if stunde is not None:
            return time((stunde - 1) % 24, 30)

    if treffer := UHRZEITMUSTER.search(text):
        stunde = int(treffer.group(1))
        minute = int(treffer.group(2) or 0)
        if 0 <= stunde <= 23 and 0 <= minute <= 59:
            return time(stunde, minute)

    if (stunde := _stundenwort(text)) is not None:
        return time(stunde, 0)
    return None


def _stundenwort(text: str) -> int | None:
    from app.dienste.mengen import ZAHLWOERTER
    wert = ZAHLWOERTER.get(text.strip())
    return wert if wert is not None and 0 <= wert <= 23 else None


# Ein Arbeitstag laenger als diese Spanne ist unglaubwuerdig und deutet auf
# eine im Zwoelfstundenformat gesprochene Uhrzeit hin.
ARBEITSTAG_STUNDEN_MAX = 14


def nachmittag_korrigieren(beginn: time | None,
                           ende: time | None) -> tuple[time | None, bool]:
    """"halb fuenf" nach einem Beginn um 7 Uhr meint 16:30, nicht 04:30.

    Auf der Baustelle spricht niemand im Vierundzwanzigstundenformat. Eine
    blinde Umrechnung waere aber falsch: Die Mappe rechnet Nachtschichten
    ueber MOD korrekt ab, und "22 Uhr bis 6 Uhr" sind acht Stunden, keine
    achtzehn.

    Deshalb wird nur verschoben, wenn die Spanne dadurch **glaubwuerdiger**
    wird - laenger als 14 Stunden vorher, hoechstens 14 Stunden nachher.

        07:00 - 04:30  ->  07:00 - 16:30   (21,5 h wird zu 9,5 h)
        22:00 - 06:00  ->  unveraendert    (8 h, plausible Nachtschicht)

    Die korrigierte Zeit erscheint im Bestaetigungsdialog und ist dort
    aenderbar - geraten wird nichts, nur ausgelegt.
    """
    if beginn is None or ende is None or ende.hour >= 12:
        return ende, False

    def spanne(bis: time) -> float:
        stunden = (bis.hour * 60 + bis.minute) - (beginn.hour * 60 + beginn.minute)
        return (stunden % (24 * 60)) / 60

    if spanne(ende) <= ARBEITSTAG_STUNDEN_MAX:
        return ende, False

    verschoben = time(ende.hour + 12, ende.minute)
    if spanne(verschoben) <= ARBEITSTAG_STUNDEN_MAX:
        return verschoben, True
    return ende, False
