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
from app.dienste.einheiten import codes as einheiten_codes
from app.dienste.excel.befueller import mappe_befuellen
from app.dienste.excel.leser import MappenFehler, stammdaten_lesen
from app.dienste.strukturierung import (
    Kontext, StrukturierungsFehler, entwurf_erzeugen,
)
from app.dienste.transkription import (
    TranskriptionsFehler, transkribierer_erzeugen, vokabular_zusammenstellen,
)


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


def befehl_bericht_aus_audio(argumente) -> int:
    """Audio -> Transkript -> Entwurf. Gibt den Entwurf als JSON aus.

    Damit ist die Kette Aufnahme -> befuellte Mappe schon vor der Oberflaeche
    vollstaendig pruefbar:

        bericht-aus-audio aufnahme.m4a --mappe M.xlsx > bericht.json
        mappe-befuellen M.xlsx --berichte bericht.json --probelauf
    """
    audio_pfad = Path(argumente.audio)
    if not audio_pfad.exists():
        print(f"Aufnahme nicht gefunden: {audio_pfad}", file=sys.stderr)
        return 1

    try:
        stammdaten = stammdaten_lesen(Path(argumente.mappe))
    except MappenFehler as fehler:
        print(f"Mappe nicht verwendbar: {fehler}", file=sys.stderr)
        return 1

    vokabular = vokabular_zusammenstellen(
        stammdaten.gewerke, stammdaten.mitarbeiter, einheiten_codes())

    try:
        transkript = transkribierer_erzeugen().transkribiere(
            audio_pfad.read_bytes(), argumente.mime, vokabular)
    except TranskriptionsFehler as fehler:
        print(f"Spracherkennung: {fehler}", file=sys.stderr)
        return 1

    heute = (date.fromisoformat(argumente.heute) if argumente.heute
             else date.today())
    kontext = Kontext(
        heute=heute, gewerke=stammdaten.gewerke, einheiten=einheiten_codes(),
        bauvorhaben=stammdaten.bauvorhaben,
        regelbeginn=time.fromisoformat(argumente.regelbeginn) if argumente.regelbeginn else None)

    try:
        entwurf = entwurf_erzeugen(transkript.text, kontext)
    except StrukturierungsFehler as fehler:
        print(f"Auswertung: {fehler}", file=sys.stderr)
        print(f"\nTranskript zur manuellen Erfassung:\n{transkript.text}", file=sys.stderr)
        return 1

    if argumente.mitarbeiter and argumente.mitarbeiter not in stammdaten.mitarbeiter:
        print(f"{argumente.mitarbeiter!r} steht nicht in der Mitarbeiterliste "
              f"der Mappe.", file=sys.stderr)
        return 1

    print(json.dumps([{
        "bericht_id": argumente.bericht_id,
        "datum": entwurf.datum.isoformat(),
        "mitarbeiter": argumente.mitarbeiter,
        "zeitfenster": ([{"gewerk": entwurf.gewerk,
                          "beginn": entwurf.beginn.isoformat(timespec="minutes"),
                          "ende": entwurf.ende.isoformat(timespec="minutes")}]
                        if entwurf.gewerk and entwurf.beginn and entwurf.ende else []),
        "leistungen": [{"taetigkeit": l.taetigkeit, "beschreibung": l.beschreibung,
                        "menge": str(l.menge) if l.menge is not None else None,
                        "einheit": l.einheit, "geschaetzt": l.geschaetzt}
                       for l in entwurf.leistungen],
        "bemerkung": entwurf.bemerkung,
        "_transkript": entwurf.transkript,
        "_unklarheiten": entwurf.unklarheiten,
        "_datum_abgeleitet": entwurf.datum_abgeleitet,
        "_zeit_abgeleitet": entwurf.zeit_abgeleitet,
    }], ensure_ascii=False, indent=2))

    # Ein Bericht ohne Gewerk oder ohne Zeiten erzeugt in der Mappe keine
    # Zeile - und ohne Arbeitsstunden bleibt das Controlling leer (D-03).
    # Das darf nicht stillschweigend als leeres Ergebnis durchgehen (§28).
    fehlt = []
    if not entwurf.gewerk:
        fehlt.append("Gewerk")
    if not entwurf.beginn or not entwurf.ende:
        fehlt.append("Arbeitsanfang und -ende")
    if not entwurf.leistungen:
        fehlt.append("mindestens eine Leistungsposition")

    if entwurf.unklarheiten or fehlt:
        print("\nOffene Punkte (im Dialog nachzufragen):", file=sys.stderr)
        for punkt in entwurf.unklarheiten:
            print(f"  · {punkt}", file=sys.stderr)
        for feld in fehlt:
            print(f"  · Es fehlt: {feld}", file=sys.stderr)

    if fehlt:
        print("\nDer Entwurf ist unvollstaendig und wuerde in der Mappe keine "
              "Zeile erzeugen. Rueckgabewert 2.", file=sys.stderr)
        return 2
    return 0


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

    aus_audio = unterbefehle.add_parser(
        "bericht-aus-audio", help="Aufnahme transkribieren und strukturieren")
    aus_audio.add_argument("audio")
    aus_audio.add_argument("--mappe", required=True, help="Projektmappe fuer die Stammdaten")
    aus_audio.add_argument("--mitarbeiter", required=True, help="Name aus der Mitarbeiterliste")
    aus_audio.add_argument("--bericht-id", dest="bericht_id", default="TB-ENTWURF")
    aus_audio.add_argument("--mime", default="audio/mp4")
    aus_audio.add_argument("--heute", help="Erfassungstag ueberschreiben (JJJJ-MM-TT)")
    aus_audio.add_argument("--regelbeginn", help="Regelarbeitsbeginn, z. B. 07:00 (D-03)")
    aus_audio.set_defaults(funktion=befehl_bericht_aus_audio)

    argumente = zerleger.parse_args(argv)
    return argumente.funktion(argumente)


if __name__ == "__main__":
    raise SystemExit(main())
