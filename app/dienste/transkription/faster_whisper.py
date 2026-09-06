"""Transkription mit einem lokalen faster-whisper-Modell (D-09).

Rueckfallebene, falls der Auftragsverarbeitungsvertrag mit einem
Cloud-Anbieter nicht rechtzeitig steht: Die Aufnahmen verlassen das Haus
nicht. Preis dafuer ist Rechenzeit - auf reiner CPU etwa das Ein- bis
Dreifache der Aufnahmedauer.

faster-whisper ist bewusst keine feste Abhaengigkeit in requirements.txt.
Wer diesen Anbieter nutzt, installiert ihn zusaetzlich:

    pip install faster-whisper
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.dienste.transkription.basis import Transkript, TranskriptionsFehler

protokoll = logging.getLogger(__name__)


class FasterWhisperTranskribierer:
    name = "faster_whisper"

    def __init__(self, modellgroesse: str = "large-v3", geraet: str = "auto",
                 modell=None):
        self._modellgroesse = modellgroesse
        self._geraet = geraet
        self._modell = modell            # einspeisbar fuer Tests

    def _modell_laden(self):
        if self._modell is not None:
            return self._modell
        try:
            from faster_whisper import WhisperModel
        except ImportError as fehler:
            raise TranskriptionsFehler(
                "Der Anbieter 'faster_whisper' ist nicht installiert. "
                "Nachinstallieren mit: pip install faster-whisper"
            ) from fehler

        protokoll.info("Lade lokales Sprachmodell %s", self._modellgroesse)
        self._modell = WhisperModel(self._modellgroesse, device=self._geraet,
                                    compute_type="int8")
        return self._modell

    def transkribiere(self, audio: bytes, mime_typ: str,
                      vokabular: tuple[str, ...] = ()) -> Transkript:
        if not audio:
            raise TranskriptionsFehler(
                "Die Aufnahme ist leer. Bitte noch einmal aufnehmen.")

        modell = self._modell_laden()
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as datei:
            datei.write(audio)
            pfad = Path(datei.name)
        try:
            abschnitte, information = modell.transcribe(
                str(pfad), language="de",
                initial_prompt=", ".join(vokabular)[:900] if vokabular else None,
            )
            text = " ".join(a.text.strip() for a in abschnitte).strip()
        except Exception as fehler:                       # noqa: BLE001
            protokoll.error("Lokale Transkription fehlgeschlagen: %s",
                            type(fehler).__name__)
            raise TranskriptionsFehler(
                "Die Spracherkennung ist fehlgeschlagen. Der Bericht kann von "
                "Hand eingetragen werden.") from fehler
        finally:
            pfad.unlink(missing_ok=True)

        if not text:
            raise TranskriptionsFehler(
                "Aus der Aufnahme wurde kein Text erkannt. Bitte noch einmal "
                "sprechen - moeglichst nah am Mikrofon.")

        return Transkript(text=text, dauer_sekunden=getattr(information, "duration", None),
                          anbieter=self.name)
