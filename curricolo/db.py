"""Schema e accesso al database dei cataloghi (discipline, opzioni, codici PECUP).

I cataloghi sono in tabella e non nel codice: la futura pagina ADMIN di inserimento
di una nuova disciplina o di nuovi codici deve poter scrivere righe senza modifiche al codice.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import unicodedata

from .config import (
    CARTELLA_DATI,
    FILE_DB,
    FILE_DB_FACTORY,
    FILE_DB_FACTORY_ALTERNATIVO,
    FILE_DB_MASTER,
    FILE_DB_MASTER_ALTERNATIVO,
)

SIGLE_INI_STORICHE = {
    "ALT": "ALTER", "BTC": "BIOTA", "BTV": "BIOTV", "CMT": "COMPM",
    "DIR": "DIRIT", "ENO": "ENOLO", "EST": "ESTIM", "FIS": "FISIC",
    "GAT": "GATER", "GNR": "GENRU", "GEO": "GEOGR", "GEE": "GEOPE",
    "GCS": "GESIC", "INF": "INFOR", "ING": "INGLE", "ITA": "ITALI",
    "LTC": "LABTC", "MAT": "MATEM", "OGP": "ORGPP", "PCI": "PCIMP",
    "PAN": "PRANI", "PRM": "PRMUL", "PVG": "PRVEG", "REL": "RELIG",
    "SCI": "SCBIO", "SCM": "SCMOT", "STA": "STAPP", "STO": "STORI",
    "TCM": "TCOMU", "TPG": "TOPOG", "TPP": "TPRPR", "TRG": "TTRGR",
    "TRP": "TRPRO", "VIT": "VITIC",
}


class ConnessioneSQLite(sqlite3.Connection):
    """Connessione che chiude il file anche quando usata con ``with``."""

    def __exit__(self, tipo, valore, traccia):
        try:
            return super().__exit__(tipo, valore, traccia)
        finally:
            self.close()

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
    sigla_ini TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS pecup_backup (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    dump TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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

-- Piano di educazione civica predisposto dall'Admin e conferme dei docenti.
CREATE TABLE IF NOT EXISTS educazione_civica_piani (
    corso TEXT NOT NULL,
    classe TEXT NOT NULL,
    articolazione TEXT NOT NULL DEFAULT '',
    disciplina TEXT NOT NULL,
    dati TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (corso, classe, articolazione, disciplina)
);

CREATE INDEX IF NOT EXISTS idx_ec_piani_contesto
    ON educazione_civica_piani (corso, classe, articolazione);

CREATE TABLE IF NOT EXISTS educazione_civica_catalogo (
    macroarea TEXT NOT NULL,
    voce TEXT NOT NULL,
    posizione INTEGER NOT NULL,
    PRIMARY KEY (macroarea, voce)
);

CREATE TABLE IF NOT EXISTS educazione_civica_backup (
    corso TEXT NOT NULL,
    classe TEXT NOT NULL,
    dump TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (corso, classe)
);
"""


def connessione() -> sqlite3.Connection:
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(FILE_DB, factory=ConnessioneSQLite)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    crea_schema(conn)
    colonne = {riga["name"] for riga in conn.execute("PRAGMA table_info(discipline)")}
    if "sigla_ini" not in colonne:
        conn.execute("ALTER TABLE discipline ADD COLUMN sigla_ini TEXT NOT NULL DEFAULT ''")
        for sigla, alias in SIGLE_INI_STORICHE.items():
            conn.execute("UPDATE discipline SET sigla_ini = ? WHERE sigla = ?", (alias, sigla))
        conn.execute(
            "UPDATE discipline SET sigla_ini = upper(substr(replace(replace(nome, ' ', ''), '.', ''), 1, 5)) WHERE sigla_ini = ''"
        )
        conn.commit()
    if "attende_ini" not in colonne:
        conn.execute("ALTER TABLE discipline ADD COLUMN attende_ini INTEGER NOT NULL DEFAULT 0")
        # L'ultima materia del database esistente e' quella aggiunta dall'Admin in questa sessione.
        conn.execute("UPDATE discipline SET attende_ini = 1 WHERE id = (SELECT MAX(id) FROM discipline)")
        conn.commit()
    return conn


