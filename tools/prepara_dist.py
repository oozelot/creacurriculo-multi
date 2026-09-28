"""Prepara gli archivi iniziali, senza dati Correnti o file INI ricevuti."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from curricolo import db
from curricolo.config import FILE_DB_ADMIN, FILE_DB_MASTER_ALTERNATIVO


def _copia_archivio_pulito(origine: Path, destinazione: Path) -> None:
    if not origine.is_file():
        raise FileNotFoundError(f"Archivio di distribuzione mancante: {origine}")
    temporaneo = db._prepara_copia_archivio(origine, destinazione)
    temporaneo.replace(destinazione)


def _verifica_archivio(percorso: Path) -> None:
    with sqlite3.connect(percorso) as conn:
        integrita = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrita != "ok":
            raise sqlite3.DatabaseError(f"Archivio non integro ({percorso}): {integrita}")
        ricevuti = conn.execute("SELECT COUNT(*) FROM ricevuti").fetchone()[0]
        if ricevuti:
            raise ValueError(f"L'archivio {percorso} contiene {ricevuti} file INI ricevuti.")


def prepara_distribuzione(destinazione: Path) -> None:
    destinazione = destinazione.resolve()
    eseguibili = ("CreaCurricoloMulti.exe", "CreaCurricoloMulti")
    if not destinazione.is_dir() or not any((destinazione / nome).is_file() for nome in eseguibili):
        raise FileNotFoundError(f"Cartella PyInstaller non valida: {destinazione}")
    if not (destinazione / "_internal").is_dir():
        raise FileNotFoundError(f"Risorse PyInstaller mancanti in {destinazione}")

    voci_attese = {"_internal", "curricolobak.db", "curricolobak-modificato.db"}
    voci_attese.update(nome for nome in eseguibili if (destinazione / nome).is_file())
    inattese = {percorso.name for percorso in destinazione.iterdir()} - voci_attese
    if inattese:
        raise ValueError(f"La distribuzione contiene file o cartelle extra: {sorted(inattese)}")
    if (destinazione / "dati" / "curricolo.db").exists():
        raise ValueError("Il database Corrente non deve essere incluso nella distribuzione.")

    _copia_archivio_pulito(FILE_DB_MASTER_ALTERNATIVO, destinazione / "curricolobak.db")
    master_interno = destinazione / "_internal" / "curricolobak.db"
    if master_interno.is_file():
        _copia_archivio_pulito(FILE_DB_MASTER_ALTERNATIVO, master_interno)
    _copia_archivio_pulito(FILE_DB_ADMIN, destinazione / "curricolobak-modificato.db")

    _verifica_archivio(destinazione / "curricolobak.db")
    if master_interno.is_file():
        _verifica_archivio(master_interno)
    _verifica_archivio(destinazione / "curricolobak-modificato.db")

    cartella_ricevuti = destinazione / "_internal" / "ADMIN" / "file_ricevuti"
    if cartella_ricevuti.exists() and any(cartella_ricevuti.glob("*.ini")):
        raise ValueError("La distribuzione non deve contenere file INI ricevuti come seed.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python tools/prepara_dist.py <cartella-distribuzione>")
    prepara_distribuzione(Path(sys.argv[1]))
