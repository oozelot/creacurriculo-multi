"""Generazione del file INI da inviare al referente, nello stesso formato del VB6.

Il tracciato e' quello di da_form4.bas (Sub generafile): righe
"<codice><etichetta>§<valore>", encoding cp1252, fine riga CRLF.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import catalogo
from .config import (
    CARTELLA_LAVORI,
    COMPETENZE_CITTADINANZA,
    COMPETENZE_EUROPEE,
    ENCODING_INI,
    MAX_ABILITA,
    MAX_COMPETENZE_PECUP,
    MAX_CONOSCENZE,
    MAX_OPZIONI_ALTRO,
    MAX_OPZIONI_ELENCO,
    MULTIDISCIPLINARE,
    SEPARATORE_INI,
    SPAZI_MODULO,
)
from .legacy import a_multiline as multiline
from .modello import Modulo, Programmazione, UnitaDidattica

INTESTAZIONE = (
    "ATTENZIONE NON MODIFICARE QUESTO DOCUMENTO ED INVIARLO TAL QUALE AL REFERENTE "
    "PER COSTITUTZIONE DEL CURRICOLO DI ISTITUTO"
)


def nome_file_invio(
    prog: Programmazione, giorno: date | None = None, referente: str = ""
) -> str:
    giorno = giorno or date.today()
    sigla = catalogo.sigla_ini_disciplina(prog.disciplina)
    indirizzo = catalogo.sigla_indirizzo(prog.indirizzo)
    cognome = f"{prog.cognome.strip().upper():<3}"[:3]
    nome = f"{prog.nome.strip().upper():<3}"[:3]
    classe = prog.classe.strip().upper()[:5]
    referente = " ".join(parola.casefold().capitalize() for parola in referente.split())
    suffisso = f" - {referente}" if referente else ""
    return f"{sigla}_{indirizzo}_{cognome}{nome}_{classe}_{giorno:%d_%m_%y}{suffisso}.ini"


def _riga(codice: str, etichetta: str, valore: str) -> str:
    return f"{codice}{etichetta}{SEPARATORE_INI}{(valore or '').strip()}"


def _sezione(titolo: str) -> str:
    return f"{titolo}{SEPARATORE_INI}"


def _voci_selezionate(scelte: list[int], elenco: list[str]) -> list[str]:
    """Ogni posizione riporta il testo dell'opzione se selezionata, altrimenti vuoto.

    Le due posizioni successive all'elenco sono le scelte "ALTRO", il cui testo libero
    viene scritto a parte nei campi dedicati.
    """
    voci = list(elenco) + ["ALTRO..."] * (MAX_OPZIONI_ELENCO - len(elenco))
    return [(voci[i - 1] if i in scelte else "") for i in range(1, MAX_OPZIONI_ELENCO + 1)]


def _righe_unita(ud: UnitaDidattica, modulo: int, unita: int) -> list[str]:
    # Bug del generatore VB6 riprodotto per compatibilita': per i moduli 1-9 il numero
    # della UDA viene scritto su 3 cifre quando vale 10, per il modulo 10 su una sola cifra.
    bn = f"{modulo:02d}"
    bu = f"0{unita}" if modulo < 10 else str(unita)
    coda = f"N\u00b0{unita}DEL MODULO N\u00b0{modulo}"

    def riga(campo: int, etichetta: str, valore: str) -> str:
        return _riga(f"{bn}{bu}{campo:02d}", etichetta, valore)

    scelte = ud.multidisciplinare or [1]
    multi = [MULTIDISCIPLINARE[i - 1] if i in scelte else "" for i in range(1, 5)]

    righe = [
        riga(1, f"TITOLO UNITA DI APPRENDIMENTO {coda}", ud.titolo),
        riga(2, f"argomenti unita di apprendimento {coda}", multiline(ud.argomenti)),
        riga(3, f"prerequisiti unita di apprendimento {coda}", multiline(ud.prerequisiti)),
        riga(4, f"si no inserita in un quadro multidisciplinare unita di apprendimento {coda}", multi[0]),
        riga(5, f"quadro multidisciplinare educazione civica unita di apprendimento {coda}", multi[1]),
        riga(6, f"quadro multidisciplinare sicurezza prime unita di apprendimento {coda}", multi[2]),
        riga(7, f"altro quadro multidisciplinare unita di apprendimento {coda}", multi[3]),
        riga(
            8,
            f"quale altro quadro multidisciplinare unita di apprendimento {coda}",
            ud.multidisciplinare_altro,
        ),
    ]

    campo = 8
    for k in range(1, MAX_ABILITA + 1):
        campo += 1
        righe.append(riga(campo, f"abilit\u00e0 n\u00b0{k}  dell'unita di apprendimento {coda}", multiline(ud.abilita[k - 1])))
    for k in range(1, MAX_ABILITA + 1):
        campo += 1
        righe.append(riga(campo, f"codice abilit\u00e0 n\u00b0{k}  dell'unita di apprendimento {coda}", ud.codici_abilita[k - 1]))
    for k in range(1, MAX_CONOSCENZE + 1):
        campo += 1
        righe.append(riga(campo, f"conoscenza n\u00b0{k}  dell'unita di apprendimento {coda}", multiline(ud.conoscenze[k - 1])))
    for k in range(1, MAX_CONOSCENZE + 1):
        campo += 1
        righe.append(riga(campo, f"codice conoscenza n\u00b0{k}  dell'unita di apprendimento {coda}", ud.codici_conoscenze[k - 1]))
    for k in range(1, 9):
        campo += 1
        valore = COMPETENZE_EUROPEE[k - 1] if k in ud.competenze_europee else ""
        righe.append(riga(campo, f"competenza in chiave europea n\u00b0{k}  dell'unita di apprendimento {coda}", valore))
    for k in range(1, 9):
        campo += 1
        valore = COMPETENZE_CITTADINANZA[k - 1] if k in ud.competenze_cittadinanza else ""
        righe.append(riga(campo, f"competenza in chiave cittadinanza n\u00b0{k}  dell'unita di apprendimento {coda}", valore))
    for k in range(1, MAX_COMPETENZE_PECUP + 1):
        campo += 1
        righe.append(riga(campo, f"competenza pecup n\u00b0{k}  dell'unita di apprendimento {coda}", multiline(ud.competenze_pecup[k - 1])))
    for k in range(1, MAX_COMPETENZE_PECUP + 1):
        campo += 1
        righe.append(riga(campo, f"codice competenza pecup n\u00b0{k}  dell'unita di apprendimento {coda}", ud.codici_competenze_pecup[k - 1]))

    righe.append(_riga(f"{bn}{bu}71", f"competenze minime unita di apprendimento {coda}", multiline(ud.competenze_minime)))
    righe.append(_riga(f"{bn}{bu}72", f"competenze intermedie unita di apprendimento {coda}", multiline(ud.competenze_intermedie)))
    righe.append(_riga(f"{bn}{bu}73", f"competenze avanzate unita di apprendimento {coda}", multiline(ud.competenze_avanzate)))
    righe.append(_riga(
        f"{bn}{bu}74",
        f"quadro multidisciplinare scienze sperimentali unita di apprendimento {coda}",
        MULTIDISCIPLINARE[4] if 5 in ud.multidisciplinare else "",
    ))
    righe.append(_riga(
        f"{bn}{bu}75",
        f"voci educazione civica unita di apprendimento {coda}",
        "@".join(str(voce).strip() for voce in ud.ec_voci if str(voce).strip()),
    ))
    righe.append(_riga(f"{bn}{bu}76", f"ore educazione civica unita di apprendimento {coda}", ud.ec_ore))
    righe.append(_riga(f"{bn}{bu}77", f"periodo educazione civica unita di apprendimento {coda}", ud.ec_periodo))
    righe.append(_riga(f"{bn}{bu}78", f"quadrimestre educazione civica unita di apprendimento {coda}", ud.ec_quadrimestre))
    return righe


def _righe_modulo(modulo: Modulo, numero: int) -> list[str]:
    bn = f"{numero:02d}"
    spazi = [SPAZI_MODULO[i - 1] if i in modulo.spazi else "" for i in range(1, 5)]
    righe = [
        _sezione(f"======== DATI SPECIFICI DEL MODULO N\u00b0{numero}========"),
        _riga(f"{bn}0001", f"TITOLO DEL MODULO{numero}", modulo.titolo),
        _riga(f"{bn}0002", f"Periodo di esecuzione del modulo{numero}", modulo.periodo),
        _riga(f"{bn}0003", f"opzione aule del modulo{numero}", spazi[0]),
        _riga(f"{bn}0004", f"opzione laboratori del modulo{numero}", spazi[1]),
        _riga(f"{bn}0005", f"opzione palestra del modulo{numero}", spazi[2]),
        _riga(f"{bn}0006", f"opzione altri spazi del modulo{numero}", spazi[3]),
        _riga(f"{bn}0007", f"specificazione di spazi del modulo{numero}", modulo.spazi_altro),
        _riga(f"{bn}0008", f"N\u00b0 UDA UTILIZZATE PER IL MODULO{numero}", str(len(modulo.unita))),
        _riga(
            f"{bn}0009",
            f"Unita di apprendimento in uso per il modulo{numero}",
            modulo.unita_in_uso or str(len(modulo.unita) or 1),
        ),
        _sezione(f"======== UNITA' DI APPRENDIMENTO DEL MODULO N\u00b0{numero}========"),
    ]
    if not modulo.unita:
        righe.append(_sezione(f"IL MODULO N\u00b0{numero}NON CONTIENE UNITA' DI APPRENDIMENTO"))
        return righe
    for indice, ud in enumerate(modulo.unita, start=1):
        righe.append(_sezione(f"***UNITA' DI APPRENDIMENTO N\u00b0{indice}DEL MODULO N\u00b0{numero} ***"))
        righe.extend(_righe_unita(ud, numero, indice))
    return righe


def genera_righe(prog: Programmazione, giorno: date | None = None) -> list[str]:
    giorno = giorno or date.today()
    righe = [
        _sezione(INTESTAZIONE),
        _riga("000001", "DATA", f"{giorno:%d_%m_%y}"),
        _riga("000002", "COGNOME", prog.cognome.upper()),
        _riga("000003", "NOME", prog.nome.upper()),
        _riga("000004", "", prog.classe),
        _riga("000005", "INDIRIZZO", prog.indirizzo),
        _riga("000006", "DISCIPLINA", prog.disciplina),
        _sezione("======== DATI BASE DELLA PROGRAMMAZIONE ========"),
        _riga("000007", "ore settimanali della disciplina", prog.ore_settimanali),
        _riga("000008", "numero minimo verifiche indistinte al quadrimestre", prog.verifiche_indistinte),
        _riga("000009", "numero minimo verifiche orali al quadrimestre", prog.verifiche_orali),
        _riga("000010", "numero minimo verifiche pratiche al quadrimestre", prog.verifiche_pratiche),
    ]

    gruppi = [
        ("strategia", "strategia n\u00b0{n} dell'elenco", "strategia inserita come altro n\u00b0{n}", prog.strategie, prog.strategie_altro),
        ("mezzo", "mezzi n\u00b0{n} dell'elenco", "mezzo inserito come altro n\u00b0{n}", prog.mezzi, prog.mezzi_altro),
        ("strumento", "strumento n\u00b0{n} dell'elenco", "strumento inserito come altro n\u00b0{n}", prog.strumenti, prog.strumenti_altro),
    ]

    codice = 10
    for gruppo, etichetta, etichetta_altro, scelte, altri in gruppi:
        valori = _voci_selezionate(scelte, catalogo.opzioni(gruppo))
        for n in range(1, MAX_OPZIONI_ELENCO + 1):
            codice += 1
            righe.append(_riga(f"{codice:06d}", etichetta.format(n=n), valori[n - 1]))
        for n in range(1, MAX_OPZIONI_ALTRO + 1):
            codice += 1
            righe.append(_riga(f"{codice:06d}", etichetta_altro.format(n=n), altri[n - 1]))

    righe.append(_sezione("======== DATI BASE DEI MODULI ========"))
    righe.append(_riga("000062", "N\u00b0 MODULI UTILIZZATI", str(len(prog.moduli))))
    righe.append(
        _riga("000063", "Modulo in uso", prog.modulo_in_uso or str(len(prog.moduli) or 1))
    )

    for numero, modulo in enumerate(prog.moduli, start=1):
        righe.extend(_righe_modulo(modulo, numero))
    return righe


def scrivi_file(prog: Programmazione, giorno: date | None = None) -> Path:
    giorno = giorno or date.today()
    cartella = CARTELLA_LAVORI / prog.cartella_docente / "da_inviare"
    cartella.mkdir(parents=True, exist_ok=True)
    referente = f"{prog.nome.strip()} {prog.cognome.strip()}".strip()
    percorso = cartella / nome_file_invio(prog, giorno, referente)
    contenuto = "\r\n".join(genera_righe(prog, giorno)) + "\r\n"
    percorso.write_bytes(contenuto.encode(ENCODING_INI, errors="replace"))
    return percorso
