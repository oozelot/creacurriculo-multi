import json
import sqlite3

from curricolo import catalogo, db, educazione_civica
import main


def _prepara_db(monkeypatch, tmp_path):
    percorso = tmp_path / "corrente.db"
    monkeypatch.setattr(db, "FILE_DB", percorso)
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)
    with db.connessione() as conn:
        conn.executemany(
            "INSERT INTO classi (numero, nome) VALUES (?, ?)",
            [(1, "PRIMA"), (2, "SECONDA"), (3, "TERZA"), (4, "QUARTA"), (5, "QUINTA")],
        )
        conn.executemany(
            "INSERT INTO indirizzi (id, nome, sigla, posizione) VALUES (?, ?, ?, ?)",
            [
                (1, "COMUNE", "COM", 1),
                (2, "CAT", "CAT", 2),
                (3, "GRAFICO", "GRA", 3),
                (4, "AGRARIO (tutte le articolazioni)", "AGR", 4),
                (5, "AGRARIO (g.a.t.)", "GAT", 5),
                (6, "AGRARIO (p.t.)", "PT", 6),
                (7, "AGRARIO (eno)", "ENO", 7),
            ],
        )
        conn.execute(
            "INSERT INTO educazione_civica_catalogo (macroarea, voce, posizione) "
            "VALUES ('COSTITUZIONE', 'LEGALITA', 1)"
        )
        conn.executemany(
            "INSERT INTO discipline (id, nome, sigla, sigla_ini, attende_ini) VALUES (?, ?, ?, ?, 0)",
            [(1, "MATERIA DA ELIMINARE", "MDE", "MATER"), (2, "MATERIA DESTINATARIA", "MDT", "MATER")],
        )
        conn.executemany(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (?, ?, ?)",
            [(1, 2, 1), (2, 2, 1)],
        )
        conn.execute(
            "INSERT INTO pecup (id, tipo, codice, descrizione) VALUES (1, 'abilita', 'MDE1', 'Voce')"
        )
        conn.execute(
            "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) VALUES (1, 'MATERIA DA ELIMINARE', 1, 2)"
        )
        conn.commit()
    return percorso


def _aggiungi_piano(percorso, disciplina, ore, conferme=None, corso="CAT", classe="PRIMA"):
    dati = {
        "macroarea": "COSTITUZIONE",
        "voci": [{"macroarea": "COSTITUZIONE", "voce": "LEGALITA", "ore": ore}],
        "ore_disciplina": ore,
        "conferme": conferme or {},
    }
    conn = sqlite3.connect(percorso)
    conn.execute(
        "INSERT INTO educazione_civica_piani "
        "(corso, classe, articolazione, disciplina, dati) VALUES (?, ?, 'COMUNE', ?, ?)",
        (corso, classe, disciplina, json.dumps(dati)),
    )
    conn.commit()
    conn.close()


def test_eliminazione_materia_senza_trasferimento_rimuove_solo_piano_collegato(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    _aggiungi_piano(percorso, "MATERIA DA ELIMINARE", 6)
    _aggiungi_piano(percorso, "MATERIA DESTINATARIA", 3)

    piani = catalogo.piani_educazione_per_rimozione(1)
    assert len(piani) == 1
    assert piani[0]["corso"] == "CAT"
    assert piani[0]["dati"]["voci"][0]["ore"] == 6

    assert catalogo.applica_rimozione_materia(1)

    with db.connessione() as conn:
        assert conn.execute("SELECT 1 FROM discipline WHERE id = 1").fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM educazione_civica_piani WHERE disciplina = 'MATERIA DA ELIMINARE'"
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM educazione_civica_piani WHERE disciplina = 'MATERIA DESTINATARIA'"
        ).fetchone() is not None
        assert conn.execute("SELECT COUNT(*) FROM pecup_validita").fetchone()[0] == 0


def test_trasferimento_materia_somma_ore_e_azzera_conferme(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    _aggiungi_piano(
        percorso,
        "MATERIA DA ELIMINARE",
        6,
        {"DOCENTE|MATERIA|M1|UD1": {"voci": ["LEGALITA"], "periodo": "PRIMO"}},
    )
    _aggiungi_piano(
        percorso,
        "MATERIA DESTINATARIA",
        3,
        {"ALTRO|DOCENTE|M1|UD1": {"voci": ["LEGALITA"], "periodo": "SECONDO"}},
    )
    piani = catalogo.piani_educazione_per_rimozione(1)
    opzioni = catalogo.materie_destinazione_educazione(1, piani[0])
    assert [voce["id"] for voce in opzioni] == [2]

    assert catalogo.applica_rimozione_materia(1, {"0": 2})

    with db.connessione() as conn:
        piano = conn.execute(
            "SELECT dati FROM educazione_civica_piani WHERE disciplina = 'MATERIA DESTINATARIA'"
        ).fetchone()
    dati = json.loads(piano["dati"])
    assert dati["voci"][0]["ore"] == 9
    assert dati["ore_disciplina"] == 9
    assert dati["conferme"] == {}
    completamento_cat = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "CAT"
    )
    assert completamento_cat["ore"][0] == 9


