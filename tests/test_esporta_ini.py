from datetime import date

from curricolo import archivio, esporta_ini
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