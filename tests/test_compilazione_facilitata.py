import sqlite3

from curricolo import catalogo


def test_codici_sicurezza_biennio_include_solo_codici_sic(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE pecup (id INTEGER PRIMARY KEY, tipo TEXT, codice TEXT, descrizione TEXT);
        CREATE TABLE pecup_validita (pecup_id INTEGER, disciplina TEXT, classe INTEGER);
        INSERT INTO pecup VALUES
            (1, 'abilita', 'SICTBIEABP01', 'Corretta scelta degli strumenti DPI da utilizzare.'),
            (2, 'abilita', 'CHITBIEABP01', 'Sicurezza nei laboratori di chimica.'),
            (3, 'abilita', 'SIC345ABP01', 'Sicurezza nel secondo biennio.');
        INSERT INTO pecup_validita VALUES
            (1, 'CHIMICA', 1),
            (1, 'FISICA', 2),
            (2, 'CHIMICA', 1),
            (3, 'CHIMICA', 3);
        """
    )
    monkeypatch.setattr(catalogo, "connessione", lambda: conn)

    voci = catalogo.codici_sicurezza_biennio("abilita")

    assert [voce["codice"] for voce in voci] == ["SICTBIEABP01"]
