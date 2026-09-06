"""Transkription ueber einen Whisper-kompatiblen HTTP-Endpunkt (D-09).

Dieselbe Schnittstelle bedienen die Whisper-API und ein selbst betriebener
whisper.cpp- oder faster-whisper-Server. Der Wechsel zwischen Cloud und
eigenem Haus ist damit ein anderer Wert fuer TRANSKRIPTION_BASIS_URL - genau
die Beweglichkeit, die D-09 braucht, solange die Datenschutzfrage offen ist.
"""
from __future__ import annotations

import logging

import httpx

from app.dienste.transkription.basis import Transkript, TranskriptionsFehler

protokoll = logging.getLogger(__name__)

STANDARD_URL = "https://api.openai.com/v1"
ZEITLIMIT_SEKUNDEN = 120.0


class WhisperApiTranskribierer:
    name = "whisper_api"

    def __init__(self, api_schluessel: str, basis_url: str = "",
                 modell: str = "whisper-1", klient: httpx.Client | None = None):
        if not api_schluessel:
            raise TranskriptionsFehler(
                "Fuer den Anbieter 'whisper_api' fehlt TRANSKRIPTION_API_SCHLUESSEL.")
        self._schluessel = api_schluessel
        self._basis_url = (basis_url or STANDARD_URL).rstrip("/")
        self._modell = modell
        self._klient = klient

    def transkribiere(self, audio: bytes, mime_typ: str,
                      vokabular: tuple[str, ...] = ()) -> Transkript:
        if not audio:
            raise TranskriptionsFehler(
                "Die Aufnahme ist leer. Bitte noch einmal aufnehmen.")

        felder = {"model": self._modell, "language": "de",
                  "response_format": "verbose_json"}
        if vokabular:
            # Der Vokabular-Prompt verbessert genau die Begriffe, auf die es
            # ankommt: Gewerke, Mitarbeiternamen, Einheiten. Kostet nichts.
            felder["prompt"] = ", ".join(vokabular)[:900]

        klient = self._klient or httpx.Client(timeout=ZEITLIMIT_SEKUNDEN)
        try:
            antwort = klient.post(
                f"{self._basis_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._schluessel}"},
                files={"file": ("aufnahme", audio, mime_typ)},
                data=felder,
            )
            antwort.raise_for_status()
            daten = antwort.json()
        except httpx.TimeoutException as fehler:
            raise TranskriptionsFehler(
                "Die Spracherkennung hat zu lange gebraucht. Bitte noch einmal "
                "versuchen - die Aufnahme bleibt gespeichert.") from fehler
        except httpx.HTTPStatusError as fehler:
            # Kein Statuscode und keine Anbieterdetails an den Mitarbeiter;
            # das Protokoll traegt die Einzelheiten, ohne Transkriptinhalt (§20).
            protokoll.error("Whisper-Endpunkt antwortete mit %s",
                            fehler.response.status_code)
            raise TranskriptionsFehler(
                "Die Spracherkennung ist gerade nicht erreichbar. Der Bericht "
                "kann von Hand eingetragen werden.") from fehler
        except httpx.HTTPError as fehler:
            protokoll.error("Whisper-Endpunkt nicht erreichbar: %s", type(fehler).__name__)
            raise TranskriptionsFehler(
                "Keine Verbindung zur Spracherkennung. Die Aufnahme bleibt "
                "gespeichert und wird spaeter erneut gesendet.") from fehler
        finally:
            if self._klient is None:
                klient.close()

        text = (daten.get("text") or "").strip()
        if not text:
            raise TranskriptionsFehler(
                "Aus der Aufnahme wurde kein Text erkannt. Bitte noch einmal "
                "sprechen - moeglichst nah am Mikrofon.")

        return Transkript(text=text, sprache=daten.get("language", "de"),
                          dauer_sekunden=daten.get("duration"), anbieter=self.name)
