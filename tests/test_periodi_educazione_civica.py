from pathlib import Path

import pytest

from curricolo.educazione_civica import quadrimestre_periodo


@pytest.mark.parametrize(
    ("periodo", "quadrimestre"),
    [
        ("primo quadrimestre", "I"),
        ("gennaio", "I"),
        ("dicembre - gennaio", "I"),
        ("secondo quadrimestre", "II"),
        ("dicembre - gennaio - febbraio", "II"),
        ("gennaio - febbraio", "II"),
        ("febbraio", "II"),
        ("", ""),
        ("periodo non definito", ""),
    ],
)
def test_quadrimestre_periodo(periodo, quadrimestre):
    assert quadrimestre_periodo(periodo) == quadrimestre


def test_tutti_i_periodi_catalogo_seguono_il_confine_del_secondo_quadrimestre():
    percorso = (
        Path(__file__).resolve().parent.parent
        / "do_not_use"
        / "moduli"
        / "periodi.ini"
    )
    periodi = percorso.read_text(encoding="cp1252").splitlines()
    indice_secondo = periodi.index("secondo quadrimestre")

    assert all(
        quadrimestre_periodo(periodo) == "I"
        for periodo in periodi[:indice_secondo]
    )
    assert all(
        quadrimestre_periodo(periodo) == "II"
        for periodo in periodi[indice_secondo:]
    )