def test_completamento_ignora_piano_di_materia_non_piu_attiva(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute(
            "UPDATE discipline SET nome = ? WHERE id = 1",
            ("TECNOLOGIE INFORMATICHE",),
        )
        conn.execute(
            "UPDATE discipline SET nome = ? WHERE id = 2",
            ("TECNOLOGIE DELL'INFORMAZIONE E DELLA COMUNICAZIONE BIENNIO CAT",),
        )
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 1")
        conn.commit()
    _aggiungi_piano(percorso, "TECNOLOGIE INFORMATICHE", 6)

    completamento_cat = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "CAT"
    )

    assert completamento_cat["ore"][0] == 0


def test_completamento_conta_materie_comuni_previste_per_cat(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 2")
        conn.execute(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (2, 1, 1)"
        )
        conn.commit()
    _aggiungi_piano(percorso, "MATERIA DESTINATARIA", 6)

    completamento_cat = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "CAT"
    )

    assert completamento_cat["ore"][0] == 6


def test_completamento_conta_piano_comune_per_materia_agraria_di_articolazione(monkeypatch, tmp_path):
    _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 2")
        conn.execute(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (2, 6, 4)"
        )
        conn.commit()
    _aggiungi_piano(
        tmp_path / "corrente.db",
        "MATERIA DESTINATARIA",
        5,
        corso="AGRARIO",
        classe="QUARTA",
    )

    completamento_agrario = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "AGRARIO"
    )

    assert completamento_agrario["ore"][3] == {
        "articolazioni": [
            {"nome": "PT", "ore": 5},
            {"nome": "GAT", "ore": 0},
            {"nome": "ENO", "ore": 0},
        ],
        "stato": "giallo",
    }


def test_completamento_agrario_somma_ogni_articolazione_separatamente(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 2")
        conn.executemany(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (2, ?, 4)",
            [(5,), (6,), (7,)],
        )
        conn.commit()
    _aggiungi_piano(
        percorso, "MATERIA DESTINATARIA", 5, corso="AGRARIO", classe="QUARTA"
    )
    educazione_civica.salva_piano(
        "AGRARIO",
        "QUARTA",
        "PT",
        "MATERIA DESTINATARIA",
        {
            "macroarea": "COSTITUZIONE",
            "voci": [{"macroarea": "COSTITUZIONE", "voce": "LEGALITA", "ore": 7}],
            "ore_disciplina": 7,
            "conferme": {},
        },
    )

    completamento_agrario = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "AGRARIO"
    )

    assert completamento_agrario["ore"][3] == {
        "articolazioni": [
            {"nome": "PT", "ore": 7},
            {"nome": "GAT", "ore": 5},
            {"nome": "ENO", "ore": 5},
        ],
        "stato": "giallo",
    }


def test_completamento_agrario_verde_solo_se_tutte_le_articolazioni_raggiungono_33(
    monkeypatch, tmp_path
):
    percorso = _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 2")
        conn.executemany(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (2, ?, 4)",
            [(5,), (6,), (7,)],
        )
        conn.commit()
    _aggiungi_piano(
        percorso, "MATERIA DESTINATARIA", 33, corso="AGRARIO", classe="QUARTA"
    )

    completamento_agrario = next(
        voce for voce in main._calcola_completamento() if voce["corso"] == "AGRARIO"
    )

    assert completamento_agrario["ore"][3] == {
        "articolazioni": [
            {"nome": "PT", "ore": 33},
            {"nome": "GAT", "ore": 33},
            {"nome": "ENO", "ore": 33},
        ],
        "stato": "verde",
    }