def sigla_ini_da_nome(nome: str) -> str:
    """Genera un alias di cinque caratteri leggibile per i file INI."""
    normalizzato = unicodedata.normalize("NFKD", str(nome or ""))
    normalizzato = "".join(carattere for carattere in normalizzato if not unicodedata.combining(carattere))
    lettere = re.sub(r"[^A-Z0-9]", "", normalizzato.upper())
    return (lettere + "XXXXX")[:5]


def sigla_ini_da_sigla(sigla: str, nome: str) -> str:
    return SIGLE_INI_STORICHE.get(str(sigla or "").strip().upper(), sigla_ini_da_nome(nome))


def _percorso_master() -> str | None:
    for percorso in (FILE_DB_MASTER, FILE_DB_MASTER_ALTERNATIVO):
        if percorso.is_file():
            return str(percorso)
    return None


def _inizializza_archivio_factory() -> str | None:
    if FILE_DB_FACTORY.is_file():
        _svuota_archivio_ricevuti(FILE_DB_FACTORY)
        return str(FILE_DB_FACTORY)
    master = _percorso_master()
    if master is None:
        return None
    FILE_DB_FACTORY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(master, FILE_DB_FACTORY)
    _svuota_archivio_ricevuti(FILE_DB_FACTORY)
    return str(FILE_DB_FACTORY)


def _svuota_archivio_ricevuti(percorso: str | os.PathLike[str]) -> None:
    conn = sqlite3.connect(percorso)
    try:
        conn.execute("DELETE FROM ricevuti")
        conn.commit()
    finally:
        conn.close()


def _copia_tabelle_da_operativo(tabelle: tuple[str, ...]) -> bool:
    factory = _inizializza_archivio_factory()
    if factory is None:
        return False
    origine = sqlite3.connect(FILE_DB)
    destinazione = sqlite3.connect(factory)
    try:
        origine.row_factory = sqlite3.Row
        for tabella in reversed(tabelle):
            colonne = [riga["name"] for riga in origine.execute(f'PRAGMA table_info("{tabella}")')]
            if not colonne:
                continue
            destinazione.execute(f'DELETE FROM "{tabella}"')
        for tabella in tabelle:
            colonne = [riga["name"] for riga in origine.execute(f'PRAGMA table_info("{tabella}")')]
            if not colonne:
                continue
            valori = [tuple(riga[colonna] for colonna in colonne) for riga in origine.execute(f'SELECT * FROM "{tabella}"')]
            segnaposto = ", ".join("?" for _ in colonne)
            destinazione.executemany(
                f'INSERT INTO "{tabella}" ({", ".join(colonne)}) VALUES ({segnaposto})',
                valori,
            )
        destinazione.commit()
    finally:
        origine.close()
        destinazione.close()
    return True


def inizializza_database() -> None:
    """Crea il database e ricostruisce il catalogo se manca del tutto."""
    factory = _inizializza_archivio_factory()
    database_nuovo = not FILE_DB.exists()
    if database_nuovo and factory is not None:
        CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
        shutil.copy2(factory, FILE_DB)
        database_nuovo = False
    with connessione() as conn:
        catalogo_vuoto = conn.execute("SELECT COUNT(*) FROM classi").fetchone()[0] == 0
    if database_nuovo or catalogo_vuoto:
        from tools.importa_cataloghi import main as importa_cataloghi

        if importa_cataloghi() != 0:
            raise RuntimeError("Impossibile ricostruire il catalogo di base.")
    from . import educazione_civica
    educazione_civica.sincronizza_catalogo_file()
    _inizializza_educazione_civica_factory()
    inizializza_backup_stato()


def inizializza_backup_stato() -> None:
    """Crea gli snapshot iniziali se il database non ne possiede ancora."""
    with connessione() as conn:
        pecup_backup = conn.execute("SELECT 1 FROM pecup_backup WHERE id = 1").fetchone()
        contesti = conn.execute(
            "SELECT DISTINCT corso, classe FROM educazione_civica_piani"
        ).fetchall()
        backup_civica = {
            (riga["corso"], riga["classe"])
            for riga in conn.execute(
                "SELECT corso, classe FROM educazione_civica_backup"
            )
        }
    if pecup_backup is None:
        backup_pecup_attuali()
    for riga in contesti:
        if (riga["corso"], riga["classe"]) not in backup_civica:
            backup_educazione_civica(riga["corso"], riga["classe"])


