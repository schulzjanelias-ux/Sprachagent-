"""Regelbasierter Strukturierer fuer Tests und den Betrieb ohne KI-Anbieter.

Erkennt das Muster "<Menge> <Einheit> <Taetigkeit>" beziehungsweise
"<Taetigkeit> <Menge> <Einheit>" in einfachen Saetzen. Er ersetzt das
Sprachmodell nicht - er macht die Testsuite offline lauffaehig und dient als
Rueckfallebene, solange D-09 offen ist.
"""
from __future__ import annotations

import re

from app.dienste.einheiten import normalisieren as einheit_normalisieren
from app.dienste.strukturierung.basis import (
    Kontext, RohArbeitszeit, RohLeistung, Rohentwurf, StrukturierungsFehler,
)

# "65 Quadratmeter gespachtelt" / "ungefähr 45 qm geschliffen"
MUSTER_MENGE_ZUERST = re.compile(
    r"(?P<menge>(?:ungefähr|etwa|circa|ca\.?|rund|knapp)?\s*[\d.,]+)\s+"
    r"(?P<einheit>[A-Za-zÄÖÜäöüß²³^]+)\s+(?P<taetigkeit>[a-zäöüß]+(?:t|en))",
    re.IGNORECASE)

# "von 7 Uhr bis 16:30" ebenso wie "von sieben bis halb fünf"
ZEITMUSTER = re.compile(
    r"von\s+(?P<beginn>(?:halb\s+)?[\wäöüß:.]+)\s*(?:uhr)?\s+bis\s+"
    r"(?P<ende>(?:halb\s+)?[\wäöüß:.]+)\s*(?:uhr)?",
    re.IGNORECASE)
DAUERMUSTER = re.compile(
    r"(?P<dauer>[\d.,]+|acht|neun|zehn|sieben|sechs|fünf|elf|zwölf)\s+Stunden",
    re.IGNORECASE)

GEWERKWOERTER = {
    "spachtel": "Trockenbau", "trockenbau": "Trockenbau", "ständerwerk": "Trockenbau",
    "gipskarton": "Trockenbau", "schleif": "Trockenbau",
    "streich": "Maler", "grundier": "Maler", "maler": "Maler", "lackier": "Maler",
    "fliese": "Fliesen", "elektr": "Elektro", "sanitär": "Sanitär/Heizung",
    "heizung": "Sanitär/Heizung", "maurer": "Maurer", "mauer": "Maurer",
    "abbruch": "Rückbau", "rückbau": "Rückbau", "entkern": "Rückbau",
    "reinig": "Reinigung", "boden": "Bodenleger", "tischler": "Tischler",
    "bauleitung": "Bauleitung",
}


class AttrappenStrukturierer:
    name = "attrappe"

    def strukturiere(self, transkript: str, kontext: Kontext) -> Rohentwurf:
        if not transkript or not transkript.strip():
            raise StrukturierungsFehler(
                "Das Transkript ist leer. Bitte die Aufnahme wiederholen.")

        text = transkript.strip()
        klein = text.lower()

        datum_wortlaut = next(
            (w for w in ("vorgestern", "gestern", "heute") if w in klein), None)

        gewerk = next((g for stichwort, g in GEWERKWOERTER.items()
                       if stichwort in klein and g in kontext.gewerke), None)

        # Nur Treffer uebernehmen, deren Einheit tatsaechlich eine bekannte
        # Einheit ist. Ohne diese Pruefung macht das Muster aus
        # "Musterstraße 12. Wir haben …" die Leistung "Haben 12 Wir" -
        # schlimmer als gar kein Ergebnis, weil es plausibel aussieht.
        leistungen = [
            RohLeistung(
                taetigkeit=treffer.group("taetigkeit").strip().capitalize(),
                beschreibung=None,
                menge_wortlaut=treffer.group("menge").strip(),
                einheit_wortlaut=treffer.group("einheit").strip(),
                konfidenz=0.8,
            )
            for treffer in MUSTER_MENGE_ZUERST.finditer(text)
            if einheit_normalisieren(treffer.group("einheit").strip()) is not None
        ]

        beginn = ende = dauer = None
        if treffer := ZEITMUSTER.search(text):
            beginn, ende = treffer.group("beginn").strip(), treffer.group("ende").strip()
        elif treffer := DAUERMUSTER.search(text):
            dauer = treffer.group("dauer").strip()

        unklarheiten = []
        if not leistungen:
            unklarheiten.append("Es wurde keine Leistungsposition erkannt.")
        if gewerk is None:
            unklarheiten.append("Das Gewerk liess sich nicht sicher zuordnen.")

        return Rohentwurf(
            datum_wortlaut=datum_wortlaut, gewerk=gewerk, leistungen=leistungen,
            arbeitszeit=RohArbeitszeit(beginn_wortlaut=beginn, ende_wortlaut=ende,
                                       dauer_wortlaut=dauer),
            bemerkung=None, unklarheiten=unklarheiten)