def test_piano_comune_agrario_e_visibile_nell_articolazione_della_materia(monkeypatch, tmp_path):
    _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute("DELETE FROM offerta_formativa WHERE disciplina_id = 2")
        conn.execute(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (2, 6, 4)"
        )
        conn.commit()
    _aggiungi_piano(
        tmp_path / "corrente.db",
        "MATERIA DESTINATARIA",
        5,
        corso="AGRARIO",
        classe="QUARTA",
    )
    monkeypatch.setattr(main, "_sessione_inizializzata", True)

    risposta = main.app.test_client().get(
        "/admin/educazione-civica?corso=AGRARIO&classe=QUARTA"
    )

    assert risposta.status_code == 200
    assert b'value="MATERIA DESTINATARIA" checked' in risposta.data
    assert b"5-0-0" in risposta.data
    assert b'aria-label="PT: 5, GAT: 0, ENO: 0"' in risposta.data


def test_rimozione_parziale_rimuove_solo_il_contesto_interessato(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    with db.connessione() as conn:
        conn.execute(
            "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (1, 3, 1)"
        )
        conn.commit()
    _aggiungi_piano(percorso, "MATERIA DA ELIMINARE", 6, corso="CAT")
    _aggiungi_piano(percorso, "MATERIA DA ELIMINARE", 8, corso="GRAFICO")
    contesti = educazione_civica.contesti_per_percorsi(
        "PRIMA", [("PRIMA", "CAT")]
    )
    assert contesti == [("CAT", "PRIMA", "COMUNE")]
    piani = catalogo.piani_educazione_per_rimozione(1, [("PRIMA", "CAT")])
    assert [piano["corso"] for piano in piani] == ["CAT"]

    assert catalogo.applica_rimozione_materia(
        1, {}, [("PRIMA", "GRAFICO")]
    )

    with db.connessione() as conn:
        assert conn.execute(
            "SELECT 1 FROM offerta_formativa WHERE disciplina_id = 1 AND indirizzo_id = 2"
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM offerta_formativa WHERE disciplina_id = 1 AND indirizzo_id = 3"
        ).fetchone() is not None
        assert conn.execute(
            "SELECT 1 FROM educazione_civica_piani WHERE corso = 'CAT'"
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM educazione_civica_piani WHERE corso = 'GRAFICO'"
        ).fetchone() is not None


def test_contesti_per_percorsi_rispetta_comune_e_articolazioni():
    assert educazione_civica.contesti_per_percorsi(
        "PRIMA", [("PRIMA", "COMUNE")]
    ) == [
        ("CAT", "PRIMA", "COMUNE"),
        ("GRAFICO", "PRIMA", "COMUNE"),
        ("AGRARIO", "PRIMA", "COMUNE"),
    ]
    assert educazione_civica.contesti_per_percorsi(
        "TERZA",
        [
            ("TERZA", "CAT"),
            ("TERZA", "GRAFICO"),
            ("TERZA", "AGRARIO (tutte le articolazioni)"),
            ("TERZA", "AGRARIO (g.a.t.)"),
            ("TERZA", "AGRARIO (p.t.)"),
        ],
    ) == [
        ("CAT", "TERZA", "COMUNE"),
        ("GRAFICO", "TERZA", "COMUNE"),
        ("AGRARIO", "TERZA", "COMUNE"),
        ("AGRARIO", "TERZA", "PT"),
        ("AGRARIO", "TERZA", "GAT"),
    ]


def test_flusso_admin_mostra_conferma_e_trasferisce_prima_di_eliminare(monkeypatch, tmp_path):
    percorso = _prepara_db(monkeypatch, tmp_path)
    _aggiungi_piano(percorso, "MATERIA DA ELIMINARE", 6)
    monkeypatch.setattr(main, "_sessione_inizializzata", True)

    client = main.app.test_client()
    risposta = client.post(
        "/admin/materie/elimina",
        data={"identificativo": "1"},
        follow_redirects=True,
    )

    assert risposta.status_code == 200
    assert b"Eliminazione materia" in risposta.data
    assert b"6 ore" in risposta.data

    risposta = client.post(
        "/admin/materie/elimina/decidi",
        data={"azione": "trasferisci"},
        follow_redirects=True,
    )
    assert risposta.status_code == 200
    assert b"Memorizza trasferimenti ed eliminazione" in risposta.data
    assert b"MATERIA DESTINATARIA" in risposta.data

    risposta = client.post(
        "/admin/materie/elimina/memorizza",
        data={"destinatario_0": "2"},
        follow_redirects=False,
    )
    assert risposta.status_code == 302
    assert risposta.headers["Location"].endswith(
        "/admin/educazione-civica?corso=CAT&classe=PRIMA"
    )
    with db.connessione() as conn:
        assert conn.execute("SELECT 1 FROM discipline WHERE id = 1").fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM educazione_civica_piani WHERE disciplina = 'MATERIA DESTINATARIA'"
        ).fetchone() is not None
