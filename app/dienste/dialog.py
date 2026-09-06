"""Der Rueckfragedialog (EPIC 05).

Haelt zusammen, was Strukturierung und Vollstaendigkeitspruefung liefern, und
begrenzt den Ablauf auf hoechstens zwei Runden (D-12).

    Aufnahme -> Entwurf -> Luecken? -- nein --> bestaetigen
                              |
                             ja
                              v
                    eine gebuendelte Frage
                              |
                     Antwort (Sprache oder Text)
                              |
                              v
                    Luecken? -- nein --> bestaetigen
                              |
                             ja, Runde 2 erreicht
                              v
             manuelles Formular mit markierten Luecken

Wichtig ist der letzte Zweig: Der Mitarbeiter wird nie in einer Schleife
festgehalten. Nach zwei Runden bekommt er den Entwurf mit den offenen Stellen
und traegt sie von Hand ein.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.dienste.leistungstext import menge_deutsch
from app.dienste.strukturierung.basis import (
    Entwurf, Kontext, Strukturierer, StrukturierungsFehler,
)
from app.dienste.strukturierung.normalisierung import normalisieren
from app.dienste.vollstaendigkeit import (
    RUNDEN_MAX, Luecke, Pruefergebnis, antwort_einarbeiten, luecken_finden,
    rueckfrage_formulieren,
)


@dataclass
class Dialogstand:
    entwurf: Entwurf
    runde: int = 0
    luecken: list[Luecke] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    rueckfrage: str | None = None

    @property
    def vollstaendig(self) -> bool:
        return not self.luecken

    @property
    def weitere_runde_moeglich(self) -> bool:
        return bool(self.luecken) and self.runde < RUNDEN_MAX

    @property
    def manuell_ergaenzen(self) -> bool:
        """Der Dialog ist ausgereizt, es fehlt aber noch etwas."""
        return bool(self.luecken) and self.runde >= RUNDEN_MAX

    def zusammenfassung(self) -> str:
        """Was dem Mitarbeiter zur Bestaetigung angezeigt wird (Briefing §12)."""
        zeilen = [f"{self.entwurf.datum:%d.%m.%Y}"]
        if self.entwurf.gewerk:
            zeilen.append(self.entwurf.gewerk)
        if self.entwurf.beginn and self.entwurf.ende:
            zeilen.append(f"{self.entwurf.beginn:%H:%M} bis "
                          f"{self.entwurf.ende:%H:%M}")
        zeilen.append("")
        for position in self.entwurf.leistungen:
            menge = ""
            if position.menge is not None:
                menge = (f"  {menge_deutsch(position.menge)} "
                         f"{position.einheit or '?'}")
            zeilen.append(f"{position.taetigkeit}{menge}")
        if self.entwurf.bemerkung:
            zeilen += ["", f"Bemerkung: {self.entwurf.bemerkung}"]
        return "\n".join(zeilen)


def _stand_bilden(entwurf: Entwurf, kontext: Kontext, runde: int) -> Dialogstand:
    ergebnis: Pruefergebnis = luecken_finden(entwurf, kontext)
    stand = Dialogstand(entwurf=entwurf, runde=runde, luecken=ergebnis.luecken,
                        hinweise=ergebnis.hinweise)
    if stand.weitere_runde_moeglich:
        stand.rueckfrage = rueckfrage_formulieren(ergebnis, entwurf, kontext)
    return stand


def starten(transkript: str, kontext: Kontext,
            strukturierer: Strukturierer) -> Dialogstand:
    """Erste Aufnahme auswerten."""
    entwurf = normalisieren(
        strukturierer.strukturiere(transkript, kontext), kontext, transkript)
    return _stand_bilden(entwurf, kontext, runde=0)


def fortsetzen(stand: Dialogstand, antwort_transkript: str, kontext: Kontext,
               strukturierer: Strukturierer) -> Dialogstand:
    """Antwort auf die Rueckfrage einarbeiten.

    Schlaegt die Auswertung der Antwort fehl, geht der bisherige Entwurf
    **nicht** verloren: Der Stand wird unveraendert mit einem Hinweis
    zurueckgegeben. Eine misslungene zweite Aufnahme darf nicht die erste
    entwerten (Briefing §28).
    """
    if not stand.weitere_runde_moeglich:
        return stand

    ergebnis = Pruefergebnis(luecken=stand.luecken, hinweise=stand.hinweise)

    try:
        antwort = normalisieren(
            strukturierer.strukturiere(antwort_transkript, kontext),
            kontext, antwort_transkript)
    except StrukturierungsFehler:
        naechster = _stand_bilden(stand.entwurf, kontext, runde=stand.runde + 1)
        naechster.hinweise.append(
            "Die Antwort konnte nicht ausgewertet werden. Die offenen Angaben "
            "bitte von Hand ergaenzen.")
        return naechster

    antwort_einarbeiten(stand.entwurf, antwort, ergebnis)
    return _stand_bilden(stand.entwurf, kontext, runde=stand.runde + 1)
