"""Schema e accesso al database dei cataloghi (discipline, opzioni, codici PECUP).

I cataloghi sono in tabella e non nel codice: la futura pagina ADMIN di inserimento
di una nuova disciplina o di nuovi codici deve poter scrivere righe senza modifiche al codice.
"""

from __future__ import annotations

import sqlite3

from .config import CARTELLA_DATI, FILE_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS indirizzi (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    sigla TEXT NOT NULL,
    posizione INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS classi (
    numero INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS discipline (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    sigla TEXT NOT NULL,
    attende_ini INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS offerta_formativa (
    disciplina_id INTEGER NOT NULL REFERENCES discipline(id),
    indirizzo_id INTEGER NOT NULL REFERENCES indirizzi(id),
    classe INTEGER NOT NULL REFERENCES classi(numero),
    PRIMARY KEY (disciplina_id, indirizzo_id, classe)
);

CREATE TABLE IF NOT EXISTS opzioni (
    id INTEGER PRIMARY KEY,
    gruppo TEXT NOT NULL,
    posizione INTEGER NOT NULL,
    testo TEXT NOT NULL,
    testo_documento TEXT NOT NULL DEFAULT '',
    UNIQUE (gruppo, posizione)
);

CREATE TABLE IF NOT EXISTS competenze_ue (
    posizione INTEGER PRIMARY KEY,
    etichetta TEXT NOT NULL,
    titolo_documento TEXT NOT NULL,
    titolo_esteso TEXT NOT NULL DEFAULT '',
    descrizione TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS livelli_ue (
    posizione INTEGER NOT NULL REFERENCES competenze_ue(posizione) ON DELETE CASCADE,
    ordine INTEGER NOT NULL,
    etichetta TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    PRIMARY KEY (posizione, ordine)
);

CREATE TABLE IF NOT EXISTS pecup (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    codice TEXT NOT NULL,
    descrizione TEXT NOT NULL,
    UNIQUE (tipo, codice)
);

CREATE TABLE IF NOT EXISTS pecup_validita (
    pecup_id INTEGER NOT NULL REFERENCES pecup(id) ON DELETE CASCADE,
    disciplina TEXT NOT NULL,
    classe INTEGER NOT NULL,
    indirizzo_id INTEGER NOT NULL REFERENCES indirizzi(id),
    PRIMARY KEY (pecup_id, disciplina, classe, indirizzo_id)
);

CREATE INDEX IF NOT EXISTS idx_validita_ricerca
    ON pecup_validita (disciplina, classe, indirizzo_id);

-- Programmazioni inviate dai docenti: sostituisce il database.xlsx del VB6.
CREATE TABLE IF NOT EXISTS ricevuti (
    id INTEGER PRIMARY KEY,
    nome_file TEXT NOT NULL UNIQUE,
    data TEXT NOT NULL DEFAULT '',
    cognome TEXT NOT NULL DEFAULT '',
    nome TEXT NOT NULL DEFAULT '',
    classe TEXT NOT NULL DEFAULT '',
    indirizzo TEXT NOT NULL DEFAULT '',
    disciplina TEXT NOT NULL DEFAULT '',
    contenuto TEXT NOT NULL,
    importato_il TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_ricevuti_corso ON ricevuti (classe, indirizzo, disciplina);
"""


def connessione() -> sqlite3.Connection:
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(FILE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    crea_schema(conn)
    colonne = {riga["name"] for riga in conn.execute("PRAGMA table_info(discipline)")}
    if "attende_ini" not in colonne:
        conn.execute("ALTER TABLE discipline ADD COLUMN attende_ini INTEGER NOT NULL DEFAULT 0")
        # L'ultima materia del database esistente e' quella aggiunta dall'Admin in questa sessione.
        conn.execute("UPDATE discipline SET attende_ini = 1 WHERE id = (SELECT MAX(id) FROM discipline)")
        conn.commit()
    return conn


def inizializza_database() -> None:
    """Crea il database e ricostruisce il catalogo se manca del tutto."""
    database_nuovo = not FILE_DB.exists()
    with connessione() as conn:
        catalogo_vuoto = conn.execute("SELECT COUNT(*) FROM classi").fetchone()[0] == 0
    if database_nuovo or catalogo_vuoto:
        from tools.importa_cataloghi import main as importa_cataloghi

        if importa_cataloghi() != 0:
            raise RuntimeError("Impossibile ricostruire il catalogo di base.")


def resetta_database() -> None:
    """Svuota il database senza rimuovere il file, poi ricrea il catalogo base."""
    with connessione() as conn:
        tabelle = [
            riga["name"]
            for riga in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        conn.execute("PRAGMA foreign_keys = OFF")
        for tabella in tabelle:
            conn.execute(f'DROP TABLE "{tabella}"')
        conn.commit()
    from tools.importa_cataloghi import main as importa_cataloghi

    if importa_cataloghi() != 0:
        raise RuntimeError("Impossibile ricostruire il catalogo di base.")


def crea_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
