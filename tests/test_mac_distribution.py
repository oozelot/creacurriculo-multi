import json
import sqlite3

from curricolo import db
from tools import prepara_dist


def _crea_archivio(percorso):
    with sqlite3.connect(percorso) as conn:
        conn.executescript(db.SCHEMA)
        conn.execute("INSERT INTO indirizzi (id, nome, sigla, posizione) VALUES (1, 'COMUNE', 'COM', 1)")
        conn.execute("INSERT INTO classi (numero, nome) VALUES (1, 'PRIMA')")
        conn.execute("INSERT INTO discipline (id, nome, sigla) VALUES (1, 'CHIMICA', 'CHI')")
        conn.execute("INSERT INTO pecup (id, tipo, codice, descrizione) VALUES (1, 'abilita', 'CHITBIEABP01', 'Abilita')")
        conn.execute(
            "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) VALUES (1, 'CHIMICA', 1, 1)"
        )
        conn.execute(
            "INSERT INTO ricevuti (nome_file, contenuto) VALUES ('docente.ini', 'dati operativi')"
        )
        dati = json.dumps({"conferme": {"docente": "confermato"}, "voci": []})
        conn.execute(
            "INSERT INTO educazione_civica_piani (corso, classe, disciplina, dati) VALUES ('CAT', 'PRIMA', 'CHIMICA', ?)",
            (dati,),
        )


def test_pacchetto_macos_usa_archivi_memorizzati_senza_corrente_o_ini(monkeypatch, tmp_path):
    admin = tmp_path / "admin.db"
    master = tmp_path / "master.db"
    _crea_archivio(admin)
    _crea_archivio(master)
    monkeypatch.setattr(prepara_dist, "FILE_DB_ADMIN", admin)
    monkeypatch.setattr(prepara_dist, "FILE_DB_MASTER_ALTERNATIVO", master)
    distribuzione = tmp_path / "CreaCurricoloMulti"

    prepara_dist.prepara_distribuzione_macos(distribuzione)

    assert (distribuzione / "Avvia CreaCurricolo.command").is_file()
    launcher = (distribuzione / "Avvia CreaCurricolo.command").read_text(encoding="utf-8")
    ramo_python_mancante = launcher.split('if [[ ! -x ".venv/bin/python" ]]')[0]
    assert "display dialog" in ramo_python_mancante
    assert "Apri download ufficiali" in ramo_python_mancante
    assert "https://www.python.org/downloads/macos/" in ramo_python_mancante
    assert "read -r -p" not in launcher
    assert (distribuzione / "curricolobak.db").is_file()
    assert (distribuzione / "curricolobak-modificato.db").is_file()
    assert not (distribuzione / "dati" / "curricolo.db").exists()
    assert not (distribuzione / "DIPARTIMENTO_DIRITTO").exists()
    with sqlite3.connect(distribuzione / "curricolobak-modificato.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM ricevuti").fetchone()[0] == 0
        piano = conn.execute("SELECT dati FROM educazione_civica_piani").fetchone()[0]
        assert json.loads(piano)["conferme"] == {}
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
