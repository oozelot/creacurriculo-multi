"""Allinea il factory alla situazione Civica del database operativo."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


RADICE = Path(__file__).resolve().parent.parent
OPERATIVO = RADICE / "dati" / "curricolo.db"
FACTORY = RADICE / "curricolobak.db"


def copia_tabella(destinazione: sqlite3.Connection, origine: sqlite3.Connection, nome: str) -> None:
    destinazione.execute(f'DELETE FROM "{nome}"')
    colonne = [riga[1] for riga in origine.execute(f'PRAGMA table_info("{nome}")')]
    segnaposto = ", ".join("?" for _ in colonne)
    righe = origine.execute(f'SELECT {", ".join(colonne)} FROM "{nome}"').fetchall()
    destinazione.executemany(
        f'INSERT INTO "{nome}" ({", ".join(colonne)}) VALUES ({segnaposto})',
        righe,
    )


def ricrea_snapshot(connessione: sqlite3.Connection) -> None:
    connessione.execute("DELETE FROM educazione_civica_backup")
    contesti = connessione.execute(
        "SELECT DISTINCT corso, classe FROM educazione_civica_piani ORDER BY corso, classe"
    ).fetchall()
    for corso, classe in contesti:
        piani = connessione.execute(
            "SELECT articolazione, disciplina, dati FROM educazione_civica_piani "
            "WHERE corso = ? AND classe = ? ORDER BY articolazione, disciplina",
            (corso, classe),
        ).fetchall()
        dump = __import__("json").dumps(
            [
                {"articolazione": riga[0], "disciplina": riga[1], "dati": riga[2]}
                for riga in piani
            ],
            ensure_ascii=False,
        )
        connessione.execute(
            "INSERT INTO educazione_civica_backup (corso, classe, dump) VALUES (?, ?, ?)",
            (corso, classe, dump),
        )


def main() -> None:
    sicurezza = FACTORY.with_name("curricolobak.prima-educazione-civica.db")
    shutil.copy2(FACTORY, sicurezza)
    try:
        with sqlite3.connect(OPERATIVO) as origine:
            ricrea_snapshot(origine)
            origine.commit()
        with sqlite3.connect(OPERATIVO) as origine, sqlite3.connect(FACTORY) as destinazione:
            destinazione.execute(
                """
                CREATE TABLE IF NOT EXISTS educazione_civica_backup (
                    corso TEXT NOT NULL,
                    classe TEXT NOT NULL,
                    dump TEXT NOT NULL,
                    aggiornato_il TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    PRIMARY KEY (corso, classe)
                )
                """
            )
            copia_tabella(destinazione, origine, "educazione_civica_piani")
            ricrea_snapshot(destinazione)
            destinazione.commit()
    except Exception:
        shutil.copy2(sicurezza, FACTORY)
        raise
    print(f"Factory aggiornato: {FACTORY}")
    print(f"Backup sicurezza: {sicurezza}")


if __name__ == "__main__":
    main()