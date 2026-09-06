"""EPIC 04 · Deterministische Normalisierung.

Deckt aus der Testmatrix (Briefing §21) die Faelle N (deutsche Zahlen),
M (Sonderzeichen), C/D (fehlende Menge und Einheit) und F (unsichere
Erkennung) ab - alle ohne API-Aufruf.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from app.dienste.datum import aufloesen, uhrzeit_aufloesen
from app.dienste.einheiten import codes, normalisieren as einheit
from app.dienste.mengen import parsen

HEUTE = date(2026, 9, 10)          # Donnerstag


# --- N · deutsche Zahlen ---------------------------------------------------

@pytest.mark.parametrize("wortlaut,wert,geschaetzt", [
    ("65", Decimal("65"), False),
    ("ungefähr 45", Decimal("45"), True),          # Briefing §21 N
    ("rund 12,5", Decimal("12.5"), True),          # Briefing §21 N
    ("ca. 30", Decimal("30"), True),
    ("etwa 8", Decimal("8"), True),
    ("12,5", Decimal("12.5"), False),
    ("1.250", Decimal("1250"), False),             # Tausenderpunkt
    ("1.250,50", Decimal("1250.50"), False),
    ("eineinhalb", Decimal("1.5"), False),
    ("anderthalb", Decimal("1.5"), False),
    ("acht", Decimal("8"), False),
    ("zwanzig", Decimal("20"), False),
])
def test_mengen_werden_korrekt_gelesen(wortlaut, wert, geschaetzt):
    menge = parsen(wortlaut)
    assert menge is not None, wortlaut
    assert menge.wert == wert
    assert menge.geschaetzt is geschaetzt


@pytest.mark.parametrize("wortlaut", ["", None, "ein paar", "einige", "viel"])
def test_unklare_mengen_werden_nicht_geraten(wortlaut):
    """Briefing §8: niemals halluzinieren. Lieber None als eine erfundene Zahl."""
    assert parsen(wortlaut) is None


def test_gut_und_knapp_gelten_als_schaetzung():
    assert parsen("gut 50").geschaetzt is True
    assert parsen("knapp 20").geschaetzt is True


# --- M · Sonderzeichen und Einheiten --------------------------------------

@pytest.mark.parametrize("wortlaut,erwartet", [
    ("Quadratmeter", "m²"), ("qm", "m²"), ("m2", "m²"), ("m²", "m²"), ("QM", "m²"),
    ("laufende Meter", "lfm"), ("lfdm", "lfm"), ("Laufmeter", "lfm"),
    ("Kubikmeter", "m³"), ("cbm", "m³"), ("m3", "m³"),
    ("Stück", "Stück"), ("Stck.", "Stück"), ("stk", "Stück"), ("Stueck", "Stück"),
    ("Kilogramm", "kg"), ("kilo", "kg"),
    ("Liter", "Liter"), ("ltr", "Liter"),
    ("Stunden", "Stunden"), ("Std.", "Stunden"), ("h", "Stunden"),
    ("pauschal", "Pauschal"),
])
def test_einheiten_werden_normalisiert(wortlaut, erwartet):
    assert einheit(wortlaut) == erwartet


@pytest.mark.parametrize("wortlaut", ["Kisten", "Paletten", "Eimer", "", None])
def test_unbekannte_einheiten_werden_nicht_geraten(wortlaut):
    """D-07: Was nicht in der Liste steht, wird zur Rueckfrage."""
    assert einheit(wortlaut) is None


def test_einheitenliste_ist_geschlossen():
    assert codes() == ("m²", "lfm", "m³", "Stück", "kg", "Liter", "Stunden", "Pauschal")


# --- Datum -----------------------------------------------------------------

@pytest.mark.parametrize("wortlaut,erwartet", [
    (None, HEUTE),                                  # kein Datum -> Erfassungstag
    ("heute", HEUTE),
    ("gestern", date(2026, 9, 9)),
    ("vorgestern", date(2026, 9, 8)),
    ("letzten Freitag", date(2026, 9, 4)),
    ("am Montag", date(2026, 9, 7)),
    ("14.3.", date(2026, 3, 14)),
    ("14.03.2026", date(2026, 3, 14)),
    ("am 1.9.2026", date(2026, 9, 1)),
])
def test_datumsangaben(wortlaut, erwartet):
    assert aufloesen(wortlaut, HEUTE) == erwartet


def test_wochentag_meint_immer_die_vergangenheit():
    """Es geht um geleistete Arbeit - 'am Donnerstag' am Donnerstag meint
    die Vorwoche, nicht heute."""
    assert aufloesen("am Donnerstag", HEUTE) == date(2026, 9, 3)


def test_datum_ohne_jahr_kurz_nach_dem_jahreswechsel():
    """Am 02.01. gesagt meint '28.12.' das Vorjahr."""
    assert aufloesen("28.12.", date(2027, 1, 2)) == date(2026, 12, 28)


def test_jahresrueckfall_gilt_nur_fuer_die_juengste_vergangenheit():
    """Im September gesagt ist '14.12.' eher ein Hoerfehler als ein Bericht
    vom vorletzten Dezember - dann lieber nachfragen."""
    assert aufloesen("14.12.", HEUTE) is None


@pytest.mark.parametrize("wortlaut", ["nächste Woche", "irgendwann", "morgen früh"])
def test_unklare_datumsangaben_ergeben_none(wortlaut):
    assert aufloesen(wortlaut, HEUTE) is None


@pytest.mark.parametrize("wortlaut,erwartet", [
    ("7 Uhr", time(7, 0)), ("07:00", time(7, 0)), ("16:30", time(16, 30)),
    ("halb acht", time(7, 30)), ("halb fünf", time(4, 30)),
    ("sieben", time(7, 0)), ("7.30 Uhr", time(7, 30)),
])
def test_uhrzeiten(wortlaut, erwartet):
    assert uhrzeit_aufloesen(wortlaut) == erwartet


# --- Zwoelfstundenformat der Umgangssprache -------------------------------

@pytest.mark.parametrize("beginn,ende,erwartet,verschoben", [
    (time(7, 0), time(4, 30), time(16, 30), True),    # "von 7 bis halb fünf"
    (time(6, 30), time(3, 0), time(15, 0), True),
    (time(7, 0), time(16, 30), time(16, 30), False),  # schon eindeutig
    (time(22, 0), time(6, 0), time(6, 0), False),     # echte Nachtschicht
    (time(20, 0), time(4, 0), time(4, 0), False),
    (time(8, 0), time(8, 0), time(8, 0), False),
])
def test_nachmittagskorrektur(beginn, ende, erwartet, verschoben):
    """Auf der Baustelle sagt niemand "sechzehn Uhr dreissig" - aber
    Nachtschichten duerfen dabei nicht kaputtgehen."""
    from app.dienste.datum import nachmittag_korrigieren
    ergebnis, wurde_verschoben = nachmittag_korrigieren(beginn, ende)
    assert ergebnis == erwartet
    assert wurde_verschoben is verschoben


def test_nachmittagskorrektur_ohne_zeiten():
    from app.dienste.datum import nachmittag_korrigieren
    assert nachmittag_korrigieren(None, time(4, 0)) == (time(4, 0), False)
    assert nachmittag_korrigieren(time(7, 0), None) == (None, False)
