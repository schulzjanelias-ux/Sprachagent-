"""Analysiert die HAG-Bauablaufmappe und belegt die in docs/EXCEL-MAPPING.md
dokumentierten Strukturannahmen.

Aufruf:
    python3 werkzeuge/mappe_analysieren.py [pfad/zur/mappe.xlsx]

Das Skript ist bewusst read-only. Es dient als reproduzierbarer Nachweis:
Wenn die HAG die Mappe aendert, zeigt ein erneuter Lauf sofort, ob die
Mapping-Annahmen (10-Zeilen-Bloecke, Formelspalten, Dropdown-Quellen) noch gelten.
"""
from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import openpyxl

STANDARD_MAPPE = Path(__file__).resolve().parents[1] / "referenz" / \
    "Bauablaufmappe_Projektcontrolling_anonymisiert.xlsx"

# Spalten der Zeiterfassung, die die App NIE beschreiben darf (Formeln/Layout).
GESPERRTE_SPALTEN = {"A": "KW", "B": "DATUM", "C": "TAG", "H": "ARBEITSSTUNDEN",
                     "K": "DATUM INTERN", "L": "KW-Hinweis"}
# Spalten, die die App befuellt.
SCHREIBBARE_SPALTEN = {"D": "MITARBEITER", "E": "GEWERK", "F": "ARBEITSANFANG",
                       "G": "ARBEITSENDE", "I": "LEISTUNGEN", "J": "TAGESBEMERKUNG"}


def abschnitt(titel: str) -> None:
    print(f"\n{'=' * 78}\n{titel}\n{'=' * 78}")


def blattuebersicht(wb) -> None:
    abschnitt("1 · WORKSHEETS")
    for ws in wb.worksheets:
        print(f"  {ws.title:24} {ws.dimensions:14} zeilen={ws.max_row:5} "
              f"spalten={ws.max_column:3} sichtbar={ws.sheet_state}")


def blockstruktur(ws) -> dict:
    """Weist die 10-Zeilen-Tagesblockstruktur ueber die verbundenen Zellen nach."""
    abschnitt("2 · TAGESBLOCK-STRUKTUR (Zeiterfassung)")
    bereiche = [str(r) for r in ws.merged_cells.ranges]
    je_spalte = Counter(re.match(r"([A-Z]+)", b).group(1) for b in bereiche)

    tagesmerges = [b for b in bereiche if re.match(r"^[ABCIJ]\d+:[ABCIJ]\d+$", b)]
    startzeilen = sorted({int(re.match(r"[A-Z]+(\d+)", b).group(1)) for b in tagesmerges})
    startzeilen = [z for z in startzeilen if z >= 6]
    hoehen = {int(re.match(r"[A-Z]+(\d+):[A-Z]+(\d+)", b).group(2))
              - int(re.match(r"[A-Z]+(\d+):[A-Z]+(\d+)", b).group(1)) + 1
              for b in tagesmerges if int(re.match(r"[A-Z]+(\d+)", b).group(1)) >= 6}
    abstaende = {b - a for a, b in zip(startzeilen, startzeilen[1:])}

    print(f"  Verbundene Bereiche gesamt : {len(bereiche)}")
    print(f"  Merges je Spalte           : {dict(je_spalte)}")
    print(f"  Tagesblock-Hoehe (Zeilen)  : {hoehen}")
    print(f"  Abstand der Blockanfaenge  : {abstaende}")
    print(f"  Erster Block beginnt in    : Zeile {startzeilen[0]}")
    print(f"  Anzahl Tagesbloecke        : {len(startzeilen)}")

    aufklappbar = sum(1 for z in range(startzeilen[0], startzeilen[0] + 10)
                      if ws.row_dimensions[z].outlineLevel > 0)
    print(f"  Mitarbeiter-Slots je Tag   : {10 - aufklappbar} sichtbar "
          f"+ {aufklappbar} aufklappbar = 10")
    return {"start": startzeilen[0], "hoehe": 10, "anzahl": len(startzeilen)}


