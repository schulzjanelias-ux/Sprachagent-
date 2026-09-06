"""Datenbanktabellen (EPIC 07).

Namensgebung: Die Klassen hier sind die **gespeicherten** Zeilen. Die
Werteobjekte in app/dienste/berichte.py (Tagesbericht, Zeitfenster, Leistung)
sind das, womit der Excel-Befueller arbeitet. Die Trennung ist Absicht - der
Export haengt nicht an SQLAlchemy, und das Datenmodell darf sich aendern, ohne
den Excel-Weg anzufassen.

Zwei Punkte, die auf SQLite besondere Behandlung brauchen:

- Mengen sind abrechnungsnah und muessen exakt bleiben. SQLite kennt kein
  Decimal; SQLAlchemys Numeric weicht dort auf float aus und verliert
  Nachkommastellen. Deshalb DezimalAlsText.
- Fremdschluessel werden von SQLite nur geprueft, wenn man es je Verbindung
  einschaltet. Siehe app/datenbank.py.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Integer,
    String, Text, Time, TypeDecorator, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Basis(DeclarativeBase):
    pass


class DezimalAlsText(TypeDecorator):
    """Decimal verlustfrei in SQLite ablegen.

    Als Text gespeichert, weil jede Fliesskommadarstellung 12,5 oder 0,1
    verfaelschen kann - bei Werten, nach denen abgerechnet wird, ist das
    nicht hinnehmbar.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, wert, dialekt):
        return None if wert is None else str(Decimal(str(wert)))

    def process_result_value(self, wert, dialekt):
        return None if wert is None else Decimal(wert)


class Rolle(str, enum.Enum):
    mitarbeiter = "mitarbeiter"
    bauleiter = "bauleiter"


class Berichtsstatus(str, enum.Enum):
    entwurf = "entwurf"
    rueckfrage = "rueckfrage"
    bestaetigt = "bestaetigt"
    storniert = "storniert"


class Zeitquelle(str, enum.Enum):
    gesprochen = "gesprochen"       # der Mitarbeiter hat Anfang und Ende genannt
    abgeleitet = "abgeleitet"       # aus einer Dauer plus Regelbeginn (D-03)
    korrigiert = "korrigiert"       # im Bestaetigungsdialog von Hand geaendert


class Sprecher(str, enum.Enum):
    mitarbeiter = "mitarbeiter"
    system = "system"


class Mitarbeiter(Basis):
    __tablename__ = "mitarbeiter"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Der Anmeldename ist bewusst nicht der excel_name: Aus einem erratenen
    # Anmeldenamen soll nicht der Klarname folgen (D-11).
    anmeldename: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    anzeigename: Mapped[str] = mapped_column(String(120))
    # Muss wortgleich in MitarbeiterListe der Mappe stehen, sonst faellt der
    # Eintrag dort lautlos aus der Auswertung (D-05).
    excel_name: Mapped[str] = mapped_column(String(120))
    passwort_hash: Mapped[str] = mapped_column(String(255))
    passwort_wechseln: Mapped[bool] = mapped_column(Boolean, default=False)
    # Wird bei jedem Passwortwechsel neu gesetzt. Damit werden alle noch
    # laufenden Sitzungen ungueltig - wer ein Passwort aendert, weil es
    # kompromittiert war, will genau das.
    sitzungs_kennung: Mapped[str] = mapped_column(String(32), default="")
    rolle: Mapped[Rolle] = mapped_column(Enum(Rolle), default=Rolle.mitarbeiter)
    regelbeginn: Mapped[time | None] = mapped_column(Time, default=None)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    berichte: Mapped[list[Bericht]] = relationship(back_populates="mitarbeiter")


class Projekt(Basis):
    __tablename__ = "projekte"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Muss mit Projektübersicht!B9 der Mappe uebereinstimmen (D-04).
    name: Mapped[str] = mapped_column(String(200), unique=True)
    mappe_pfad: Mapped[str] = mapped_column(String(500))
    baubeginn: Mapped[date | None] = mapped_column(Date, default=None)
    bauende: Mapped[date | None] = mapped_column(Date, default=None)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True)

    berichte: Mapped[list[Bericht]] = relationship(back_populates="projekt")


