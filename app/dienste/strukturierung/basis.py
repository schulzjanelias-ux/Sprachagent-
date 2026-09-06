"""Schnittstelle und Datenformen fuer die Strukturierung des Transkripts.

Kernentscheidung (ARCHITECTURE §5): **Das Sprachmodell liefert Wortlaute,
keine aufgeloesten Werte.** Es gibt "gestern" zurueck, nicht ein Datum, und
"Quadratmeter", nicht "m²". Aufloesung und Normalisierung passieren
deterministisch im Code.

Zwei Gruende. Erstens ist beides damit ohne API-Aufruf testbar (Briefing §21).
Zweitens kann ein Modell hier nichts erfinden: Was nicht in der Einheitenliste
steht, wird zur Rueckfrage, nicht zur Vermutung (Briefing §8 - niemals
halluzinieren).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class StrukturierungsFehler(RuntimeError):
    """Aus dem Transkript liess sich kein Entwurf gewinnen.

    Traegt eine deutsche Meldung. Der Mitarbeiter landet danach im manuellen
    Formular mit vorausgefuelltem Transkript - nie in einer Sackgasse.
    """


# --- Was das Modell liefern muss (striktes JSON-Schema) --------------------

class RohLeistung(BaseModel):
    taetigkeit: str = Field(description="Ausgefuehrte Taetigkeit, z. B. 'Spachtelarbeiten'")
    beschreibung: str | None = Field(description="Ort oder Zusatz, z. B. 'Waende im Wohnzimmer'")
    menge_wortlaut: str | None = Field(
        description="Mengenangabe **im Wortlaut**, z. B. 'ungefaehr 45' oder '12,5'. "
                    "null, wenn keine genannt wurde. Niemals schaetzen.")
    einheit_wortlaut: str | None = Field(
        description="Einheit **im Wortlaut**, z. B. 'Quadratmeter' oder 'qm'. "
                    "null, wenn keine genannt wurde. Niemals ableiten.")
    konfidenz: float = Field(ge=0.0, le=1.0,
                             description="Wie sicher ist diese Position? 0.0 bis 1.0")


class RohArbeitszeit(BaseModel):
    beginn_wortlaut: str | None = Field(description="Arbeitsbeginn im Wortlaut, z. B. '7 Uhr'")
    ende_wortlaut: str | None = Field(description="Arbeitsende im Wortlaut, z. B. 'halb fuenf'")
    dauer_wortlaut: str | None = Field(
        description="Nur wenn eine Dauer statt Zeiten genannt wurde, z. B. 'acht Stunden'")


class Rohentwurf(BaseModel):
    datum_wortlaut: str | None = Field(
        description="Datumsangabe im Wortlaut, z. B. 'gestern' oder '14.3.'. "
                    "null, wenn keine genannt wurde - dann gilt der Erfassungstag.")
    gewerk: str | None = Field(
        description="Gewerk, **wortgleich** aus der vorgegebenen Liste. "
                    "null, wenn keine sichere Zuordnung moeglich ist.")
    leistungen: list[RohLeistung] = Field(
        description="Eine Position je genannter Taetigkeit. Mehrere Taetigkeiten "
                    "niemals zu einer zusammenfassen.")
    arbeitszeit: RohArbeitszeit
    bemerkung: str | None = Field(
        description="Besonderheiten, Behinderungen, offene Punkte. Sonst null.")
    unklarheiten: list[str] = Field(
        description="Was im Transkript unklar blieb, in ganzen deutschen Saetzen. "
                    "Hier gehoert alles hinein, was sonst geraten werden muesste.")


# --- Was der Code daraus macht --------------------------------------------

@dataclass
class EntwurfLeistung:
    taetigkeit: str
    beschreibung: str | None = None
    menge: Decimal | None = None
    einheit: str | None = None
    geschaetzt: bool = False
    konfidenz: float = 1.0
    menge_wortlaut: str | None = None
    einheit_wortlaut: str | None = None

    @property
    def einheit_unbekannt(self) -> bool:
        """Es wurde etwas gesagt, aber es passt in keine bekannte Einheit."""
        return bool(self.einheit_wortlaut) and self.einheit is None

    @property
    def menge_unklar(self) -> bool:
        return bool(self.menge_wortlaut) and self.menge is None


@dataclass
class Entwurf:
    """Vorschlag fuer einen Tagesbericht - noch nicht bestaetigt."""

    datum: date
    transkript: str
    gewerk: str | None = None
    leistungen: list[EntwurfLeistung] = field(default_factory=list)
    beginn: time | None = None
    ende: time | None = None
    bemerkung: str | None = None
    unklarheiten: list[str] = field(default_factory=list)
    datum_abgeleitet: bool = False       # kein Datum genannt, Erfassungstag gesetzt
    zeit_abgeleitet: bool = False        # aus Dauer + Regelbeginn errechnet (D-03)
    dauer_wortlaut: str | None = None


@dataclass(frozen=True)
class Kontext:
    """Was das Modell ueber den Betrieb wissen muss."""

    heute: date
    gewerke: tuple[str, ...]
    einheiten: tuple[str, ...]
    bauvorhaben: str | None = None
    regelbeginn: time | None = None      # fuer D-03, wenn nur eine Dauer genannt wird


@runtime_checkable
class Strukturierer(Protocol):
    name: str

    def strukturiere(self, transkript: str, kontext: Kontext) -> Rohentwurf:
        ...
