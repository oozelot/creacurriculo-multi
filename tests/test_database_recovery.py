import json
import sqlite3

from curricolo import db


def _crea_database(percorso):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(percorso)
    db.crea_schema(conn)
    conn.executemany(
        "INSERT INTO classi (numero, nome) VALUES (?, ?)",
        [(1, "PRIMA"), (2, "SECONDA")],
    )
    conn.executemany(
        "INSERT INTO indirizzi (id, nome, sigla, posizione) VALUES (?, ?, ?, ?)",
        [(1, "COMUNE", "COM", 1), (2, "CAT", "CAT", 2)],
    )
    conn.commit()
    conn.close()


def _aggiungi_materia(percorso, identificativo, nome, classe=1, indirizzo=1):
    conn = sqlite3.connect(percorso)
    conn.execute(
        "INSERT INTO discipline (id, nome, sigla, sigla_ini, attende_ini) VALUES (?, ?, ?, ?, 0)",
        (identificativo, nome, nome[:3], nome[:5]),
    )
    conn.execute(
        "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (?, ?, ?)",
        (identificativo, indirizzo, classe),
    )
    conn.commit()
    conn.close()


def _aggiungi_piano(percorso, corso, classe, disciplina, conferme=None, articolazione="COMUNE"):
    dati = {
        "macroarea": "COSTITUZIONE",
        "voci": [{"macroarea": "COSTITUZIONE", "voce": "LEGALITA", "ore": 4}],
        "ore_disciplina": 4,
        "conferme": conferme or {},
    }
    conn = sqlite3.connect(percorso)
    conn.execute(
        "INSERT INTO educazione_civica_piani "
        "(corso, classe, articolazione, disciplina, dati) VALUES (?, ?, ?, ?, ?)",
        (corso, classe, articolazione, disciplina, json.dumps(dati)),
    )
    conn.commit()
    conn.close()


def _conteggio(percorso, query, parametri=()):
    conn = sqlite3.connect(percorso)
    try:
        return conn.execute(query, parametri).fetchone()[0]
    finally:
        conn.close()


