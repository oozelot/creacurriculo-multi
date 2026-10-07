from pathlib import Path

import pytest

from curricolo import educazione_civica
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


def test_quadrimestre_periodo_segue_il_catalogo_modificato_dall_utente(tmp_path, monkeypatch):
    cartella_legacy = tmp_path / "do_not_use"
    cartella_moduli = cartella_legacy / "moduli"
    cartella_moduli.mkdir(parents=True)
    (cartella_moduli / "periodi.ini").write_text(
        "primo quadrimestre\ngennaio - febbraio\n"
        "secondo quadrimestre\nmarzo\n",
        encoding="cp1252",
    )
    monkeypatch.setattr(educazione_civica, "CARTELLA_LEGACY", cartella_legacy)

    assert quadrimestre_periodo("gennaio - febbraio") == "I"
    assert quadrimestre_periodo("marzo") == "II"
