"""Normalisierung gesprochener Einheiten auf die zentrale Liste (D-07).

Laeuft deterministisch im Code, nicht im Sprachmodell. Zwei Gruende: Es ist
ohne API-Aufruf testbar (Briefing §21), und ein Modell kann hier nichts
erfinden - was nicht in der Liste steht, wird zur Rueckfrage, nicht zur
Vermutung (Briefing §8).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import einstellungen


@dataclass(frozen=True)
class Einheit:
    code: str
    bezeichnung: str
    synonyme: tuple[str, ...]


def _schluessel(text: str) -> str:
    """Vergleichsform: klein, ohne Satzzeichen, ohne Mehrfachleerzeichen.

    Umlaute bleiben erhalten - 'Stück' und 'Stueck' werden ueber die
    Synonymliste zusammengefuehrt, nicht ueber eine Entfaltung, die auch
    'm²' zu 'm2' machen wuerde.
    """
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = "".join(z for z in text if not unicodedata.category(z).startswith("P")
                   or z in "^")
    return " ".join(text.split())


@lru_cache
def einheiten_laden(pfad: Path | None = None) -> tuple[Einheit, ...]:
    quelle = pfad or einstellungen().konfiguration_verzeichnis / "einheiten.yaml"
    daten = yaml.safe_load(quelle.read_text(encoding="utf-8"))
    return tuple(
        Einheit(code=e["code"], bezeichnung=e["bezeichnung"],
                synonyme=tuple(e.get("synonyme", [])))
        for e in daten["einheiten"]
    )


@lru_cache
def _nachschlagetabelle(pfad: Path | None = None) -> dict[str, str]:
    tabelle: dict[str, str] = {}
    for einheit in einheiten_laden(pfad):
        tabelle[_schluessel(einheit.code)] = einheit.code
        tabelle[_schluessel(einheit.bezeichnung)] = einheit.code
        for synonym in einheit.synonyme:
            tabelle[_schluessel(synonym)] = einheit.code
    return tabelle


def normalisieren(wortlaut: str | None, pfad: Path | None = None) -> str | None:
    """Gesprochene Einheit -> Code aus der Liste, oder None.

        "Quadratmeter" -> "m²"        "qm" -> "m²"        "Stck." -> "Stück"
        "Kisten"       -> None        (wird zur Rueckfrage, nicht geraten)
    """
    if not wortlaut or not wortlaut.strip():
        return None
    return _nachschlagetabelle(pfad).get(_schluessel(wortlaut))


def codes(pfad: Path | None = None) -> tuple[str, ...]:
    """Alle zulaessigen Codes - fuer Schema und Prompt des Sprachmodells."""
    return tuple(e.code for e in einheiten_laden(pfad))