def spaltenrollen(ws, struktur: dict) -> None:
    """Prueft, welche Spalten Formeln tragen (= tabu) und welche frei sind."""
    abschnitt("3 · SPALTENROLLEN (Zeile 6 = erste Datenzeile)")
    for spalte in "ABCDEFGHIJKL":
        zelle = ws[f"{spalte}6"]
        wert = zelle.value
        ist_formel = isinstance(wert, str) and wert.startswith("=")
        rolle = ("FORMEL – nicht beschreiben" if ist_formel else
                 "frei – App-Eingabe" if spalte in SCHREIBBARE_SPALTEN else "leer")
        erwartet = spalte in GESPERRTE_SPALTEN
        marker = "OK " if ist_formel == erwartet else "!! ABWEICHUNG"
        kopf = ws[f"{spalte}5"].value or ""
        print(f"  {marker} {spalte}  {str(kopf)[:26]:28} fmt={zelle.number_format:12} {rolle}")


def validierungen(ws) -> None:
    abschnitt("4 · DATENVALIDIERUNGEN (geschlossene Wertelisten)")
    for dv in ws.data_validations.dataValidation:
        print(f"  {str(dv.sqref):16} typ={dv.type:8} regel={dv.formula1}")


def stammdaten(wb) -> None:
    abschnitt("5 · STAMMDATENLISTEN (Blatt 'Listen')")
    ws = wb["Listen"]
    for name, dn in wb.defined_names.items():
        if "Listen" not in str(dn.value) or "INDEX" in str(dn.value):
            continue
        bereich = str(dn.value).split("!")[1].replace("$", "")
        werte = [z.value for reihe in ws[bereich] for z in reihe
                 if z.value not in (None, "")]
        beispiel = [str(w)[:18] for w in werte[:6]]
        print(f"  {name:22} n={len(werte):4}  z.B. {beispiel}")


def kopplungen(wb) -> None:
    """Zeigt, welche Auswertungen an der Zeiterfassung haengen."""
    abschnitt("6 · ABHAENGIGE AUSWERTUNGEN (was bricht, wenn Spalten wandern)")
    treffer = []
    for ws in wb.worksheets:
        if ws.title == "Zeiterfassung":
            continue
        for reihe in ws.iter_rows():
            for zelle in reihe:
                if isinstance(zelle.value, str) and "Zeiterfassung!" in zelle.value:
                    treffer.append((ws.title, zelle.coordinate, zelle.value))
    gesehen = set()
    for blatt, koord, formel in treffer:
        muster = re.sub(r"\d+", "#", formel)
        schluessel = (blatt, muster)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        print(f"  {blatt:22} {koord:6} {formel[:88]}")
    print(f"\n  Formeln mit Zeiterfassungs-Bezug gesamt: {len(treffer)}")


def roundtrip_risiko(pfad: Path) -> None:
    """Belegt, was ein openpyxl-Schreibvorgang an der Mappe zerstoeren wuerde."""
    abschnitt("7 · OPENPYXL-ROUND-TRIP: WAS GEHT VERLOREN?")
    ziel = pfad.parent / "_roundtrip_pruefung.xlsx"
    openpyxl.load_workbook(pfad).save(ziel)
    vorher, nachher = zipfile.ZipFile(pfad), zipfile.ZipFile(ziel)
    verloren = sorted(set(vorher.namelist()) - set(nachher.namelist()))
    vorher.close(); nachher.close(); ziel.unlink()

    if verloren:
        for n in verloren:
            print(f"  VERLUST: {n}")
        print("\n  Folge: Die Meistermappe darf nicht mit openpyxl zurueckgeschrieben")
        print("  werden. Siehe docs/DECISIONS.md · D-01.")
    else:
        print("  Kein Verlust festgestellt.")


def main() -> int:
    pfad = Path(sys.argv[1]) if len(sys.argv) > 1 else STANDARD_MAPPE
    if not pfad.exists():
        print(f"Mappe nicht gefunden: {pfad}", file=sys.stderr)
        return 1

    print(f"Analysiere: {pfad.name}  ({pfad.stat().st_size / 1024:.0f} KB)")
    wb = openpyxl.load_workbook(pfad)

    blattuebersicht(wb)
    struktur = blockstruktur(wb["Zeiterfassung"])
    spaltenrollen(wb["Zeiterfassung"], struktur)
    validierungen(wb["Zeiterfassung"])
    stammdaten(wb)
    kopplungen(wb)
    roundtrip_risiko(pfad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
