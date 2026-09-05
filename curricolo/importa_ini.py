"""Lettura dei file INI inviati dai docenti (ADMIN/file_ricevuti).

Il tracciato e' quello prodotto da esporta_ini: righe "<codice><etichetta>§<valore>"
in cp1252. Qui si ricostruisce la programmazione completa a partire dal file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ENCODING_INI, SEPARATORE_INI
from .legacy import da_multiline
from .modello import Programmazione


def _posizioni_valorizzate(valori: dict[int, str], primo: int, quanti: int) -> list[int]:
    return [i for i in range(1, quanti + 1) if (valori.get(primo + i - 1) or "").strip()]


def _testi(valori: dict[int, str], primo: int, quanti: int, *, multilinea: bool) -> list[str]:
    voci = [valori.get(primo + i, "") for i in range(quanti)]
    return [da_multiline(v) if multilinea else v for v in voci]


def leggi_righe(percorso: Path) -> dict[tuple[int, int], dict[int, str]]:
    """Valori del file raggruppati per (modulo, unita); (0, 0) e' la sezione generale."""
    dati: dict[tuple[int, int], dict[int, str]] = {}
    testo = percorso.read_text(encoding=ENCODING_INI, errors="replace")

    for riga in testo.splitlines():
        cifre = 0
        while cifre < len(riga) and riga[cifre].isdigit():
            cifre += 1
        if cifre not in (6, 7):
            continue
        codice, resto = riga[:cifre], riga[cifre:]
        valore = resto.partition(SEPARATORE_INI)[2]
        # Il generatore VB6 scrive 7 cifre quando l'unita' didattica e' la decima.
        if cifre == 6:
            modulo, unita, campo = int(codice[0:2]), int(codice[2:4]), int(codice[4:6])
        else:
            modulo, unita, campo = int(codice[0:2]), int(codice[2:5]), int(codice[5:7])
        dati.setdefault((modulo, unita), {})[campo] = valore

    return dati


def _unita(valori: dict[int, str]) -> dict[str, Any]:
    return {
        "titolo": valori.get(1, ""),
        "argomenti": da_multiline(valori.get(2, "")),
        "prerequisiti": da_multiline(valori.get(3, "")),
        "multidisciplinare": _posizioni_valorizzate(valori, 4, 4),
        "multidisciplinare_altro": valori.get(8, ""),
        "abilita": _testi(valori, 9, 9, multilinea=True),
        "codici_abilita": _testi(valori, 18, 9, multilinea=False),
        "conoscenze": _testi(valori, 27, 9, multilinea=True),
        "codici_conoscenze": _testi(valori, 36, 9, multilinea=False),
        "competenze_europee": _posizioni_valorizzate(valori, 45, 8),
        "competenze_cittadinanza": _posizioni_valorizzate(valori, 53, 8),
        "competenze_pecup": _testi(valori, 61, 5, multilinea=True),
        "codici_competenze_pecup": _testi(valori, 66, 5, multilinea=False),
        "competenze_minime": da_multiline(valori.get(71, "")),
        "competenze_intermedie": da_multiline(valori.get(72, "")),
        "competenze_avanzate": da_multiline(valori.get(73, "")),
    }


def leggi_file(percorso: Path) -> Programmazione:
    dati = leggi_righe(percorso)
    base = dati.get((0, 0), {})

    programmazione: dict[str, Any] = {
        "cognome": base.get(2, ""),
        "nome": base.get(3, ""),
        "classe": base.get(4, ""),
        "indirizzo": base.get(5, ""),
        "disciplina": base.get(6, ""),
        "ore_settimanali": base.get(7, ""),
        "verifiche_indistinte": base.get(8, ""),
        "verifiche_orali": base.get(9, ""),
        "verifiche_pratiche": base.get(10, ""),
        "strategie": _posizioni_valorizzate(base, 11, 15),
        "strategie_altro": _testi(base, 26, 2, multilinea=False),
        "mezzi": _posizioni_valorizzate(base, 28, 15),
        "mezzi_altro": _testi(base, 43, 2, multilinea=False),
        "strumenti": _posizioni_valorizzate(base, 45, 15),
        "strumenti_altro": _testi(base, 60, 2, multilinea=False),
        "modulo_in_uso": base.get(63, ""),
        "moduli": [],
    }

    numeri = sorted({m for m, u in dati if m > 0})
    for numero in numeri:
        campi = dati.get((numero, 0), {})
        unita = [
            _unita(dati[(numero, u)])
            for u in sorted(u for m, u in dati if m == numero and u > 0)
        ]
        programmazione["moduli"].append(
            {
                "titolo": campi.get(1, ""),
                "periodo": campi.get(2, ""),
                "spazi": _posizioni_valorizzate(campi, 3, 4),
                "spazi_altro": campi.get(7, ""),
                "unita_in_uso": campi.get(9, ""),
                "unita": unita,
            }
        )

    return Programmazione.da_dict(programmazione)


def data_documento(percorso: Path) -> str:
    return leggi_righe(percorso).get((0, 0), {}).get(1, "")
