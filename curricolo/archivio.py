"""Archivio delle programmazioni ricevute dai docenti (modalita' ADMIN).

Sostituisce il database.xlsx del VB6 con una tabella: ogni riga e' un file INI
ricevuto, con i dati identificativi e la programmazione completa in JSON.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from . import esporta_ini, importa_ini
from .config import CARTELLA_RICEVUTI, CLASSI, INDIRIZZI
from .db import connessione
from .modello import Programmazione


def file_ricevuti() -> list[Path]:
    if not CARTELLA_RICEVUTI.exists():
        return []
    return sorted(CARTELLA_RICEVUTI.glob("*.ini"), key=lambda p: p.name.lower())


def gia_importati() -> set[str]:
    with connessione() as conn:
        return {r["nome_file"] for r in conn.execute("SELECT nome_file FROM ricevuti")}


def importa(percorso: Path) -> int:
    """Inserisce o aggiorna la programmazione contenuta in un file ricevuto."""
    prog = importa_ini.leggi_file(percorso)
    contenuto = json.dumps(prog.come_dict(), ensure_ascii=False)
    with connessione() as conn:
        conn.execute(
            """
            INSERT INTO ricevuti (nome_file, data, cognome, nome, classe, indirizzo,
                                  disciplina, contenuto)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (nome_file) DO UPDATE SET
                 data = excluded.data, cognome = excluded.cognome, nome = excluded.nome,
                 classe = excluded.classe, indirizzo = excluded.indirizzo,
                 disciplina = excluded.disciplina, contenuto = excluded.contenuto,
                 importato_il = datetime('now', 'localtime')
            """,
            (
                percorso.name,
                importa_ini.data_documento(percorso),
                prog.cognome,
                prog.nome,
                prog.classe,
                prog.indirizzo,
                prog.disciplina,
                contenuto,
            ),
        )
        conn.commit()
        riga = conn.execute(
            "SELECT id FROM ricevuti WHERE nome_file = ?", (percorso.name,)
        ).fetchone()
        return int(riga["id"])


def leggi_file(percorso: Path) -> Programmazione:
    """Legge un file ricevuto per le azioni ADMIN senza alterare l'archivio."""
    return importa_ini.leggi_file(percorso)


def importa_tutti(sostituisci: bool = True) -> tuple[int, list[str]]:
    """Importa tutti i file e restituisce quanti sono stati elaborati e saltati."""
    importati = gia_importati()
    saltati = [percorso.name for percorso in file_ricevuti() if percorso.name in importati]
    percorsi = file_ricevuti() if sostituisci else [
        percorso for percorso in file_ricevuti() if percorso.name not in importati
    ]
    return sum(1 for percorso in percorsi if importa(percorso)), saltati


def elenca(classe: str = "", indirizzo: str = "", disciplina: str = "") -> list[dict[str, Any]]:
    condizioni, parametri = [], []
    for colonna, valore in (
        ("classe", classe),
        ("indirizzo", indirizzo),
        ("disciplina", disciplina),
    ):
        if valore:
            condizioni.append(f"{colonna} = ?")
            parametri.append(valore)
    filtro = f"WHERE {' AND '.join(condizioni)}" if condizioni else ""

    with connessione() as conn:
        righe = conn.execute(
            f"""
            SELECT id, nome_file, data, cognome, nome, classe, indirizzo, disciplina, importato_il
              FROM ricevuti {filtro}
             ORDER BY disciplina, classe, cognome, nome
            """,
            parametri,
        )
        return [dict(r) for r in righe]


def programmazione(identificativo: int) -> Programmazione | None:
    with connessione() as conn:
        riga = conn.execute(
            "SELECT contenuto FROM ricevuti WHERE id = ?", (identificativo,)
        ).fetchone()
    if riga is None:
        return None
    return Programmazione.da_dict(json.loads(riga["contenuto"]))


def elimina(identificativo: int) -> bool:
    with connessione() as conn:
        modificate = conn.execute(
            "DELETE FROM ricevuti WHERE id = ?", (identificativo,)
        ).rowcount
        conn.commit()
    return modificate > 0


def esporta_su_file(identificativo: int) -> Path | None:
    """Riscrive un record dell'archivio come file INI in ADMIN/file_ricevuti."""
    prog = programmazione(identificativo)
    if prog is None:
        return None
    with connessione() as conn:
        riga = conn.execute("SELECT data FROM ricevuti WHERE id = ?", (identificativo,)).fetchone()
    giorno = _data(riga["data"] if riga else "")

    CARTELLA_RICEVUTI.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA_RICEVUTI / esporta_ini.nome_file_invio(prog, giorno)
    contenuto = "\r\n".join(esporta_ini.genera_righe(prog, giorno)) + "\r\n"
    percorso.write_bytes(contenuto.encode("cp1252", errors="replace"))
    return percorso


def _data(testo: str) -> date:
    try:
        return date(2000 + int(testo[6:8]), int(testo[3:5]), int(testo[0:2]))
    except (ValueError, IndexError):
        return date.today()


def completamento() -> dict[tuple[str, str, str], int]:
    """Quanti record ci sono per ogni combinazione disciplina/classe/indirizzo."""
    with connessione() as conn:
        righe = conn.execute(
            "SELECT classe, indirizzo, disciplina, COUNT(*) AS quanti"
            "  FROM ricevuti GROUP BY classe, indirizzo, disciplina"
        )
        return {(r["disciplina"], r["classe"], r["indirizzo"]): r["quanti"] for r in righe}


def unita_per_competenza(classe: str, indirizzi: list[str]) -> dict[int, list[dict[str, Any]]]:
    """Unita' didattiche che concorrono a ciascuna competenza in chiave europea."""
    trovate: dict[int, list[dict[str, Any]]] = {}
    for record in elenca(classe=classe):
        if record["indirizzo"] not in indirizzi:
            continue
        prog = programmazione(record["id"])
        if prog is None:
            continue
        for modulo in prog.moduli:
            for unita in modulo.unita:
                for posizione in unita.competenze_europee:
                    trovate.setdefault(posizione, []).append(
                        {"programmazione": prog, "modulo": modulo, "unita": unita}
                    )
    return trovate


def aree_multidisciplinari(classe: str, indirizzi: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Unita' didattiche raggruppate per area multidisciplinare dichiarata."""
    trovate: dict[str, list[dict[str, Any]]] = {}
    for record in elenca(classe=classe):
        if record["indirizzo"] not in indirizzi:
            continue
        prog = programmazione(record["id"])
        if prog is None:
            continue
        for modulo in prog.moduli:
            for unita in modulo.unita:
                for area in _aree(unita):
                    trovate.setdefault(area, []).append(
                        {"programmazione": prog, "modulo": modulo, "unita": unita}
                    )
    return trovate


def _aree(unita) -> list[str]:
    aree = []
    if 2 in unita.multidisciplinare:
        aree.append("ED CIVICA")
    if 3 in unita.multidisciplinare:
        aree.append("SICUREZZA")
    if 4 in unita.multidisciplinare and unita.multidisciplinare_altro.strip():
        aree.append(unita.multidisciplinare_altro.strip().upper())
    return aree


def classi_disponibili() -> list[str]:
    return list(CLASSI)


def indirizzi_disponibili() -> list[str]:
    return list(INDIRIZZI)
