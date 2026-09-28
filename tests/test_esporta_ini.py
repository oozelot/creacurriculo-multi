from datetime import date
from pathlib import Path

from curricolo import archivio, esporta_ini, legacy
from curricolo.modello import Programmazione


def test_nome_file_invio_aggiunge_il_referente():
    prog = Programmazione(
        cognome="DIPARTIMENTO",
        nome="BIOTECNOLOGIE AGRARIE",
        classe="TERZA",
        indirizzo="AGRARIO (g.a.t.)",
        disciplina="BIOTECNOLOGIE AGRARIE",
    )

    nome = esporta_ini.nome_file_invio(prog, date(2023, 9, 29), "ALESSANDRO MAESTRI")

    assert nome.endswith("_29_09_23 - Alessandro Maestri.ini")


def test_referente_da_nome_file_normalizza_nome_e_cognome():
    assert archivio._referente_da_nome_file(
        "BIOTA_GAT_DIPBIO_TERZA_29_09_23 - aLESSANDRO mAESTRI.ini"
    ) == "Alessandro Maestri"


def test_legacy_uda_roundtrip_preserva_dati_educazione_civica(tmp_path):
    originale = {
        "titolo": "UDA test",
        "argomenti": "Argomenti",
        "prerequisiti": "Prerequisiti",
        "multidisciplinare": [2],
        "multidisciplinare_altro": "",
        "abilita": ["Abilita 1"],
        "codici_abilita": ["A1"],
        "conoscenze": ["Conoscenza 1"],
        "codici_conoscenze": ["C1"],
        "competenze_europee": [1],
        "competenze_cittadinanza": [2],
        "competenze_pecup": ["Competenza 1"],
        "codici_competenze_pecup": ["P1"],
        "competenze_minime": "Minime",
        "competenze_intermedie": "Intermedie",
        "competenze_avanzate": "Avanzate",
        "ec_voci": ["Cittadinanza digitale", "Educazione ambientale"],
        "ec_ore": "3",
        "ec_periodo": "ottobre-dicembre",
        "ec_quadrimestre": "I",
    }

    percorso = tmp_path / "datispecificiud.ini"
    percorso.write_bytes(("\r\n".join(legacy._righe_unita(originale)) + "\r\n").encode("cp1252"))

    letto = legacy._leggi_unita(percorso)

    assert letto["ec_voci"] == originale["ec_voci"]
    assert letto["ec_ore"] == originale["ec_ore"]
    assert letto["ec_periodo"] == originale["ec_periodo"]
    assert letto["ec_quadrimestre"] == originale["ec_quadrimestre"]