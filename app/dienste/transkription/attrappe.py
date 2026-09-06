"""Transkribierer fuer Tests und Entwicklung ohne Netz, Schluessel und Kosten.

Kein Wegwerfcode: Erst diese Attrappe macht die gesamte Testsuite offline
lauffaehig - und sie ist der Anbieter, mit dem die App startet, solange D-09
(Auftragsverarbeitung) nicht geklaert ist.
"""
from __future__ import annotations

import hashlib

from app.dienste.transkription.basis import Transkript, TranskriptionsFehler

# Feste Antworten fuer wiederholbare Tests, angesprochen ueber den Audio-Hash.
VORGABEN: dict[str, str] = {}

STANDARDTEXT = (
    "Heute waren wir auf der Baustelle in der Musterstraße 12. "
    "Wir haben die Wände im Wohnzimmer gespachtelt und anschließend geschliffen."
)


class AttrappenTranskribierer:
    name = "attrappe"

    def __init__(self, antwort: str | None = None):
        self._antwort = antwort

    def transkribiere(self, audio: bytes, mime_typ: str,
                      vokabular: tuple[str, ...] = ()) -> Transkript:
        if not audio:
            raise TranskriptionsFehler(
                "Die Aufnahme ist leer. Bitte noch einmal aufnehmen.")

        if self._antwort is not None:
            text = self._antwort
        else:
            text = VORGABEN.get(hashlib.sha256(audio).hexdigest(), STANDARDTEXT)

        return Transkript(text=text, dauer_sekunden=len(audio) / 16000,
                          anbieter=self.name)