def _inizializza_educazione_civica_factory() -> None:
    """Importa i piani base quando il database operativo e' ancora vuoto."""
    with connessione() as conn:
        piani_presenti = conn.execute("SELECT 1 FROM educazione_civica_piani LIMIT 1").fetchone()
        backup_presente = conn.execute("SELECT 1 FROM educazione_civica_backup LIMIT 1").fetchone()
    if piani_presenti is None and backup_presente is None:
        _ripristina_educazione_civica_da_factory()


def _sostituisci_operativo_da_archivio(archivio: str, preserva_ricevuti: bool) -> bool:
    if not os.path.isfile(archivio):
        return False
    ricevuti = []
    if preserva_ricevuti and FILE_DB.is_file():
        conn = sqlite3.connect(FILE_DB)
        try:
            conn.row_factory = sqlite3.Row
            ricevuti = [dict(riga) for riga in conn.execute("SELECT * FROM ricevuti")]
        finally:
            conn.close()
    temporaneo = FILE_DB.with_name(f"{FILE_DB.name}.restore.tmp")
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archivio, temporaneo)
    os.replace(temporaneo, FILE_DB)
    if ricevuti:
        with connessione() as conn:
            colonne = list(ricevuti[0])
            segnaposto = ", ".join("?" for _ in colonne)
            conn.executemany(
                f'INSERT OR IGNORE INTO ricevuti ({", ".join(colonne)}) VALUES ({segnaposto})',
                [tuple(riga[colonna] for colonna in colonne) for riga in ricevuti],
            )
            conn.commit()
    return True


def resetta_database() -> None:
    """Azzera i dati locali e ricrea anche la configurazione civica iniziale."""
    if not ripristina_database_factory():
        raise RuntimeError("Impossibile ripristinare il factory modificato.")


def ripristina_database_factory() -> bool:
    """Copia il secondo archivio sul database operativo."""
    factory = _inizializza_archivio_factory()
    if factory is None:
        return False
    return _sostituisci_operativo_da_archivio(factory, preserva_ricevuti=False)


def ripristina_database_master() -> bool:
    """Copia il master sul secondo archivio e poi sul database operativo."""
    master = _percorso_master()
    if master is None:
        return False
    FILE_DB_FACTORY.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = FILE_DB_FACTORY.with_name(f"{FILE_DB_FACTORY.name}.master.tmp")
    shutil.copy2(master, temporaneo)
    os.replace(temporaneo, FILE_DB_FACTORY)
    _svuota_archivio_ricevuti(FILE_DB_FACTORY)
    return _sostituisci_operativo_da_archivio(str(FILE_DB_FACTORY), preserva_ricevuti=False)


def memorizza_pecup_factory() -> bool:
    """Aggiorna nel secondo archivio i codici PECUP dell'operativo."""
    return _copia_tabelle_da_operativo(("pecup", "pecup_validita"))


def memorizza_educazione_civica_factory(corso: str, classe: str) -> bool:
    """Aggiorna nel secondo archivio il piano civico indicato."""
    factory = _inizializza_archivio_factory()
    if factory is None:
        return False
    origine = sqlite3.connect(FILE_DB)
    destinazione = sqlite3.connect(factory)
    try:
        origine.row_factory = sqlite3.Row
        destinazione.execute(
            "DELETE FROM educazione_civica_piani WHERE corso = ? AND classe = ?",
            (corso, classe),
        )
        righe = origine.execute(
            "SELECT articolazione, disciplina, dati FROM educazione_civica_piani WHERE corso = ? AND classe = ?",
            (corso, classe),
        ).fetchall()
        destinazione.executemany(
            "INSERT INTO educazione_civica_piani (corso, classe, articolazione, disciplina, dati) VALUES (?, ?, ?, ?, ?)",
            [(corso, classe, riga["articolazione"], riga["disciplina"], riga["dati"]) for riga in righe],
        )
        destinazione.commit()
    finally:
        origine.close()
        destinazione.close()
    return True


def backup_pecup_attuali() -> None:
    """Salva lo stato corrente dei codici PECUP in un backup riservato all'app."""
    with connessione() as conn:
        pecup = [
            {"id": riga["id"], "tipo": riga["tipo"], "codice": riga["codice"], "descrizione": riga["descrizione"]}
            for riga in conn.execute("SELECT id, tipo, codice, descrizione FROM pecup ORDER BY id")
        ]
        validita = [
            {"pecup_id": riga["pecup_id"], "disciplina": riga["disciplina"], "classe": riga["classe"], "indirizzo_id": riga["indirizzo_id"]}
            for riga in conn.execute("SELECT pecup_id, disciplina, classe, indirizzo_id FROM pecup_validita ORDER BY pecup_id, disciplina, classe, indirizzo_id")
        ]
        conn.execute(
            "INSERT INTO pecup_backup (id, dump, aggiornato_il) VALUES (1, ?, datetime('now', 'localtime')) ON CONFLICT(id) DO UPDATE SET dump = excluded.dump, aggiornato_il = excluded.aggiornato_il",
            (json.dumps({"pecup": pecup, "validita": validita}, ensure_ascii=False),),
        )
        conn.commit()


