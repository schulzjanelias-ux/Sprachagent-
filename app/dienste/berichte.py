"""Werteobjekte fuer einen Tagesbericht.

Bewusst ohne Datenbankbezug: Der Excel-Befueller haengt an diesen Typen, nicht
an SQLAlchemy. Damit ist die Excel-Seite unabhaengig vom Datenmodell testbar
und bleibt es auch, wenn die Persistenz spaeter waechst.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True)
class Leistung:
    """Eine Leistungsposition (Briefing §6).

    `menge` und `einheit` duerfen fehlen - die Mappe hat dafuer ohnehin kein
    Ziel (D-02). Die App erzwingt Vollstaendigkeit im Dialog, nicht hier.
    """

    taetigkeit: str
    beschreibung: str | None = None
    menge: Decimal | None = None
    einheit: str | None = None
    geschaetzt: bool = False


@dataclass(frozen=True)
class Zeitfenster:
    """Ein Gewerk mit Arbeitsanfang und -ende.

    Entspricht genau **einer** Zeile im Blatt 'Zeiterfassung'. Wer vormittags
    Trockenbau und nachmittags Maler macht, hat zwei Zeitfenster und belegt
    zwei Slots - so rechnet 'Eigenleistung' je Gewerk richtig.
    """

    gewerk: str
    beginn: time
    ende: time


@dataclass(frozen=True)
class Tagesbericht:
    """Was ein Mitarbeiter fuer einen Tag gemeldet und bestaetigt hat."""

    bericht_id: str
    datum: date
    mitarbeiter: str                       # excel_name aus MitarbeiterListe
    zeitfenster: tuple[Zeitfenster, ...] = ()
    leistungen: tuple[Leistung, ...] = ()
    bemerkung: str | None = None

    @property
    def benoetigte_slots(self) -> int:
        return len(self.zeitfenster)
