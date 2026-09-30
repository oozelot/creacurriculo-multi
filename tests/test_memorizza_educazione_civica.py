import json
import sqlite3

from curricolo import db


def _crea_database(percorso):
    conn = sqlite3.connect(percorso)
    db.crea_schema(conn)
    conn.commit()
    conn.close()


def _inserisci_piano(percorso, corso, classe, disciplina, conferme):
    dati = {
        "macroarea": "COSTITUZIONE",
        "voci": [
            {
                "macroarea": "COSTITUZIONE",
                "voce": "LEGALITA",
                "ore": 35,
            }
        ],
        "ore_disciplina": 35,
        "conferme": conferme,
    }
    conn = sqlite3.connect(percorso)
    conn.execute(
        "INSERT INTO educazione_civica_piani "
        "(corso, classe, articolazione, disciplina, dati) "
        "VALUES (?, ?, 'COMUNE', ?, ?)",
        (corso, classe, disciplina, json.dumps(dati)),
    )
    conn.commit()
    conn.close()


def test_memorizza_educazione_civica_sostituisce_tutti_i_piani_e_backup(
    monkeypatch, tmp_path
):
    master = tmp_path / "master.db"
    admin = tmp_path / "admin.db"
    corrente = tmp_path / "corrente.db"
    for percorso in (master, admin, corrente):
        _crea_database(percorso)

    _inserisci_piano(admin, "AGRARIO", "QUINTA", "PIANO OBSOLETO", {})
    _inserisci_piano(
        corrente,
        "CAT",
        "PRIMA",
        "CHIMICA",
        {"conferma docente": {"periodo": "I"}},
    )
    _inserisci_piano(
        corrente,
        "GRAFICO",
        "SECONDA",
        "FISICA",
        {"conferma docente": {"periodo": "II"}},
    )

    monkeypatch.setattr(db, "FILE_DB_MASTER", master)
    monkeypatch.setattr(db, "FILE_DB_MASTER_ALTERNATIVO", tmp_path / "missing-master.db")
    monkeypatch.setattr(db, "FILE_DB_ADMIN", admin)
    monkeypatch.setattr(db, "FILE_DB_ADMIN_ALTERNATIVO", tmp_path / "missing-admin.db")
    monkeypatch.setattr(db, "FILE_DB", corrente)
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)

    assert db.memorizza_educazione_civica_factory()

    conn = sqlite3.connect(admin)
    try:
        piani = conn.execute(
            "SELECT corso, classe, disciplina, dati FROM educazione_civica_piani "
            "ORDER BY corso, classe"
        ).fetchall()
        snapshot = conn.execute(
            "SELECT corso, classe, dump FROM educazione_civica_backup "
            "ORDER BY corso, classe"
        ).fetchall()
    finally:
        conn.close()

    assert [(corso, classe, disciplina) for corso, classe, disciplina, _ in piani] == [
        ("CAT", "PRIMA", "CHIMICA"),
        ("GRAFICO", "SECONDA", "FISICA"),
    ]
    for _, _, _, contenuto in piani:
        dati = json.loads(contenuto)
        assert sum(voce["ore"] for voce in dati["voci"]) == 35
        assert dati["conferme"] == {}
    assert [(corso, classe) for corso, classe, _ in snapshot] == [
        ("CAT", "PRIMA"),
        ("GRAFICO", "SECONDA"),
    ]
