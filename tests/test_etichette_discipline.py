from datetime import date

import pytest

from curricolo import esporta_ini, importa_ini
from curricolo import catalogo
from curricolo.catalogo import etichetta_disciplina
from curricolo.config import ENCODING_INI, SEPARATORE_INI
from main import app


def test_etichetta_disciplina_mostra_nomi_scienze_sperimentali():
    assert etichetta_disciplina("CHIMICA") == "Sc.Sp. Chimica"
    assert etichetta_disciplina("fisica") == "Sc.Sp. Fisica"
    assert (
        etichetta_disciplina("SCIENZA DELLA TERRA E BIOLOGIA")
        == "Sc.Sp. Scienza della Terra e Biologia"
    )


def test_etichetta_disciplina_non_modifica_identificativi_interni():
    assert etichetta_disciplina("CHIMICA") != "CHIMICA"
    assert etichetta_disciplina("MATEMATICA") == "MATEMATICA"
    assert (
        etichetta_disciplina("CHIMICA (solo se specifica per indirizzo)")
        == "Sc.Sp. Chimica"
    )


def test_filtro_interfaccia_usa_etichette_senza_alterare_valori_form():
    etichetta = app.jinja_env.from_string(
        "{{ disciplina | etichetta_disciplina }}"
    ).render(disciplina="CHIMICA")
    valore_form = app.jinja_env.from_string(
        '<input value="{{ disciplina }}">'
    ).render(disciplina="CHIMICA")

    assert etichetta == "Sc.Sp. Chimica"
    assert valore_form == '<input value="CHIMICA">'


def test_api_discipline_restituisce_etichetta_e_nome_interno(monkeypatch):
    from curricolo import catalogo

    monkeypatch.setattr(catalogo, "discipline", lambda _classe, _indirizzo: ["CHIMICA"])

    risposta = app.test_client().get(
        "/api/discipline?classe=PRIMA&indirizzo=COMUNE"
    )

    assert risposta.status_code == 200
    assert risposta.get_json() == [
        {"valore": "CHIMICA", "etichetta": "Sc.Sp. Chimica"}
    ]


@pytest.mark.parametrize(
    "disciplina",
    ["CHIMICA", "FISICA", "SCIENZA DELLA TERRA E BIOLOGIA"],
)
def test_file_ini_legacy_restano_compatibili(disciplina, tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "opzioni", lambda _gruppo: [])
    percorso = tmp_path / "programmazione.ini"
    percorso.write_bytes(
        f"000006DISCIPLINA{SEPARATORE_INI}{disciplina}\r\n".encode(ENCODING_INI)
    )

    riletta = importa_ini.leggi_file(percorso)
    righe_esportate = esporta_ini.genera_righe(riletta, date(2026, 9, 30))

    assert riletta.disciplina == disciplina
    assert etichetta_disciplina(riletta.disciplina).startswith("Sc.Sp.")
    assert f"000006DISCIPLINA{SEPARATORE_INI}{disciplina}" in righe_esportate
