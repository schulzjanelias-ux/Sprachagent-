"""Auswahl des Strukturierers ueber die Konfiguration."""
from __future__ import annotations

from app.config import Einstellungen, einstellungen
from app.dienste.strukturierung.attrappe import AttrappenStrukturierer
from app.dienste.strukturierung.basis import (
    Entwurf, EntwurfLeistung, Kontext, Rohentwurf, StrukturierungsFehler, Strukturierer,
)
from app.dienste.strukturierung.normalisierung import normalisieren

__all__ = ["Entwurf", "EntwurfLeistung", "Kontext", "Rohentwurf", "Strukturierer",
           "StrukturierungsFehler", "normalisieren", "strukturierer_erzeugen",
           "entwurf_erzeugen"]


def strukturierer_erzeugen(konfiguration: Einstellungen | None = None) -> Strukturierer:
    konfiguration = konfiguration or einstellungen()
    anbieter = konfiguration.strukturierung_anbieter.strip().lower()

    if anbieter == "attrappe":
        return AttrappenStrukturierer()
    if anbieter == "claude":
        from app.dienste.strukturierung.claude import ClaudeStrukturierer
        return ClaudeStrukturierer(api_schluessel=konfiguration.anthropic_api_key)

    raise StrukturierungsFehler(
        f"Unbekannter Strukturierungsanbieter {konfiguration.strukturierung_anbieter!r}. "
        "Zulaessig sind: attrappe, claude.")


def entwurf_erzeugen(transkript: str, kontext: Kontext,
                     strukturierer: Strukturierer | None = None) -> Entwurf:
    """Transkript -> geprueften Entwurf. Der uebliche Einstiegspunkt."""
    werkzeug = strukturierer or strukturierer_erzeugen()
    return normalisieren(werkzeug.strukturiere(transkript, kontext), kontext, transkript)
