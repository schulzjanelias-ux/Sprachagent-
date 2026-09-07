"""Erkennungsqualitaet an echten Sprachaufnahmen messen.

Zweck: Bevor die Oberflaeche gebaut wird, muss belegt sein, dass die Kette
Transkription -> Strukturierung auf echter Bausprache traegt. Nicht auf
ausgedachten Beispielsaetzen.

    python3 werkzeuge/realitaetstest.py aufnahmen/*.ogg \
        --mappe referenz/mappe.xlsx --bericht ergebnis.md

Erzeugt einen Markdown-Bericht mit je Aufnahme: technische Kennwerte,
Transkript, erkannte Felder, offene Luecken und die Rueckfrage. Der Bericht
enthaelt Ankreuzfelder - jemand aus dem Betrieb traegt ein, was richtig war.
Erst daraus wird eine Trefferquote, die etwas wert ist.

Anbieter kommen aus der .env (D-09). Ohne Schluessel laeuft der Test mit den
Attrappen und pruefen damit nur, ob die Kette technisch durchlaeuft.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import date, time as uhrzeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dienste.dialog import starten                                # noqa: E402
from app.dienste.einheiten import codes as einheiten_codes            # noqa: E402
from app.dienste.excel.leser import MappenFehler, stammdaten_lesen    # noqa: E402
from app.dienste.strukturierung import (                              # noqa: E402
    Kontext, StrukturierungsFehler, strukturierer_erzeugen,
)
from app.dienste.transkription import (                               # noqa: E402
    TranskriptionsFehler, transkribierer_erzeugen, vokabular_zusammenstellen,
)

MIME_NACH_ENDUNG = {".ogg": "audio/ogg", ".opus": "audio/ogg", ".m4a": "audio/mp4",
                    ".mp4": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                    ".webm": "audio/webm", ".aac": "audio/aac", ".flac": "audio/flac"}


@dataclass
class Messung:
    datei: str
    dauer: float | None = None
    groesse_kb: float = 0.0
    sekunden_transkription: float = 0.0
    sekunden_strukturierung: float = 0.0
    transkript: str = ""
    fehler: str | None = None
    stand: object = None


def audio_kennwerte(pfad: Path) -> tuple[float | None, str]:
    """Dauer und Codec, wenn PyAV vorhanden ist - sonst ohne."""
    try:
        import av
    except ImportError:
        return None, "unbekannt"
    try:
        with av.open(str(pfad)) as behaelter:
            spur = behaelter.streams.audio[0]
            rate = spur.codec_context.sample_rate
            samples = sum(rahmen.samples for rahmen in behaelter.decode(audio=0))
            return samples / rate, spur.codec_context.name
    except Exception:                                        # noqa: BLE001
        return None, "unlesbar"


def messen(pfad: Path, kontext: Kontext, vokabular: tuple[str, ...],
           transkribierer, strukturierer) -> Messung:
    ergebnis = Messung(datei=pfad.name, groesse_kb=pfad.stat().st_size / 1024)
    ergebnis.dauer, _ = audio_kennwerte(pfad)

    mime = MIME_NACH_ENDUNG.get(pfad.suffix.lower(), "audio/ogg")
    beginn = time.perf_counter()
    try:
        transkript = transkribierer.transkribiere(pfad.read_bytes(), mime, vokabular)
    except TranskriptionsFehler as fehler:
        ergebnis.fehler = f"Transkription: {fehler}"
        return ergebnis
    ergebnis.sekunden_transkription = time.perf_counter() - beginn
    ergebnis.transkript = transkript.text

    beginn = time.perf_counter()
    try:
        ergebnis.stand = starten(transkript.text, kontext, strukturierer)
    except StrukturierungsFehler as fehler:
        ergebnis.fehler = f"Strukturierung: {fehler}"
        return ergebnis
    ergebnis.sekunden_strukturierung = time.perf_counter() - beginn
    return ergebnis


def bericht_schreiben(messungen: list[Messung], ziel: Path, *, transkribierer: str,
                      strukturierer: str, kontext: Kontext) -> None:
    zeilen = [
        "# Realitätstest — Erkennungsqualität",
        "",
        f"Aufnahmen: **{len(messungen)}** · Transkription: `{transkribierer}` · "
        f"Strukturierung: `{strukturierer}` · Erfassungstag: {kontext.heute:%d.%m.%Y}",
        "",
        "> **So wird der Bericht ausgefüllt:** Jemand, der die Aufnahme gehört hat,",
        "> hakt je Feld ab, ob die Erkennung stimmt. Erst daraus wird eine",
        "> Trefferquote, die etwas wert ist — nicht aus meiner Einschätzung.",
        "",
        "## Überblick",
        "",
        "| Aufnahme | Dauer | Transkription | Auswertung | Positionen | Lücken |",
        "|---|---|---|---|---|---|",
    ]
    for messung in messungen:
        stand = messung.stand
        positionen = len(stand.entwurf.leistungen) if stand else 0
        luecken = len(stand.luecken) if stand else "—"
        dauer = f"{messung.dauer:.0f}s" if messung.dauer else "—"
        zeilen.append(
            f"| {messung.datei[:28]} | {dauer} | {messung.sekunden_transkription:.1f}s "
            f"| {messung.sekunden_strukturierung:.1f}s | {positionen} | {luecken} |")

    for nummer, messung in enumerate(messungen, start=1):
        zeilen += ["", "---", "", f"## {nummer}. {messung.datei}", ""]
        if messung.fehler:
            zeilen += [f"**Fehlgeschlagen:** {messung.fehler}", ""]
            continue

        zeilen += ["**Transkript**", "", "> " + messung.transkript.replace("\n", "\n> "),
                   "", "- [ ] Transkript ist inhaltlich richtig",
                   "- [ ] Fachbegriffe richtig geschrieben "
                   "(Gewerke, Einheiten, Materialien)", ""]

        stand = messung.stand
        entwurf = stand.entwurf
        zeilen += ["**Erkannt**", "", "| Feld | Wert | stimmt? |", "|---|---|---|",
                   f"| Datum | {entwurf.datum:%d.%m.%Y}"
                   f"{' (abgeleitet)' if entwurf.datum_abgeleitet else ''} | [ ] |",
                   f"| Gewerk | {entwurf.gewerk or '—'} | [ ] |",
                   f"| Arbeitszeit | "
                   f"{_zeitspanne(entwurf.beginn, entwurf.ende)}"
                   f"{' (abgeleitet)' if entwurf.zeit_abgeleitet else ''} | [ ] |"]
        for position in entwurf.leistungen:
            menge = "—" if position.menge is None else \
                f"{position.menge} {position.einheit or '?'}"
            zusatz = " · geschätzt" if position.geschaetzt else ""
            zeilen.append(f"| Leistung | {position.taetigkeit}: {menge}{zusatz} | [ ] |")
        if entwurf.bemerkung:
            zeilen.append(f"| Bemerkung | {entwurf.bemerkung} | [ ] |")
        zeilen.append("")

        zeilen += ["- [ ] **Es wurde nichts erfunden**, was nicht gesagt wurde", ""]

        if stand.luecken:
            zeilen += ["**Offen**", ""]
            zeilen += [f"- {l.beschreibung}" for l in stand.luecken]
            zeilen += ["", f"**Rückfrage:** {stand.rueckfrage or '—'}", "",
                       "- [ ] Die Rückfrage ist verständlich und trifft das Fehlende", ""]
        else:
            zeilen += ["**Keine Lücken** — der Bericht wäre ohne Rückfrage "
                       "bestätigungsreif.", ""]

        if stand.hinweise:
            zeilen += ["**Hinweise**", ""] + [f"- {h}" for h in stand.hinweise] + [""]

    ziel.write_text("\n".join(zeilen), encoding="utf-8")


def _zeitspanne(beginn: uhrzeit | None, ende: uhrzeit | None) -> str:
    if beginn is None or ende is None:
        return "—"
    return f"{beginn:%H:%M} bis {ende:%H:%M}"


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Erkennungsqualitaet an echten Aufnahmen messen")
    zerleger.add_argument("aufnahmen", nargs="+")
    zerleger.add_argument("--mappe", required=True,
                          help="Projektmappe fuer Gewerke und Mitarbeiternamen")
    zerleger.add_argument("--bericht", default="realitaetstest.md")
    zerleger.add_argument("--heute", help="Erfassungstag (JJJJ-MM-TT)")
    zerleger.add_argument("--regelbeginn", default="07:00")
    argumente = zerleger.parse_args(argv)

    try:
        stammdaten = stammdaten_lesen(Path(argumente.mappe))
    except MappenFehler as fehler:
        print(f"Mappe nicht verwendbar: {fehler}", file=sys.stderr)
        return 1

    try:
        transkribierer = transkribierer_erzeugen()
        strukturierer = strukturierer_erzeugen()
    except (TranskriptionsFehler, StrukturierungsFehler) as fehler:
        print(f"Anbieter nicht verfuegbar: {fehler}", file=sys.stderr)
        return 1

    if transkribierer.name == "attrappe" or strukturierer.name == "attrappe":
        print("WARNUNG: Mindestens ein Anbieter ist die Attrappe "
              f"(Transkription: {transkribierer.name}, "
              f"Strukturierung: {strukturierer.name}).\n"
              "         Der Lauf prueft dann nur, ob die Kette technisch "
              "durchlaeuft - nicht die Erkennungsqualitaet.\n"
              "         Fuer eine belastbare Messung Schluessel in .env setzen "
              "(siehe docs/DECISIONS.md · D-09).\n", file=sys.stderr)

    kontext = Kontext(
        heute=date.fromisoformat(argumente.heute) if argumente.heute else date.today(),
        gewerke=stammdaten.gewerke, einheiten=einheiten_codes(),
        bauvorhaben=stammdaten.bauvorhaben,
        regelbeginn=uhrzeit.fromisoformat(argumente.regelbeginn))
    vokabular = vokabular_zusammenstellen(
        stammdaten.gewerke, stammdaten.mitarbeiter, einheiten_codes())

    messungen = []
    for muster in argumente.aufnahmen:
        pfad = Path(muster)
        if not pfad.exists():
            print(f"Nicht gefunden: {pfad}", file=sys.stderr)
            continue
        print(f"  {pfad.name} …", file=sys.stderr, flush=True)
        messungen.append(messen(pfad, kontext, vokabular, transkribierer, strukturierer))

    if not messungen:
        print("Keine Aufnahmen verarbeitet.", file=sys.stderr)
        return 1

    ziel = Path(argumente.bericht)
    bericht_schreiben(messungen, ziel, transkribierer=transkribierer.name,
                      strukturierer=strukturierer.name, kontext=kontext)

    gescheitert = sum(1 for m in messungen if m.fehler)
    print(f"\n{len(messungen)} Aufnahmen, {gescheitert} fehlgeschlagen")
    print(f"Bericht: {ziel}")
    return 1 if gescheitert == len(messungen) else 0


if __name__ == "__main__":
    raise SystemExit(main())
