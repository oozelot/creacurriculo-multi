import json

from curricolo import db, educazione_civica
from curricolo.modello import Modulo, Programmazione, UnitaDidattica


DISCIPLINA_CANONICA = "TRASFORMAZIONE DEI PRODOTTI"
DISCIPLINA_ARTICOLAZIONE = (
    "TRASFORMAZIONE DEI PRODOTTI (solo se specifica per articolazione)"
)
VOCE = "Educazione alla salute e al benessere"


def _prepara_piano(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "FILE_DB", tmp_path / "corrente.db")
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)
    dati = {
        "macroarea": "EDUCAZIONE SOSTENIBILE",
        "voci": [
            {"macroarea": "EDUCAZIONE SOSTENIBILE", "voce": VOCE, "ore": 2}
        ],
        "ore_disciplina": 2,
        "conferme": {},
    }
    with db.connessione() as conn:
        conn.execute(
            "INSERT INTO educazione_civica_catalogo (macroarea, voce, posizione) "
            "VALUES (?, ?, 1)",
            ("EDUCAZIONE SOSTENIBILE", VOCE),
        )
        conn.execute(
            "INSERT INTO educazione_civica_piani "
            "(corso, classe, articolazione, disciplina, dati) "
            "VALUES ('AGRARIO', 'QUARTA', 'COMUNE', ?, ?)",
            (DISCIPLINA_CANONICA, json.dumps(dati, ensure_ascii=False)),
        )


def _programmazione(ec_voci, ec_ore):
    unita = UnitaDidattica(
        titolo="Contaminanti alimentari",
        multidisciplinare=[2],
        ec_voci=ec_voci,
        ec_ore=ec_ore,
        ec_periodo="primo quadrimestre",
        ec_quadrimestre="I",
    )
    return Programmazione(
        cognome="DIPARTIMENTO",
        nome="TRASFORMAZIONE",
        classe="QUARTA",
        indirizzo="AGRARIO (eno)",
        disciplina=DISCIPLINA_ARTICOLAZIONE,
        moduli=[Modulo(unita=[unita])],
    )


def test_registra_ore_per_disciplina_con_nota_articolazione(monkeypatch, tmp_path):
    _prepara_piano(monkeypatch, tmp_path)
    chiave = educazione_civica.chiave_conferma(
        "DIPARTIMENTO", "TRASFORMAZIONE", DISCIPLINA_ARTICOLAZIONE, 2, 1,
        "QUARTA", "AGRARIO (eno)",
    )

    assert educazione_civica.registra_conferma(
        "QUARTA",
        "AGRARIO (eno)",
        DISCIPLINA_ARTICOLAZIONE,
        chiave,
        {"voci": [VOCE], "quadrimestre": "I", "periodo": "primo quadrimestre", "ore": "2"},
    )

    piano = educazione_civica.piano_per_docente(
        "QUARTA", "AGRARIO (eno)", DISCIPLINA_ARTICOLAZIONE
    )
    assert piano is not None
    assert educazione_civica.ore_utilizzate_per_voce(piano) == {VOCE: 2}
    assert piano["conferme"][chiave]["ambito_articolazioni"] == ["ENO"]

    for indirizzo in ("AGRARIO (p.t.)", "AGRARIO (g.a.t.)"):
        piano_altra_articolazione = educazione_civica.piano_per_docente(
            "QUARTA", indirizzo, DISCIPLINA_ARTICOLAZIONE
        )
        assert piano_altra_articolazione is not None
        assert educazione_civica.ore_utilizzate_per_voce(piano_altra_articolazione) == {}


def test_conferma_da_piano_agrario_comune_riguarda_tutte_le_articolazioni(
    monkeypatch, tmp_path
):
    _prepara_piano(monkeypatch, tmp_path)
    chiave = educazione_civica.chiave_conferma(
        "DIPARTIMENTO", "TRASFORMAZIONE", DISCIPLINA_CANONICA, 2, 1,
        "QUARTA", "AGRARIO",
    )

    assert educazione_civica.registra_conferma(
        "QUARTA",
        "AGRARIO",
        DISCIPLINA_CANONICA,
        chiave,
        {"voci": [VOCE], "quadrimestre": "I", "periodo": "primo quadrimestre", "ore": "2"},
    )

    for indirizzo in ("AGRARIO (p.t.)", "AGRARIO (g.a.t.)", "AGRARIO (eno)"):
        piano = educazione_civica.piano_per_docente(
            "QUARTA", indirizzo, DISCIPLINA_CANONICA
        )
        assert piano is not None
        assert educazione_civica.ore_utilizzate_per_voce(piano) == {VOCE: 2}


