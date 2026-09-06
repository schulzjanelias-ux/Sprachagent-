"""Befehlszeile fuer Betrieb und Export.

    python3 -m app.cli mappe-pruefen   MAPPE.xlsx
    python3 -m app.cli mappe-befuellen MAPPE.xlsx --berichte daten.json [--probelauf]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from app.dienste.berichte import Leistung, Tagesbericht, Zeitfenster
from app.dienste.excel.befueller import mappe_befuellen
from app.dienste.excel.leser import MappenFehler, stammdaten_lesen


def berichte_aus_json(pfad: Path) -> list[Tagesbericht]:
    """Berichte aus einer JSON-Datei lesen.

    Zwischenloesung, solange die Datenbank (EPIC 07) noch nicht steht. Sie
    macht den Excel-Weg schon jetzt vollstaendig pruefbar - und bleibt danach
    als Weg nuetzlich, um einen Export von Hand nachzustellen.
    """
    rohdaten = json.loads(pfad.read_text(encoding="utf-8"))
    berichte = []
    for eintrag in rohdaten:
        berichte.append(Tagesbericht(
            bericht_id=eintrag["bericht_id"],
            datum=date.fromisoformat(eintrag["datum"]),
            mitarbeiter=eintrag["mitarbeiter"],
            zeitfenster=tuple(
                Zeitfenster(gewerk=f["gewerk"],
                            beginn=time.fromisoformat(f["beginn"]),
                            ende=time.fromisoformat(f["ende"]))
                for f in eintrag.get("zeitfenster", [])),
            leistungen=tuple(
                Leistung(taetigkeit=l["taetigkeit"],
                         beschreibung=l.get("beschreibung"),
                         menge=Decimal(str(l["menge"])) if l.get("menge") is not None else None,
                         einheit=l.get("einheit"),
                         geschaetzt=l.get("geschaetzt", False))
                for l in eintrag.get("leistungen", [])),
            bemerkung=eintrag.get("bemerkung"),
        ))
    return berichte


def befehl_mappe_pruefen(argumente) -> int:
    try:
        stammdaten = stammdaten_lesen(Path(argumente.mappe))
    except MappenFehler as fehler:
        print(f"Mappe nicht verwendbar: {fehler}", file=sys.stderr)
        return 1

    print(f"Bauvorhaben : {stammdaten.bauvorhaben or '— nicht gesetzt —'}")
    print(f"Bauzeit     : "
          f"{stammdaten.baubeginn or '—'} bis {stammdaten.bauende or '—'}")
    print(f"Gewerke     : {len(stammdaten.gewerke)}")
    print(f"Mitarbeiter : {len(stammdaten.mitarbeiter)}")
    print(f"Feiertage   : {len(stammdaten.feiertage)}")
    print("Geometrie   : in Ordnung")
    if not stammdaten.bauzeit_gesetzt:
        print("\nHinweis: Ohne Baubeginn und Bauende erzeugt die Mappe keine "
              "Datumswerte. Ein Export ist erst danach moeglich.")
    return 0


def befehl_mappe_befuellen(argumente) -> int:
    quelle = Path(argumente.mappe)
    berichte = berichte_aus_json(Path(argumente.berichte))

    ziel = Path(argumente.ziel) if argumente.ziel else quelle.with_name(
        f"{quelle.stem}_befuellt_{datetime.now():%Y-%m-%d_%H%M%S}.xlsx")

    try:
        plan = mappe_befuellen(
            quelle, ziel, berichte,
            bauvorhaben_erwartet=argumente.bauvorhaben,
            ueberschreiben=argumente.ueberschreiben,
            probelauf=argumente.probelauf)
    except MappenFehler as fehler:
        print(f"Abbruch: {fehler}", file=sys.stderr)
        return 1

    print(plan.bericht())
    if plan.fehler:
        return 1
    if argumente.probelauf:
        print("\nProbelauf — es wurde nichts geschrieben.")
    else:
        print(f"\nGeschrieben: {ziel}")
        print("Die Quellmappe wurde nicht veraendert.")
    return 0


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        prog="app.cli", description="HAG Tagesbericht — Werkzeuge")
    unterbefehle = zerleger.add_subparsers(dest="befehl", required=True)

    pruefen = unterbefehle.add_parser(
        "mappe-pruefen", help="Stammdaten und Geometrie einer Mappe anzeigen")
    pruefen.add_argument("mappe")
    pruefen.set_defaults(funktion=befehl_mappe_pruefen)

    befuellen = unterbefehle.add_parser(
        "mappe-befuellen", help="Eine Kopie der Mappe mit Berichten befuellen")
    befuellen.add_argument("mappe")
    befuellen.add_argument("--berichte", required=True, help="JSON-Datei mit Tagesberichten")
    befuellen.add_argument("--ziel", help="Ausgabedatei (Vorgabe: Quelle + Zeitstempel)")
    befuellen.add_argument("--bauvorhaben", help="erwarteter Projektname; sonst Abbruch")
    befuellen.add_argument("--probelauf", action="store_true",
                           help="nur pruefen und den Plan ausgeben, nichts schreiben")
    befuellen.add_argument("--ueberschreiben", action="store_true",
                           help="bereits befuellte Zielzellen ueberschreiben")
    befuellen.set_defaults(funktion=befehl_mappe_befuellen)

    argumente = zerleger.parse_args(argv)
    return argumente.funktion(argumente)


if __name__ == "__main__":
    raise SystemExit(main())