def test_ripristino_master_aggiorna_corrente_e_conserva_admin(monkeypatch, tmp_path):
    master = tmp_path / "master.db"
    admin = tmp_path / "admin.db"
    corrente = tmp_path / "current" / "corrente.db"
    _crea_database(master)
    _crea_database(admin)
    _crea_database(corrente)
    _aggiungi_materia(master, 1, "MATEMATICA")
    _aggiungi_piano(
        master,
        "CAT",
        "PRIMA",
        "MATEMATICA",
        {"DOCENTE|MATEMATICA|M1|UD1": {"voci": ["LEGALITA"], "periodo": "PRIMO"}},
    )
    conn = sqlite3.connect(master)
    conn.execute("INSERT INTO ricevuti (nome_file, contenuto) VALUES ('file.ini', '{}')")
    conn.commit()
    conn.close()
    _aggiungi_materia(admin, 2, "MATERIA ADMIN")
    _aggiungi_materia(corrente, 3, "MATERIA CORRENTE")
    _aggiungi_piano(
        admin,
        "CAT",
        "PRIMA",
        "MATERIA ADMIN",
        {"DOCENTE|MATERIA ADMIN|M1|UD1": {"voci": ["LEGALITA"], "periodo": "PRIMO"}},
    )
    conn = sqlite3.connect(admin)
    conn.execute(
        "INSERT INTO pecup (id, tipo, codice, descrizione) "
        "VALUES (1, 'abilita', 'ADMTEST', 'Codice conservato in Admin')"
    )
    conn.execute(
        "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) "
        "VALUES (1, 'MATERIA ADMIN', 1, 1)"
    )
    conn.execute("INSERT INTO ricevuti (nome_file, contenuto) VALUES ('admin.ini', '{}')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "FILE_DB_MASTER", master)
    monkeypatch.setattr(db, "FILE_DB_MASTER_ALTERNATIVO", tmp_path / "master-alternativo.db")
    monkeypatch.setattr(db, "FILE_DB_ADMIN", admin)
    monkeypatch.setattr(db, "FILE_DB_ADMIN_ALTERNATIVO", tmp_path / "admin-alternativo.db")
    monkeypatch.setattr(db, "FILE_DB", corrente)
    monkeypatch.setattr(db, "CARTELLA_DATI", corrente.parent)

    assert db.ripristina_database_master()

    assert _conteggio(corrente, "SELECT COUNT(*) FROM discipline WHERE nome = 'MATEMATICA'") == 1
    assert _conteggio(corrente, "SELECT COUNT(*) FROM discipline WHERE nome LIKE 'MATERIA %'") == 0
    assert _conteggio(corrente, "SELECT COUNT(*) FROM ricevuti") == 0
    assert json.loads(_conteggio_json(corrente))["conferme"] == {}

    assert _conteggio(admin, "SELECT COUNT(*) FROM discipline WHERE nome = 'MATEMATICA'") == 0
    assert _conteggio(admin, "SELECT COUNT(*) FROM discipline WHERE nome = 'MATERIA ADMIN'") == 1
    assert _conteggio(admin, "SELECT COUNT(*) FROM pecup WHERE codice = 'ADMTEST'") == 1
    assert _conteggio(admin, "SELECT COUNT(*) FROM pecup_validita WHERE disciplina = 'MATERIA ADMIN'") == 1
    assert _conteggio(admin, "SELECT COUNT(*) FROM ricevuti") == 1
    assert json.loads(_conteggio_json(admin))["conferme"]
    assert _conteggio(master, "SELECT COUNT(*) FROM ricevuti") == 1
    assert json.loads(_conteggio_json(master))["conferme"]


def _conteggio_json(percorso):
    conn = sqlite3.connect(percorso)
    try:
        return conn.execute("SELECT dati FROM educazione_civica_piani").fetchone()[0]
    finally:
        conn.close()


def test_memorizza_pecup_aggiorna_catalogo_materie_senza_copiare_validita(monkeypatch, tmp_path):
    master = tmp_path / "master.db"
    admin = tmp_path / "admin.db"
    corrente = tmp_path / "corrente.db"
    for percorso in (master, admin, corrente):
        _crea_database(percorso)
    _aggiungi_materia(admin, 1, "MATEMATICA")
    _aggiungi_materia(corrente, 1, "MATEMATICA")
    _aggiungi_materia(corrente, 2, "NUOVA MATERIA", classe=2)

    for percorso in (admin, corrente):
        conn = sqlite3.connect(percorso)
        conn.execute(
            "INSERT INTO pecup (id, tipo, codice, descrizione) VALUES (1, 'abilita', 'MATC', 'Testo base')"
        )
        conn.execute(
            "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) "
            "VALUES (1, 'MATEMATICA', 1, 1)"
        )
        conn.commit()
        conn.close()
    conn = sqlite3.connect(corrente)
    conn.execute(
        "INSERT INTO pecup (id, tipo, codice, descrizione) VALUES (2, 'abilita', 'NUOC', 'Testo nuovo')"
    )
    conn.execute(
        "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) "
        "VALUES (2, 'NUOVA MATERIA', 2, 1)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "FILE_DB_MASTER", master)
    monkeypatch.setattr(db, "FILE_DB_MASTER_ALTERNATIVO", tmp_path / "missing-master.db")
    monkeypatch.setattr(db, "FILE_DB_ADMIN", admin)
    monkeypatch.setattr(db, "FILE_DB_ADMIN_ALTERNATIVO", tmp_path / "missing-admin.db")
    monkeypatch.setattr(db, "FILE_DB", corrente)
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)

    assert db.memorizza_pecup_factory()

    assert _conteggio(admin, "SELECT COUNT(*) FROM pecup") == 2
    assert _conteggio(admin, "SELECT COUNT(*) FROM discipline WHERE nome = 'NUOVA MATERIA'") == 1
    assert _conteggio(
        admin,
        "SELECT COUNT(*) FROM pecup_validita WHERE disciplina = 'NUOVA MATERIA'",
    ) == 0
    assert _conteggio(admin, "SELECT COUNT(*) FROM pecup_validita") == 1


def test_memorizza_educazione_civica_salva_quadro_senza_conferme(monkeypatch, tmp_path):
    master = tmp_path / "master.db"
    admin = tmp_path / "admin.db"
    corrente = tmp_path / "corrente.db"
    for percorso in (master, admin, corrente):
        _crea_database(percorso)
    _aggiungi_piano(admin, "CAT", "PRIMA", "ITALIANO")
    _aggiungi_piano(admin, "GRAFICO", "SECONDA", "STORIA")
    _aggiungi_piano(
        corrente,
        "CAT",
        "PRIMA",
        "ITALIANO",
        {"DOCENTE|ITALIANO|M1|UD1": {"voci": ["LEGALITA"], "periodo": "PRIMO"}},
    )
    conn = sqlite3.connect(admin)
    conn.execute(
        "INSERT INTO educazione_civica_backup (corso, classe, dump) "
        "VALUES ('CAT', 'PRIMA', ?)",
        (
            json.dumps(
                [
                    {
                        "articolazione": "COMUNE",
                        "disciplina": "PIANO PRECEDENTE",
                        "dati": json.dumps({"voci": [], "ore_disciplina": 0}),
                    }
                ]
            ),
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "FILE_DB_MASTER", master)
    monkeypatch.setattr(db, "FILE_DB_MASTER_ALTERNATIVO", tmp_path / "missing-master.db")
    monkeypatch.setattr(db, "FILE_DB_ADMIN", admin)
    monkeypatch.setattr(db, "FILE_DB_ADMIN_ALTERNATIVO", tmp_path / "missing-admin.db")
    monkeypatch.setattr(db, "FILE_DB", corrente)
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)

    assert db.memorizza_educazione_civica_factory("CAT", "PRIMA")

    assert _conteggio(admin, "SELECT COUNT(*) FROM educazione_civica_piani") == 2
    piani = sqlite3.connect(admin)
    try:
        dati = json.loads(
            piani.execute(
                "SELECT dati FROM educazione_civica_piani WHERE corso='CAT' AND classe='PRIMA'"
            ).fetchone()[0]
        )
    finally:
        piani.close()
    assert dati["voci"][0]["ore"] == 4
    assert dati["conferme"] == {}
    piani = sqlite3.connect(admin)
    try:
        snapshot = json.loads(
            piani.execute(
                "SELECT dump FROM educazione_civica_backup WHERE corso='CAT' AND classe='PRIMA'"
            ).fetchone()[0]
        )
    finally:
        piani.close()
    assert [(piano["disciplina"], json.loads(piano["dati"])["ore_disciplina"]) for piano in snapshot] == [
        ("ITALIANO", 4)
    ]
    assert json.loads(snapshot[0]["dati"])["conferme"] == {}