def test_conferme_della_stessa_disciplina_non_si_sovrascrivono_tra_articolazioni(
    monkeypatch, tmp_path
):
    _prepara_piano(monkeypatch, tmp_path)
    chiave_eno = educazione_civica.chiave_conferma(
        "DOCENTE", "DIPARTIMENTO", DISCIPLINA_ARTICOLAZIONE, 1, 1,
        "QUARTA", "AGRARIO (eno)",
    )
    chiave_pt = educazione_civica.chiave_conferma(
        "DOCENTE", "DIPARTIMENTO", DISCIPLINA_ARTICOLAZIONE, 1, 1,
        "QUARTA", "AGRARIO (p.t.)",
    )

    for indirizzo, chiave, periodo in (
        ("AGRARIO (eno)", chiave_eno, "primo quadrimestre"),
        ("AGRARIO (p.t.)", chiave_pt, "secondo quadrimestre"),
    ):
        assert educazione_civica.registra_conferma(
            "QUARTA",
            indirizzo,
            DISCIPLINA_ARTICOLAZIONE,
            chiave,
            {
                "voci": [VOCE],
                "quadrimestre": "I" if "primo" in periodo else "II",
                "periodo": periodo,
                "ore": "2",
            },
        )

    piano_eno = educazione_civica.piano_per_docente(
        "QUARTA", "AGRARIO (eno)", DISCIPLINA_ARTICOLAZIONE
    )
    piano_pt = educazione_civica.piano_per_docente(
        "QUARTA", "AGRARIO (p.t.)", DISCIPLINA_ARTICOLAZIONE
    )
    assert list(piano_eno["conferme"]) == [chiave_eno]
    assert list(piano_pt["conferme"]) == [chiave_pt]


def test_conferma_da_file_comune_si_registra_su_tutti_i_corsi(
    monkeypatch, tmp_path
):
    _prepara_piano(monkeypatch, tmp_path)
    dati_piano = {
        "macroarea": "EDUCAZIONE SOSTENIBILE",
        "voci": [{"macroarea": "EDUCAZIONE SOSTENIBILE", "voce": VOCE, "ore": 2}],
        "ore_disciplina": 2,
        "conferme": {},
    }
    with db.connessione() as conn:
        for corso in ("CAT", "GRAFICO"):
            conn.execute(
                "INSERT INTO educazione_civica_piani "
                "(corso, classe, articolazione, disciplina, dati) VALUES (?, 'QUARTA', "
                "'COMUNE', ?, ?)",
                (corso, DISCIPLINA_CANONICA, json.dumps(dati_piano, ensure_ascii=False)),
            )

    chiave = educazione_civica.chiave_conferma(
        "DIPARTIMENTO", "COMUNE", DISCIPLINA_CANONICA, 2, 1,
        "QUARTA", "COMUNE",
    )
    assert educazione_civica.registra_conferma(
        "QUARTA",
        "COMUNE",
        DISCIPLINA_CANONICA,
        chiave,
        {"voci": [VOCE], "quadrimestre": "I", "periodo": "primo quadrimestre", "ore": "2"},
    )

    with db.connessione() as conn:
        piani = conn.execute(
            "SELECT corso, dati FROM educazione_civica_piani "
            "WHERE classe = 'QUARTA' AND disciplina = ?",
            (DISCIPLINA_CANONICA,),
        ).fetchall()
    conferme = {
        riga["corso"]: json.loads(riga["dati"])["conferme"][chiave]
        for riga in piani
    }
    assert conferme["AGRARIO"]["ambito_articolazioni"] == ["TUTTE"]
    assert "ambito_articolazioni" not in conferme["CAT"]
    assert "ambito_articolazioni" not in conferme["GRAFICO"]


def test_import_sync_rimuove_conferma_da_piano_canonico(monkeypatch, tmp_path):
    _prepara_piano(monkeypatch, tmp_path)
    prog = _programmazione([VOCE], "2")
    chiave = educazione_civica.chiave_conferma(
        prog.cognome, prog.nome, prog.disciplina, 1, 1,
        prog.classe, prog.indirizzo,
    )

    educazione_civica.sincronizza_conferme_programmazione(prog)
    piano = educazione_civica.piano_per_docente(
        prog.classe, prog.indirizzo, prog.disciplina
    )
    assert educazione_civica.ore_utilizzate_per_voce(piano) == {VOCE: 2}
    assert next(iter(piano["conferme"].values()))["ambito_articolazioni"] == ["ENO"]

    prog.moduli[0].unita[0].multidisciplinare = [1]
    prog.moduli[0].unita[0].ec_voci = []
    prog.moduli[0].unita[0].ec_ore = ""
    educazione_civica.sincronizza_conferme_programmazione(prog)

    piano = educazione_civica.piano_per_docente(
        prog.classe, prog.indirizzo, prog.disciplina
    )
    assert piano is not None
    assert piano["conferme"] == {}
    assert chiave not in piano["conferme"]