def ripristina_pecup_backup() -> bool:
    """Ripristina i codici PECUP dal backup riservato all'app."""
    with connessione() as conn:
        riga = conn.execute("SELECT dump FROM pecup_backup WHERE id = 1").fetchone()
        if riga is None:
            return False
        backup = json.loads(riga["dump"])
        conn.execute("DELETE FROM pecup_validita")
        conn.execute("DELETE FROM pecup")
        for voce in backup.get("pecup", []):
            conn.execute(
                "INSERT INTO pecup (id, tipo, codice, descrizione) VALUES (?, ?, ?, ?)",
                (voce["id"], voce["tipo"], voce["codice"], voce["descrizione"]),
            )
        for voce in backup.get("validita", []):
            conn.execute(
                "INSERT INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) VALUES (?, ?, ?, ?)",
                (voce["pecup_id"], voce["disciplina"], voce["classe"], voce["indirizzo_id"]),
            )
        conn.commit()
    return True


def backup_educazione_civica(corso: str, classe: str) -> None:
    """Salva l'ultima situazione del piano per corso e anno."""
    with connessione() as conn:
        piani = [
            dict(riga)
            for riga in conn.execute(
                "SELECT articolazione, disciplina, dati FROM educazione_civica_piani WHERE corso = ? AND classe = ? ORDER BY articolazione, disciplina",
                (corso, classe),
            )
        ]
        conn.execute(
            """
            INSERT INTO educazione_civica_backup (corso, classe, dump, aggiornato_il)
            VALUES (?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(corso, classe) DO UPDATE SET
                dump = excluded.dump,
                aggiornato_il = excluded.aggiornato_il
            """,
            (corso, classe, json.dumps(piani, ensure_ascii=False)),
        )
        conn.commit()
def ripristina_educazione_civica_backup() -> bool:
    """Ripristina tutti i piani dagli ultimi snapshot memorizzati."""
    with connessione() as conn:
        righe = conn.execute("SELECT corso, classe, dump FROM educazione_civica_backup").fetchall()
    if not righe:
        return _ripristina_educazione_civica_da_factory()
    with connessione() as conn:
        conn.execute("DELETE FROM educazione_civica_piani")
        for riga in righe:
            for piano in json.loads(riga["dump"]):
                conn.execute(
                    "INSERT INTO educazione_civica_piani (corso, classe, articolazione, disciplina, dati) VALUES (?, ?, ?, ?, ?)",
                    (riga["corso"], riga["classe"], piano["articolazione"], piano["disciplina"], piano["dati"]),
                )
        conn.commit()
    return True


def ripristina_educazione_civica_factory() -> bool:
    """Ripristina la configurazione iniziale civica dal database factory."""
    return _ripristina_educazione_civica_da_factory()


def _ripristina_educazione_civica_da_factory() -> bool:
    """Ricostruisce i piani civici dal factory se manca lo snapshot operativo."""
    factory = next(
        (percorso for percorso in (FILE_DB_FACTORY, FILE_DB_FACTORY_ALTERNATIVO) if percorso.is_file()),
        None,
    )
    if factory is None:
        return False
    with sqlite3.connect(factory) as origine:
        origine.row_factory = sqlite3.Row
        piani = origine.execute(
            "SELECT corso, classe, articolazione, disciplina, dati FROM educazione_civica_piani"
        ).fetchall()
    with connessione() as conn:
        conn.execute("DELETE FROM educazione_civica_piani")
        conn.executemany(
            "INSERT INTO educazione_civica_piani "
            "(corso, classe, articolazione, disciplina, dati) VALUES (?, ?, ?, ?, ?)",
            [
                (riga["corso"], riga["classe"], riga["articolazione"], riga["disciplina"], riga["dati"])
                for riga in piani
            ],
        )
        conn.commit()
    inizializza_backup_stato()
    return bool(piani)


def crea_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
