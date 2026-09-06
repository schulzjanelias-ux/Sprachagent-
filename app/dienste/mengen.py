"""Deutsche Mengenangaben aus dem Transkript in Decimal umwandeln.

Briefing §21 N: "ungefähr 45 Quadratmeter" -> 45 / m², "rund 12,5 qm" -> 12.5.

Decimal statt float, weil die Werte abrechnungsnah sind. Auch hier gilt:
deterministisch im Code, nicht im Sprachmodell.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Woerter, die eine Schaetzung ankuendigen. Der Wert wird uebernommen, aber
# als geschaetzt markiert - der Mitarbeiter sieht das im Bestaetigungsdialog.
SCHAETZWOERTER = (
    "ungefähr", "ungefaehr", "etwa", "circa", "zirka", "ca", "rund",
    "grob", "geschätzt", "geschaetzt", "in etwa", "so um die", "knapp", "gut",
)

# Ausgeschriebene Zahlen, wie sie in Sprache vorkommen.
ZAHLWOERTER = {
    "null": 0, "ein": 1, "eine": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4,
    "fünf": 5, "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
    "zehn": 10, "elf": 11, "zwölf": 12, "zwoelf": 12, "dreizehn": 13,
    "vierzehn": 14, "fünfzehn": 15, "fuenfzehn": 15, "sechzehn": 16,
    "siebzehn": 17, "achtzehn": 18, "neunzehn": 19, "zwanzig": 20,
    "dreißig": 30, "dreissig": 30, "vierzig": 40, "fünfzig": 50, "fuenfzig": 50,
    "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100,
}
BRUCHWOERTER = {
    "einhalb": Decimal("0.5"), "ein halb": Decimal("0.5"),
    "eineinhalb": Decimal("1.5"), "anderthalb": Decimal("1.5"),
    "zweieinhalb": Decimal("2.5"), "dreieinhalb": Decimal("3.5"),
    "viereinhalb": Decimal("4.5"), "fünfeinhalb": Decimal("5.5"),
    "fuenfeinhalb": Decimal("5.5"),
}

# 1.250,50 | 1250,5 | 1250.5 | 1250
ZAHLMUSTER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class Menge:
    wert: Decimal
    geschaetzt: bool = False


def _zahl_lesen(rohtext: str) -> Decimal | None:
    """Deutsche Schreibweise: Komma ist Dezimaltrenner, Punkt gruppiert."""
    text = rohtext.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", text):
        text = text.replace(".", "").replace(",", ".")        # 1.250,50
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")        # 1250,5
    # Ein einzelner Punkt bleibt Dezimaltrenner ("12.5" aus dem Transkript).
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _aus_worten(text: str) -> Decimal | None:
    bereinigt = " ".join(text.lower().split())
    if bereinigt in BRUCHWOERTER:
        return BRUCHWOERTER[bereinigt]
    if bereinigt in ZAHLWOERTER:
        return Decimal(ZAHLWOERTER[bereinigt])
    return None


def parsen(wortlaut: str | None) -> Menge | None:
    """Mengenangabe aus dem Wortlaut lesen.

        "65"                  -> 65
        "ungefähr 45"         -> 45,   geschaetzt
        "rund 12,5"           -> 12.5, geschaetzt
        "eineinhalb"          -> 1.5
        "1.250"               -> 1250
        "ein paar"            -> None  (wird zur Rueckfrage)
    """
    if not wortlaut or not wortlaut.strip():
        return None

    text = " ".join(wortlaut.strip().lower().split())
    geschaetzt = any(
        re.search(rf"(?<![a-zäöüß]){re.escape(wort)}(?![a-zäöüß])", text)
        for wort in SCHAETZWOERTER
    )

    if (treffer := ZAHLMUSTER.search(text)) and (wert := _zahl_lesen(treffer.group())) is not None:
        return Menge(wert, geschaetzt)

    ohne_schaetzwort = text
    for wort in SCHAETZWOERTER:
        ohne_schaetzwort = re.sub(
            rf"(?<![a-zäöüß]){re.escape(wort)}(?![a-zäöüß])", " ", ohne_schaetzwort)
    if (wert := _aus_worten(ohne_schaetzwort)) is not None:
        return Menge(wert, geschaetzt)

    return None
