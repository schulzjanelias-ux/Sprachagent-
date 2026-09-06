"""Vollstaendigkeitspruefung und gebuendelte Rueckfrage (EPIC 05, D-12).

Das Briefing zeigt in §3 genau das gewuenschte Verhalten: "Die App fragt NICHT
zehn Dinge ab. Sie fragt gezielt." Fehlen Menge und Einheit zu zwei
Positionen, entsteht **eine** Frage, nicht vier.

Der Grund ist keine Bequemlichkeit: Ein Dialog, der laenger dauert als das
Formular, das er ersetzen soll, hat sein Ziel verfehlt (Briefing §28 - ein
brauchbarer Bericht in ein bis zwei Minuten).

Nach hoechstens zwei Runden endet der Dialog. Was dann noch fehlt, wird
markiert und von Hand ergaenzt - der Mitarbeiter wird nicht in einer Schleife
festgehalten.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from app.dienste.leistungstext import menge_deutsch
from app.dienste.strukturierung.basis import Entwurf, EntwurfLeistung, Kontext

RUNDEN_MAX = 2


class Lueckenart(str, enum.Enum):
    gewerk = "gewerk"
    leistung = "leistung"
    menge = "menge"
    einheit = "einheit"
    zeit = "zeit"


@dataclass(frozen=True)
class Luecke:
    art: Lueckenart
    beschreibung: str                       # fuer die manuelle Nachbearbeitung
    position_index: int | None = None       # welche Leistungsposition betroffen ist


@dataclass
class Pruefergebnis:
    luecken: list[Luecke] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    @property
    def vollstaendig(self) -> bool:
        return not self.luecken

    def je_art(self, art: Lueckenart) -> list[Luecke]:
        return [l for l in self.luecken if l.art == art]


def luecken_finden(entwurf: Entwurf, kontext: Kontext) -> Pruefergebnis:
    """Prueft gegen die Pflichtdaten aus Briefing §5 und D-03.

    Datum, Mitarbeiter und Bauvorhaben fehlen hier bewusst: Das Datum kommt
    aus dem Erfassungstag, der Mitarbeiter aus der Anmeldung, das Bauvorhaben
    aus der Projektwahl. Keines davon kann der Mitarbeiter vergessen.
    """
    ergebnis = Pruefergebnis()

    if not entwurf.gewerk:
        ergebnis.luecken.append(Luecke(
            Lueckenart.gewerk, "Das Gewerk ist nicht zugeordnet."))

    if not entwurf.leistungen:
        ergebnis.luecken.append(Luecke(
            Lueckenart.leistung, "Es ist keine Leistung erfasst."))

    for index, position in enumerate(entwurf.leistungen):
        if position.menge is None:
            ergebnis.luecken.append(Luecke(
                Lueckenart.menge,
                f"Bei {position.taetigkeit} fehlt die Menge.", index))
        elif position.einheit is None:
            # Einheit nur nachfragen, wenn es auch eine Menge gibt - eine
            # Einheit ohne Menge ist wertlos.
            ergebnis.luecken.append(Luecke(
                Lueckenart.einheit,
                f"Bei {position.taetigkeit} fehlt die Einheit.", index))

    if entwurf.beginn is None or entwurf.ende is None:
        ergebnis.luecken.append(Luecke(
            Lueckenart.zeit, "Arbeitsanfang und -ende fehlen."))

    # Hinweise sind keine Luecken: Sie blockieren die Bestaetigung nicht,
    # werden dem Mitarbeiter aber angezeigt (Briefing §8).
    if entwurf.datum_abgeleitet:
        ergebnis.hinweise.append(
            f"Als Datum ist der {entwurf.datum:%d.%m.%Y} eingetragen.")
    if entwurf.zeit_abgeleitet:
        ergebnis.hinweise.append(
            f"Die Arbeitszeit wurde aus einer Dauer errechnet: "
            f"{entwurf.beginn:%H:%M} bis {entwurf.ende:%H:%M}.")
    for position in entwurf.leistungen:
        if position.geschaetzt:
            ergebnis.hinweise.append(
                f"{position.taetigkeit}: die Menge ist geschätzt.")
        if position.konfidenz < 0.5:
            ergebnis.hinweise.append(
                f"{position.taetigkeit}: nur unsicher erkannt.")

    return ergebnis


def rueckfrage_formulieren(ergebnis: Pruefergebnis, entwurf: Entwurf,
                           kontext: Kontext) -> str | None:
    """Alle Luecken zu **einer** deutschen Frage buendeln (D-12).

    Beispiel aus Briefing §3:
        "Wie viel habt ihr bei Spachtelarbeiten und bei Schleifarbeiten
         geschafft?"
    """
    if ergebnis.vollstaendig:
        return None

    saetze: list[str] = []

    if ergebnis.je_art(Lueckenart.leistung):
        return "Was habt ihr heute gemacht, und wie viel davon?"

    if ergebnis.je_art(Lueckenart.gewerk):
        auswahl = _gewerk_vorschlagen(entwurf, kontext)
        saetze.append(f"Welches Gewerk war das{auswahl}?")

    if mengen := ergebnis.je_art(Lueckenart.menge):
        namen = [entwurf.leistungen[l.position_index].taetigkeit
                 for l in mengen if l.position_index is not None]
        saetze.append(f"Wie viel habt ihr bei {_aufzaehlen(namen)} geschafft?")

    if einheiten := ergebnis.je_art(Lueckenart.einheit):
        saetze.append(_einheitenfrage(einheiten, entwurf, kontext))

    if ergebnis.je_art(Lueckenart.zeit):
        saetze.append("Von wann bis wann habt ihr gearbeitet?")

    return " ".join(s for s in saetze if s)


def _gewerk_vorschlagen(entwurf: Entwurf, kontext: Kontext) -> str:
    """Bei Mehrdeutigkeit eine Auswahl anbieten statt raten (Briefing §8)."""
    if not entwurf.leistungen or len(kontext.gewerke) > 4:
        return ""
    return f" – {_aufzaehlen(list(kontext.gewerke), verbinder='oder')}"


def _einheitenfrage(luecken: list[Luecke], entwurf: Entwurf,
                    kontext: Kontext) -> str:
    """Nennt die Menge mit, damit die Frage ohne Rueckblick verstaendlich ist."""
    teile = []
    for luecke in luecken:
        if luecke.position_index is None:
            continue
        position = entwurf.leistungen[luecke.position_index]
        menge = _menge_deutsch(position)
        teile.append(f"{menge} was bei {position.taetigkeit}")

    if not teile:
        return ""
    beispiele = ", ".join(kontext.einheiten[:3])
    return f"{_aufzaehlen(teile)} – {beispiele} oder etwas anderes?"


def _menge_deutsch(position: EntwurfLeistung) -> str:
    # Nutzt bewusst dieselbe Formatierung wie der Export nach Spalte I.
    # Eine eigene Fassung hier hatte aus 40 eine 4 gemacht, weil ein
    # rstrip("0") auch die Null ganzer Zahlen frisst.
    return "Wie viel" if position.menge is None else menge_deutsch(position.menge)


def _aufzaehlen(begriffe: list[str], verbinder: str = "und") -> str:
    """a - a und b - a, b und c: deutsche Aufzaehlung."""
    eindeutig = list(dict.fromkeys(b for b in begriffe if b))
    if not eindeutig:
        return ""
    if len(eindeutig) == 1:
        return eindeutig[0]
    return f"{', '.join(eindeutig[:-1])} {verbinder} {eindeutig[-1]}"


def antwort_einarbeiten(entwurf: Entwurf, antwort: Entwurf,
                        ergebnis: Pruefergebnis) -> Entwurf:
    """Die Antwort auf die Rueckfrage in den Entwurf uebernehmen.

    Grundsatz: **Nur Luecken fuellen, nie Bestaetigtes ueberschreiben.** Was
    der Mitarbeiter in der ersten Aufnahme klar gesagt hat, bleibt stehen -
    sonst kann eine unglueckliche zweite Aufnahme eine richtige Angabe
    verdraengen.
    """
    if entwurf.gewerk is None and antwort.gewerk:
        entwurf.gewerk = antwort.gewerk

    if entwurf.beginn is None and antwort.beginn:
        entwurf.beginn = antwort.beginn
        entwurf.ende = antwort.ende
        entwurf.zeit_abgeleitet = antwort.zeit_abgeleitet

    _mengen_zuordnen(entwurf, antwort, ergebnis)

    if not entwurf.leistungen and antwort.leistungen:
        entwurf.leistungen = list(antwort.leistungen)

    if not entwurf.bemerkung and antwort.bemerkung:
        entwurf.bemerkung = antwort.bemerkung

    entwurf.unklarheiten = [u for u in entwurf.unklarheiten
                            if u not in antwort.unklarheiten]
    entwurf.unklarheiten += [u for u in antwort.unklarheiten
                             if u not in entwurf.unklarheiten]
    return entwurf


def _mengen_zuordnen(entwurf: Entwurf, antwort: Entwurf,
                     ergebnis: Pruefergebnis) -> None:
    """Mengen aus der Antwort den offenen Positionen zuordnen.

    Zuerst ueber den Namen der Taetigkeit - das ist eindeutig. Nur wenn das
    nicht traegt und die Anzahl genau passt, wird der Reihe nach zugeordnet.
    Bleibt es mehrdeutig, wird nichts geraten: Die Luecke bleibt offen und
    landet im manuellen Formular (Briefing §8).
    """
    offen = [l.position_index for l in ergebnis.je_art(Lueckenart.menge)
             if l.position_index is not None]
    offen += [l.position_index for l in ergebnis.je_art(Lueckenart.einheit)
              if l.position_index is not None]
    offen = list(dict.fromkeys(offen))
    if not offen:
        return

    verwendet: set[int] = set()

    # 1. Zuordnung ueber den Namen
    for index in list(offen):
        ziel = entwurf.leistungen[index]
        for nummer, gegeben in enumerate(antwort.leistungen):
            if nummer in verwendet or gegeben.menge is None:
                continue
            if _namen_passen(ziel.taetigkeit, gegeben.taetigkeit):
                _uebernehmen(ziel, gegeben)
                verwendet.add(nummer)
                offen.remove(index)
                break

    # 2. Der Reihe nach - nur wenn die Anzahl genau aufgeht
    uebrig = [n for n, g in enumerate(antwort.leistungen)
              if n not in verwendet and g.menge is not None]
    if offen and len(uebrig) == len(offen):
        for index, nummer in zip(offen, uebrig):
            _uebernehmen(entwurf.leistungen[index], antwort.leistungen[nummer])


def _uebernehmen(ziel: EntwurfLeistung, quelle: EntwurfLeistung) -> None:
    if ziel.menge is None:
        ziel.menge = quelle.menge
        ziel.geschaetzt = quelle.geschaetzt
    if ziel.einheit is None:
        ziel.einheit = quelle.einheit
        ziel.einheit_wortlaut = quelle.einheit_wortlaut


def _namen_passen(einer: str, anderer: str) -> bool:
    """Grober Wortvergleich: Spachtelarbeiten trifft gespachtelt."""
    a, b = einer.lower().strip(), anderer.lower().strip()
    if a == b:
        return True
    stamm_a, stamm_b = _wortstamm(a), _wortstamm(b)
    return bool(stamm_a) and bool(stamm_b) and (
        stamm_a in stamm_b or stamm_b in stamm_a)


def _wortstamm(wort: str) -> str:
    for vorsilbe in ("ge",):
        if wort.startswith(vorsilbe):
            wort = wort[len(vorsilbe):]
    for endung in ("arbeiten", "ungen", "ung", "eten", "et", "en", "t", "e"):
        if wort.endswith(endung) and len(wort) - len(endung) >= 4:
            return wort[: -len(endung)]
    return wort
