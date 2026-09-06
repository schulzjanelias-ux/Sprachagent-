"""Datenbankanbindung (SQLite).

Zwei Einstellungen, die SQLite nicht von selbst mitbringt und die beide
stillschweigend Schaden anrichten, wenn sie fehlen:

- **Fremdschluessel** werden ohne `PRAGMA foreign_keys=ON` nicht geprueft.
  Eine Position koennte dann auf einen geloeschten Bericht zeigen, ohne dass
  es auffaellt.
- **WAL** erlaubt Lesen waehrend geschrieben wird. Ohne WAL blockiert ein
  Exportlauf jede Erfassung - auf der Baustelle heisst das, dass jemand
  seinen Feierabendbericht nicht abgeben kann.

Beides wird je Verbindung gesetzt, nicht einmalig: SQLite vergisst die
Fremdschluesseleinstellung bei jeder neuen Verbindung.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import einstellungen
from app.modelle import Basis

protokoll = logging.getLogger(__name__)

_maschine: Engine | None = None
_sitzungen: sessionmaker | None = None


def _sqlite_einstellen(verbindung, _verbindungsdaten) -> None:
    zeiger = verbindung.cursor()
    zeiger.execute("PRAGMA foreign_keys=ON")
    zeiger.execute("PRAGMA journal_mode=WAL")
    zeiger.execute("PRAGMA synchronous=NORMAL")
    zeiger.execute("PRAGMA busy_timeout=5000")
    zeiger.close()


def maschine_erzeugen(pfad: Path | None = None, echo: bool = False) -> Engine:
    ziel = pfad or einstellungen().datenbank_pfad
    if str(ziel) != ":memory:":
        Path(ziel).parent.mkdir(parents=True, exist_ok=True)

    maschine = create_engine(f"sqlite:///{ziel}", echo=echo, future=True)
    event.listen(maschine, "connect", _sqlite_einstellen)
    return maschine


def einrichten(pfad: Path | None = None) -> Engine:
    """Maschine erzeugen und fehlende Tabellen anlegen."""
    global _maschine, _sitzungen
    _maschine = maschine_erzeugen(pfad)
    Basis.metadata.create_all(_maschine)
    _sitzungen = sessionmaker(bind=_maschine, expire_on_commit=False, future=True)
    protokoll.info("Datenbank bereit: %s", pfad or einstellungen().datenbank_pfad)
    return _maschine


@contextmanager
def sitzung() -> Iterator[Session]:
    """Sitzung mit Transaktionsklammer.

    Bei einer Ausnahme wird zurueckgerollt - ein halb geschriebener Bericht
    ist schlimmer als gar keiner.
    """
    if _sitzungen is None:
        einrichten()
    with _sitzungen() as offen:                     # type: ignore[misc]
        try:
            yield offen
            offen.commit()
        except Exception:
            offen.rollback()
            raise


def sichern(ziel: Path, pfad: Path | None = None) -> Path:
    """Konsistente Sicherung im laufenden Betrieb (ARCHITECTURE §8).

    VACUUM INTO statt Dateikopie: Eine Kopie waehrend eines Schreibvorgangs
    kann einen halben Transaktionszustand enthalten.
    """
    from sqlalchemy import text

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.unlink(missing_ok=True)
    maschine = _maschine or maschine_erzeugen(pfad)
    with maschine.connect() as verbindung:
        verbindung.execute(text("VACUUM INTO :ziel"), {"ziel": str(ziel)})
    return ziel
