"""Anbieterunabhaengige Schnittstelle fuer die Spracherkennung (D-09).

Der Anbieter wird ueber .env gewaehlt. Ein Wechsel ist damit eine
Konfigurationsaenderung, keine Migration - das war die Vorgabe aus dem
Briefing (§17) und die Voraussetzung dafuer, im Zweifel auf ein lokales
Modell umzuschalten, falls der AVV nicht rechtzeitig steht.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

AUDIO_TYPEN = {
    "audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/mp3",
    "audio/wav", "audio/x-wav", "audio/m4a", "audio/x-m4a", "audio/aac",
    "audio/flac",
}


class TranskriptionsFehler(RuntimeError):
    """Die Transkription ist fehlgeschlagen.

    Traegt eine deutsche, dem Mitarbeiter zumutbare Meldung - kein Fehler
    wird stillschweigend geschluckt (Briefing §28).
    """


@dataclass(frozen=True)
class Transkript:
    text: str
    sprache: str = "de"
    dauer_sekunden: float | None = None
    anbieter: str = ""


@runtime_checkable
class Transkribierer(Protocol):
    name: str

    def transkribiere(self, audio: bytes, mime_typ: str,
                      vokabular: tuple[str, ...] = ()) -> Transkript:
        """Audio in Text. `vokabular` sind Begriffe, die im Betrieb vorkommen.

        Gewerke, Mitarbeiternamen und Einheiten als Vokabular mitzugeben,
        verbessert genau die Woerter, auf die es ankommt - und kostet nichts.
        """
        ...
