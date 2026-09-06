"""Auswahl des Transkriptionsanbieters ueber die Konfiguration (D-09)."""
from __future__ import annotations

from app.config import Einstellungen, einstellungen
from app.dienste.transkription.attrappe import AttrappenTranskribierer
from app.dienste.transkription.basis import (
    AUDIO_TYPEN, Transkribierer, TranskriptionsFehler, Transkript,
)

__all__ = ["AUDIO_TYPEN", "Transkribierer", "Transkript", "TranskriptionsFehler",
           "transkribierer_erzeugen", "vokabular_zusammenstellen"]


def transkribierer_erzeugen(konfiguration: Einstellungen | None = None) -> Transkribierer:
    konfiguration = konfiguration or einstellungen()
    anbieter = konfiguration.transkription_anbieter.strip().lower()

    if anbieter == "attrappe":
        return AttrappenTranskribierer()

    if anbieter == "whisper_api":
        from app.dienste.transkription.whisper_api import WhisperApiTranskribierer
        return WhisperApiTranskribierer(
            api_schluessel=konfiguration.transkription_api_schluessel,
            basis_url=konfiguration.transkription_basis_url)

    if anbieter == "faster_whisper":
        from app.dienste.transkription.faster_whisper import FasterWhisperTranskribierer
        return FasterWhisperTranskribierer()

    raise TranskriptionsFehler(
        f"Unbekannter Transkriptionsanbieter {konfiguration.transkription_anbieter!r}. "
        "Zulaessig sind: attrappe, whisper_api, faster_whisper.")


def vokabular_zusammenstellen(gewerke: tuple[str, ...] = (),
                              mitarbeiter: tuple[str, ...] = (),
                              einheiten: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Begriffe, die auf der Baustelle vorkommen - verbessert die Erkennung.

    Kostet nichts und wirkt genau dort, wo Standardmodelle schwach sind:
    Gewerkenamen, Nachnamen und Einheiten.
    """
    return tuple(dict.fromkeys(
        begriff for gruppe in (gewerke, mitarbeiter, einheiten)
        for begriff in gruppe if begriff
    ))
