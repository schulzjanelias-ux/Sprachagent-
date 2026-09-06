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
from app.modelle import Mitarbeiter, Projekt, Rolle
from app.sicherheit import (
    einmalpasswort, passwort_bewerten, passwort_hashen, sitzungs_kennung_erzeugen,
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


def befehl_benutzer_anlegen(argumente) -> int:
    """Konto mit Einmalpasswort anlegen (D-11).

    Das Passwort wird einmal ausgegeben und nirgends gespeichert - nur sein
    Hash. Beim ersten Anmelden muss der Mitarbeiter es wechseln.
    """
    from app.datenbank import einrichten, sitzung as datenbank_sitzung
    from sqlalchemy import func, select

    einrichten()
    with datenbank_sitzung() as sitzung:
        vorhanden = sitzung.scalar(select(Mitarbeiter).where(
            func.lower(Mitarbeiter.anmeldename) == argumente.anmeldename.lower()))
        if vorhanden is not None:
            print(f"Der Anmeldename {argumente.anmeldename!r} ist bereits vergeben.",
                  file=sys.stderr)
            return 1

        passwort = argumente.passwort or einmalpasswort()
        if argumente.passwort and (gruende := passwort_bewerten(passwort)):
            print(" ".join(gruende), file=sys.stderr)
            return 1

        sitzung.add(Mitarbeiter(
            anmeldename=argumente.anmeldename,
            anzeigename=argumente.anzeigename,
            excel_name=argumente.excel_name,
            passwort_hash=passwort_hashen(passwort),
            passwort_wechseln=True,
            rolle=Rolle(argumente.rolle),
            regelbeginn=time.fromisoformat(argumente.regelbeginn) if argumente.regelbeginn else None,
            sitzungs_kennung=sitzungs_kennung_erzeugen()))

    print(f"Konto angelegt: {argumente.anmeldename}")
    print(f"Einmalpasswort: {passwort}")
    print("\nDieses Passwort wird nicht gespeichert und nicht erneut angezeigt.")
    print("Der Mitarbeiter muss es bei der ersten Anmeldung wechseln.")
    return 0


def befehl_benutzer_passwort_neu(argumente) -> int:
    """Passwort zuruecksetzen. Nur ueber die Bauleitung - kein Weg per E-Mail."""
    from app.datenbank import einrichten, sitzung as datenbank_sitzung
    from sqlalchemy import func, select

    einrichten()
    with datenbank_sitzung() as sitzung:
        mitarbeiter = sitzung.scalar(select(Mitarbeiter).where(
            func.lower(Mitarbeiter.anmeldename) == argumente.anmeldename.lower()))
        if mitarbeiter is None:
            print(f"Kein Konto mit dem Anmeldenamen {argumente.anmeldename!r}.",
                  file=sys.stderr)
            return 1

        passwort = einmalpasswort()
        mitarbeiter.passwort_hash = passwort_hashen(passwort)
        mitarbeiter.passwort_wechseln = True
        # Beendet alle laufenden Sitzungen, auch auf anderen Geraeten.
        mitarbeiter.sitzungs_kennung = sitzungs_kennung_erzeugen()

    print(f"Passwort zurueckgesetzt: {argumente.anmeldename}")
    print(f"Einmalpasswort: {passwort}")
    print("\nAlle bisherigen Sitzungen dieses Kontos sind damit beendet.")
    return 0


def befehl_projekt_anlegen(argumente) -> int:
    """Projekt mit Verweis auf seine Bauablaufmappe eintragen."""
    from app.datenbank import einrichten, sitzung as datenbank_sitzung
    from sqlalchemy import select

    mappe = Path(argumente.mappe).resolve()
    try:
        stammdaten = stammdaten_lesen(mappe)
    except MappenFehler as fehler:
        print(f"Mappe nicht verwendbar: {fehler}", file=sys.stderr)
        return 1

    if stammdaten.bauvorhaben and stammdaten.bauvorhaben != argumente.name:
        print(f"Die Mappe gehoert zum Bauvorhaben {stammdaten.bauvorhaben!r}, "
              f"angegeben wurde {argumente.name!r} (D-04).", file=sys.stderr)
        return 1

    einrichten()
    with datenbank_sitzung() as sitzung:
        if sitzung.scalar(select(Projekt).where(Projekt.name == argumente.name)):
            print(f"Projekt {argumente.name!r} ist bereits eingetragen.", file=sys.stderr)
            return 1
        sitzung.add(Projekt(name=argumente.name, mappe_pfad=str(mappe),
                            baubeginn=stammdaten.baubeginn, bauende=stammdaten.bauende))

    print(f"Projekt angelegt: {argumente.name}")
    print(f"Mappe   : {mappe}")
    print(f"Bauzeit : {stammdaten.baubeginn or '—'} bis {stammdaten.bauende or '—'}")
    if not stammdaten.bauzeit_gesetzt:
        print("\nHinweis: Ohne Baubeginn und Bauende in der Mappe ist kein "
              "Export moeglich.")
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

    anlegen = unterbefehle.add_parser(
        "benutzer-anlegen", help="Konto mit Einmalpasswort anlegen")
    anlegen.add_argument("anmeldename")
    anlegen.add_argument("--anzeigename", required=True)
    anlegen.add_argument("--excel-name", dest="excel_name", required=True,
                         help="Name wortgleich aus MitarbeiterListe der Mappe")
    anlegen.add_argument("--rolle", default="mitarbeiter",
                         choices=[r.value for r in Rolle])
    anlegen.add_argument("--regelbeginn", help="z. B. 07:00 (D-03)")
    anlegen.add_argument("--passwort", help="statt eines erzeugten Einmalpassworts")
    anlegen.set_defaults(funktion=befehl_benutzer_anlegen)

    zuruecksetzen = unterbefehle.add_parser(
        "benutzer-passwort-neu", help="Passwort zuruecksetzen (Bauleitung)")
    zuruecksetzen.add_argument("anmeldename")
    zuruecksetzen.set_defaults(funktion=befehl_benutzer_passwort_neu)

    projekt = unterbefehle.add_parser(
        "projekt-anlegen", help="Projekt mit seiner Bauablaufmappe eintragen")
    projekt.add_argument("name")
    projekt.add_argument("--mappe", required=True)
    projekt.set_defaults(funktion=befehl_projekt_anlegen)

    argumente = zerleger.parse_args(argv)
    return argumente.funktion(argumente)


if __name__ == "__main__":
    raise SystemExit(main())
