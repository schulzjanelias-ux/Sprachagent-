"""Serialisierung fuer Spalte I (D-02) - Briefing §21 M und N."""
from decimal import Decimal

import pytest

from app.dienste.berichte import Leistung
from app.dienste.leistungstext import LAENGE_MAX, menge_deutsch, serialisieren


@pytest.mark.parametrize("wert,erwartet", [
    (Decimal("65"), "65"),
    (Decimal("12.5"), "12,5"),
    (Decimal("12.50"), "12,5"),        # nachlaufende Null faellt weg
    (Decimal("100"), "100"),           # nicht 1E+2
    (Decimal("0.5"), "0,5"),
    (Decimal("1250"), "1250"),         # kein Tausenderpunkt
    (Decimal("1.25"), "1,25"),
])
def test_deutsche_zahlformatierung(wert, erwartet):
    assert menge_deutsch(wert) == erwartet


def test_beispiel_aus_dem_briefing():
    """Briefing §3: 65 m² gespachtelt, 40 m² geschliffen."""
    text = serialisieren([
        Leistung("Spachtelarbeiten", menge=Decimal("65"), einheit="m²"),
        Leistung("Schleifarbeiten", menge=Decimal("40"), einheit="m²"),
    ])
    assert text == "Spachtelarbeiten 65 m²; Schleifarbeiten 40 m²"


def test_position_ohne_menge_bleibt_reine_taetigkeit():
    assert serialisieren([Leistung("Baustelle aufgeräumt")]) == "Baustelle aufgeräumt"


def test_menge_ohne_einheit():
    assert serialisieren([Leistung("Türen", menge=Decimal("8"))]) == "Türen 8"


def test_leere_liste():
    assert serialisieren([]) == ""


def test_zeilenumbrueche_werden_zu_trennern():
    """Umbrueche erschweren das Wiedereinlesen aus Spalte I."""
    text = serialisieren([Leistung("Wand\ngespachtelt\tund geglättet")])
    assert "\n" not in text and "\t" not in text
    assert text == "Wand gespachtelt und geglättet"


def test_sonderzeichen_bleiben_erhalten():
    """§21 M: Umlaute und m² duerfen nicht verstuemmelt werden."""
    text = serialisieren([Leistung("Türöffnungen vergrößert", menge=Decimal("3"), einheit="m²")])
    assert text == "Türöffnungen vergrößert 3 m²"


def test_sehr_lange_liste_wird_an_positionsgrenze_gekuerzt():
    viele = [Leistung(f"Tätigkeit {i}", menge=Decimal("10"), einheit="m²") for i in range(120)]
    text = serialisieren(viele, bericht_id="TB-2026-0001")
    assert len(text) <= LAENGE_MAX
    assert text.endswith("vollstaendig in Bericht TB-2026-0001")
    # nicht mitten in einer Position abgeschnitten
    assert " …" in text
    erste = text.split("; ")[0]
    assert erste == "Tätigkeit 0 10 m²"
