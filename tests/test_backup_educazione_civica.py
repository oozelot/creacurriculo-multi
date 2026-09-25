from curricolo import db


def _inserisci_piano(corso, classe, disciplina, dati):
    with db.connessione() as conn:
        conn.execute(
            """
            INSERT INTO educazione_civica_piani
                (corso, classe, articolazione, disciplina, dati)
            VALUES (?, ?, 'COMUNE', ?, ?)
            """,
            (corso, classe, disciplina, dati),
        )
        conn.commit()


def test_ripristina_educazione_civica_sostituisce_lo_stato(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "CARTELLA_DATI", tmp_path)
    monkeypatch.setattr(db, "FILE_DB", tmp_path / "curricolo.db")

    _inserisci_piano("CAT", "PRIMA", "ITALIANO", '{"voci": [{"ore": 33}]}')
    _inserisci_piano("GRAFICO", "SECONDA", "MATEMATICA", '{"voci": [{"ore": 34}]}')
    db.backup_educazione_civica("CAT", "PRIMA")
    db.backup_educazione_civica("GRAFICO", "SECONDA")

    with db.connessione() as conn:
        conn.execute("DELETE FROM educazione_civica_piani")
        conn.execute(
            "INSERT INTO educazione_civica_piani (corso, classe, articolazione, disciplina, dati) "
            "VALUES ('AGRARIO', 'TERZA', 'COMUNE', 'STORIA', '{\"voci\": [{\"ore\": 99}]}')"
        )
        conn.commit()

    assert db.ripristina_educazione_civica_backup()
    with db.connessione() as conn:
        piani = conn.execute(
            "SELECT corso, classe, disciplina, dati FROM educazione_civica_piani "
            "ORDER BY corso, classe, disciplina"
        ).fetchall()

    assert [(r["corso"], r["classe"], r["disciplina"]) for r in piani] == [
        ("CAT", "PRIMA", "ITALIANO"),
        ("GRAFICO", "SECONDA", "MATEMATICA"),
    ]