class Bericht(Basis):
    """Ein Tagesbericht eines Mitarbeiters fuer ein Projekt."""

    __tablename__ = "berichte"
    __table_args__ = (
        # Ein Mitarbeiter, ein Tag, ein Projekt - hoechstens ein gueltiger
        # Bericht. Storniertes und aeltere Versionen bleiben erhalten (D-13),
        # deshalb greift die Eindeutigkeit ueber die Anwendungslogik, nicht
        # ueber einen Index.
        UniqueConstraint("client_uuid", name="uq_bericht_client_uuid"),
        CheckConstraint("version >= 1", name="ck_bericht_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Vom Handy erzeugt. Verhindert Doppelbuchungen, wenn bei schlechtem Netz
    # die Antwort verlorengeht und erneut gesendet wird (ARCHITECTURE §4).
    client_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    mitarbeiter_id: Mapped[int] = mapped_column(ForeignKey("mitarbeiter.id"))
    projekt_id: Mapped[int] = mapped_column(ForeignKey("projekte.id"))
    datum: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[Berichtsstatus] = mapped_column(
        Enum(Berichtsstatus), default=Berichtsstatus.entwurf, index=True)

    rohtranskript: Mapped[str | None] = mapped_column(Text, default=None)
    bemerkung: Mapped[str | None] = mapped_column(Text, default=None)

    version: Mapped[int] = mapped_column(Integer, default=1)
    ersetzt_bericht_id: Mapped[int | None] = mapped_column(
        ForeignKey("berichte.id"), default=None)

    bestaetigt_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    mitarbeiter: Mapped[Mitarbeiter] = relationship(back_populates="berichte")
    projekt: Mapped[Projekt] = relationship(back_populates="berichte")
    positionen: Mapped[list[Position]] = relationship(
        back_populates="bericht", cascade="all, delete-orphan",
        order_by="Position.reihenfolge")
    anwesenheiten: Mapped[list[Anwesenheit]] = relationship(
        back_populates="bericht", cascade="all, delete-orphan")
    dialogschritte: Mapped[list[Dialogschritt]] = relationship(
        back_populates="bericht", cascade="all, delete-orphan",
        order_by="Dialogschritt.id")


class Position(Basis):
    """Eine Leistungsposition (Briefing §6)."""

    __tablename__ = "positionen"

    id: Mapped[int] = mapped_column(primary_key=True)
    bericht_id: Mapped[int] = mapped_column(ForeignKey("berichte.id"), index=True)

    taetigkeit: Mapped[str] = mapped_column(String(200))
    beschreibung: Mapped[str | None] = mapped_column(Text, default=None)
    menge: Mapped[Decimal | None] = mapped_column(DezimalAlsText, default=None)
    einheit_code: Mapped[str | None] = mapped_column(String(16), default=None)
    geschaetzt: Mapped[bool] = mapped_column(Boolean, default=False)
    # Briefing §8: Unsicherheit muss sichtbar bleiben.
    konfidenz: Mapped[float] = mapped_column(Float, default=1.0)
    reihenfolge: Mapped[int] = mapped_column(Integer, default=0)

    bericht: Mapped[Bericht] = relationship(back_populates="positionen")


class Anwesenheit(Basis):
    """Ein Gewerk mit Zeitfenster - entspricht genau einer Zeile in der Mappe.

    Das Gewerk haengt hier und nicht am Bericht: Wer vormittags Trockenbau und
    nachmittags Maler macht, erzeugt zwei Zeilen. Nur so rechnet die
    Eigenleistung je Gewerk richtig.
    """

    __tablename__ = "anwesenheiten"

    id: Mapped[int] = mapped_column(primary_key=True)
    bericht_id: Mapped[int] = mapped_column(ForeignKey("berichte.id"), index=True)

    gewerk: Mapped[str] = mapped_column(String(60))
    beginn: Mapped[time] = mapped_column(Time)
    ende: Mapped[time] = mapped_column(Time)
    quelle: Mapped[Zeitquelle] = mapped_column(
        Enum(Zeitquelle), default=Zeitquelle.gesprochen)

    bericht: Mapped[Bericht] = relationship(back_populates="anwesenheiten")


class Dialogschritt(Basis):
    """Was gesagt und was zurueckgefragt wurde - Nachweis und Fehlersuche."""

    __tablename__ = "dialogschritte"

    id: Mapped[int] = mapped_column(primary_key=True)
    bericht_id: Mapped[int] = mapped_column(ForeignKey("berichte.id"), index=True)

    sprecher: Mapped[Sprecher] = mapped_column(Enum(Sprecher))
    text: Mapped[str] = mapped_column(Text)
    audio_dauer: Mapped[float | None] = mapped_column(Float, default=None)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    bericht: Mapped[Bericht] = relationship(back_populates="dialogschritte")


class Exportlauf(Basis):
    __tablename__ = "exportlaeufe"

    id: Mapped[int] = mapped_column(primary_key=True)
    projekt_id: Mapped[int] = mapped_column(ForeignKey("projekte.id"))
    ziel_datei: Mapped[str] = mapped_column(String(500))
    von: Mapped[date | None] = mapped_column(Date, default=None)
    bis: Mapped[date | None] = mapped_column(Date, default=None)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    zuordnungen: Mapped[list[Exportzuordnung]] = relationship(
        back_populates="lauf", cascade="all, delete-orphan")


class Exportzuordnung(Basis):
    """Welcher Bericht in welche Zeile welcher Mappe ging.

    Verhindert, dass zwei Exportlaeufe fuer denselben Zeitraum die Stunden
    doppelt in die Mappe schreiben (M-6).
    """

    __tablename__ = "exportzuordnungen"
    __table_args__ = (
        # Eindeutig ist die **Zielzeile**, nicht der Bericht: Wer an einem Tag
        # zwei Gewerke gearbeitet hat, belegt zwei Zeilen und erscheint
        # deshalb zweimal im selben Lauf. Eine Regel auf (Lauf, Bericht)
        # haette genau den Fall verboten, der die Eigenleistung erst richtig
        # rechnen laesst.
        UniqueConstraint("exportlauf_id", "ziel_zeile", name="uq_zuordnung_zeile"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exportlauf_id: Mapped[int] = mapped_column(ForeignKey("exportlaeufe.id"), index=True)
    bericht_id: Mapped[int] = mapped_column(ForeignKey("berichte.id"), index=True)

    ziel_zeile: Mapped[int] = mapped_column(Integer)
    ziel_slot: Mapped[int] = mapped_column(Integer)

    lauf: Mapped[Exportlauf] = relationship(back_populates="zuordnungen")
