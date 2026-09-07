"""Einstellungen aus der Umgebung beziehungsweise aus .env.

Grundsatz aus dem Briefing (§16, §20): keine Geheimnisse im Code. Alles, was
je nach Umgebung anders ist, kommt aus Umgebungsvariablen.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJEKTWURZEL = Path(__file__).resolve().parents[1]

# Erkennbar unsicherer Vorgabewert. Steht dieser Wert in Produktion noch drin,
# waeren alle Sitzungscookies faelschbar - deshalb wird er beim Start geprueft.
UNSICHERER_SCHLUESSEL = "bitte-ersetzen-nicht-in-produktion-verwenden"


class Einstellungen(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJEKTWURZEL / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Betrieb ---------------------------------------------------------
    sitzung_schluessel: str = UNSICHERER_SCHLUESSEL
    https_aktiv: bool = True
    sitzung_tage: int = 30

    # --- Pfade -----------------------------------------------------------
    datenbank_pfad: Path = Path("daten/tagesberichte.db")
    konfiguration_verzeichnis: Path = Path("konfiguration")
    export_verzeichnis: Path = Path("export")

    # --- Anbieter (D-09) -------------------------------------------------
    transkription_anbieter: str = "attrappe"
    transkription_api_schluessel: str = ""
    transkription_basis_url: str = ""
    strukturierung_anbieter: str = "attrappe"
    anthropic_api_key: str = ""

    # --- Grenzwerte ------------------------------------------------------
    audio_groesse_max_mb: int = 25
    # 180 statt der urspruenglich angesetzten 90 Sekunden. Vier echte
    # WhatsApp-Sprachnachrichten aus dem Betrieb dauerten 48, 67, 76 und
    # 82 Sekunden - die laengste lag acht Sekunden unter der alten Grenze.
    # Wer etwas ausfuehrlicher spricht, waere mitten im Satz abgeschnitten
    # worden. Bei 19,5 kbit/s Opus sind 180 Sekunden rund 440 KB.
    aufnahme_sekunden_max: int = 180
    passwort_laenge_min: int = 10          # D-11

    protokoll_stufe: str = "INFO"

    @field_validator("datenbank_pfad", "konfiguration_verzeichnis", "export_verzeichnis")
    @classmethod
    def _absolut_machen(cls, wert: Path) -> Path:
        return wert if wert.is_absolute() else PROJEKTWURZEL / wert

    @property
    def schluessel_ist_unsicher(self) -> bool:
        return self.sitzung_schluessel == UNSICHERER_SCHLUESSEL

    def warnungen(self) -> list[str]:
        """Betriebsrisiken, die beim Start sichtbar werden muessen.

        Nicht als Ausnahme: Fuer lokale Entwicklung sind beide Zustaende in
        Ordnung. In Produktion sind sie es nicht - deshalb laut ins Protokoll.
        """
        offen = []
        if self.schluessel_ist_unsicher:
            offen.append(
                "SITZUNG_SCHLUESSEL steht auf dem Vorgabewert. Sitzungscookies "
                "sind damit faelschbar. In Produktion zwingend ersetzen."
            )
        if not self.https_aktiv:
            offen.append(
                "HTTPS_AKTIV=false. Das Session-Cookie wird ohne Secure-Flag "
                "gesetzt und Browser geben das Mikrofon nicht frei (D-10). "
                "Nur fuer lokale Entwicklung zulaessig."
            )
        return offen


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()


def protokollierung_einrichten(stufe: str = "INFO") -> None:
    """Protokolle nach stdout, ohne personenbezogene Inhalte (§20)."""
    logging.basicConfig(
        level=getattr(logging, stufe.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s · %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    # Zugriffsprotokoll von uvicorn ist bei einem Dienst hinter Proxy redundant
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
