"""Lettura e scrittura delle cartelle di lavoro nel formato del VB6.

Struttura prodotta e riconosciuta (identica a quella del programma originale):

    <COGNOME_NOME>/
        da_inviare/
        <CLASSE_INDIRIZZO_DISCIPLINA>/
            output/
            do_not_use/
                datibase_programmazione.ini            (55 righe)
                moduli/
                    datibasemoduli.ini                 (2 righe)
                    modulo<n>/datispecificimodulo.ini  (9 righe)
                    modulo<n>/ud<u>/datispecificiud.ini(73 righe)

I file contengono solo valori, uno per riga, in posizione fissa: e' il tracciato
letto e scritto da Form2/Form3 e riversato nel file di invio da da_form4.bas.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .config import (
    CARTELLA_LAVORI,
    CLASSI,
    COMPETENZE_CITTADINANZA,
    COMPETENZE_EUROPEE,
    ENCODING_INI,
    INDIRIZZI,
    MAX_ABILITA,
    MAX_COMPETENZE_PECUP,
    MAX_CONOSCENZE,
    MAX_OPZIONI_ALTRO,
    MAX_OPZIONI_ELENCO,
    MULTIDISCIPLINARE,
    SPAZI_MODULO,
)

RIGHE_DATIBASE = 55
RIGHE_MODULO = 9
# Il tracciato VB6 originario prevedeva 74 righe; le 4 righe aggiuntive sotto
# conservano i dati di Educazione civica per non perdere la selezione del docente
# al riaprire la singola UDA.
RIGHE_UD = 78

# Cartelle di progetto da non confondere con quelle dei docenti.
CARTELLE_RISERVATE = {
    "admin",
    "curricolo",
    "dati",
    "do_not_use",
    "fase1py",
    "fase2py",
    "fase3py",
    "fase4py",
    "lavori",
    "templates",
    "tools",
    "__pycache__",
    ".git",
    ".venv",
    ".vscode",
}


def _leggi(percorso: Path, quante: int) -> list[str]:
    if not percorso.exists():
        return [""] * quante
    righe = percorso.read_text(encoding=ENCODING_INI, errors="replace").splitlines()
    righe = [r.strip() for r in righe][:quante]
    return righe + [""] * (quante - len(righe))


def _scrivi(percorso: Path, righe: list[str]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    contenuto = "\r\n".join(righe) + "\r\n"
    percorso.write_bytes(contenuto.encode(ENCODING_INI, errors="replace"))


def da_multiline(valore: str) -> str:
    """'@riga1@riga2' -> testo su piu' righe (Module3.risolvimultiline)."""
    return "\n".join(p for p in (valore or "").split("@") if p.strip())


def a_multiline(testo: str) -> str:
    """Testo su piu' righe -> '@riga1@riga2' (Module3.multiline)."""
    return "".join("@" + riga for riga in (testo or "").splitlines() if riga.strip())


def _numero(valore: str, predefinito: int = 0) -> int:
    valore = (valore or "").strip()
    return int(valore) if valore.isdigit() else predefinito


def _posizioni_valorizzate(righe: list[str]) -> list[int]:
    return [i for i, valore in enumerate(righe, start=1) if valore.strip()]


def cartella_docente(cognome: str, nome: str) -> Path:
    return CARTELLA_LAVORI / f"{cognome.strip().upper()}_{nome.strip().upper()}"


def cartella_corso(cognome: str, nome: str, classe: str, indirizzo: str, disciplina: str) -> Path:
    corso = f"{classe.strip()}_{indirizzo.strip()}_{disciplina.strip()}"
    return cartella_docente(cognome, nome) / corso


def _cartella_moduli(base: Path) -> Path:
    return base / "do_not_use" / "moduli"


def esiste_lavoro(cognome, nome, classe, indirizzo, disciplina) -> bool:
    base = cartella_corso(cognome, nome, classe, indirizzo, disciplina)
    return (base / "do_not_use" / "datibase_programmazione.ini").exists()


# --------------------------------------------------------------------------- lettura


def _leggi_unita(percorso: Path) -> dict[str, Any]:
    righe = _leggi(percorso, RIGHE_UD)
    return {
        "titolo": righe[0],
        "argomenti": da_multiline(righe[1]),
        "prerequisiti": da_multiline(righe[2]),
        "multidisciplinare": _posizioni_valorizzate(righe[3:7])
        + ([5] if righe[73].strip() else []),
        "multidisciplinare_altro": righe[7],
        "abilita": [da_multiline(v) for v in righe[8:17]],
        "codici_abilita": righe[17:26],
        "conoscenze": [da_multiline(v) for v in righe[26:35]],
        "codici_conoscenze": righe[35:44],
        "competenze_europee": _posizioni_valorizzate(righe[44:52]),
        "competenze_cittadinanza": _posizioni_valorizzate(righe[52:60]),
        "competenze_pecup": [da_multiline(v) for v in righe[60:65]],
        "codici_competenze_pecup": righe[65:70],
        "competenze_minime": da_multiline(righe[70]),
        "competenze_intermedie": da_multiline(righe[71]),
        "competenze_avanzate": da_multiline(righe[72]),
        "ec_voci": [v.strip() for v in (righe[74].split("@") if len(righe) > 74 else []) if v.strip()],
        "ec_ore": righe[75].strip() if len(righe) > 75 else "",
        "ec_periodo": righe[76].strip() if len(righe) > 76 else "",
        "ec_quadrimestre": righe[77].strip() if len(righe) > 77 else "",
    }


def _leggi_modulo(cartella: Path) -> dict[str, Any]:
    righe = _leggi(cartella / "datispecificimodulo.ini", RIGHE_MODULO)
    quante_ud = _numero(righe[7])
    unita = []
    for u in range(1, quante_ud + 1):
        percorso = cartella / f"ud{u}" / "datispecificiud.ini"
        if percorso.exists():
            unita.append(_leggi_unita(percorso))
    return {
        "titolo": righe[0],
        "periodo": righe[1],
        "spazi": _posizioni_valorizzate(righe[2:6]),
        "spazi_altro": righe[6],
        "unita_in_uso": righe[8],
        "unita": unita,
    }


def leggi_lavoro(cognome, nome, classe, indirizzo, disciplina) -> dict[str, Any]:
    base = cartella_corso(cognome, nome, classe, indirizzo, disciplina)
    righe = _leggi(base / "do_not_use" / "datibase_programmazione.ini", RIGHE_DATIBASE)

    dati: dict[str, Any] = {
        "cognome": cognome,
        "nome": nome,
        "classe": classe,
        "indirizzo": indirizzo,
        "disciplina": disciplina,
        "ore_settimanali": righe[0],
        "verifiche_indistinte": righe[1],
        "verifiche_orali": righe[2],
        "verifiche_pratiche": righe[3],
        "strategie": _posizioni_valorizzate(righe[4:19]),
        "strategie_altro": righe[19:21],
        "mezzi": _posizioni_valorizzate(righe[21:36]),
        "mezzi_altro": righe[36:38],
        "strumenti": _posizioni_valorizzate(righe[38:53]),
        "strumenti_altro": righe[53:55],
        "moduli": [],
    }

    cartella_moduli = _cartella_moduli(base)
    righe_moduli = _leggi(cartella_moduli / "datibasemoduli.ini", 2)
    dati["modulo_in_uso"] = righe_moduli[1]
    quanti = _numero(righe_moduli[0])
    for n in range(1, quanti + 1):
        cartella = cartella_moduli / f"modulo{n}"
        if (cartella / "datispecificimodulo.ini").exists():
            dati["moduli"].append(_leggi_modulo(cartella))
    return dati


# --------------------------------------------------------------------------- scrittura


def _righe_unita(ud: dict[str, Any]) -> list[str]:
    def elenco(chiave: str, quanti: int, multilinea: bool) -> list[str]:
        valori = list(ud.get(chiave) or [])[:quanti]
        valori += [""] * (quanti - len(valori))
        return [a_multiline(v) if multilinea else (v or "").strip() for v in valori]

    scelte = [int(n) for n in ud.get("multidisciplinare") or [1]]
    righe = [
        (ud.get("titolo") or "").strip(),
        a_multiline(ud.get("argomenti", "")),
        a_multiline(ud.get("prerequisiti", "")),
    ]
    righe += [MULTIDISCIPLINARE[i - 1] if i in scelte else "" for i in range(1, 5)]
    righe.append((ud.get("multidisciplinare_altro") or "").strip())
    righe += elenco("abilita", MAX_ABILITA, True)
    righe += elenco("codici_abilita", MAX_ABILITA, False)
    righe += elenco("conoscenze", MAX_CONOSCENZE, True)
    righe += elenco("codici_conoscenze", MAX_CONOSCENZE, False)

    europee = [int(n) for n in ud.get("competenze_europee") or []]
    cittadinanza = [int(n) for n in ud.get("competenze_cittadinanza") or []]
    righe += [COMPETENZE_EUROPEE[i - 1] if i in europee else "" for i in range(1, 9)]
    righe += [COMPETENZE_CITTADINANZA[i - 1] if i in cittadinanza else "" for i in range(1, 9)]

    righe += elenco("competenze_pecup", MAX_COMPETENZE_PECUP, True)
    righe += elenco("codici_competenze_pecup", MAX_COMPETENZE_PECUP, False)
    righe.append(a_multiline(ud.get("competenze_minime", "")))
    righe.append(a_multiline(ud.get("competenze_intermedie", "")))
    righe.append(a_multiline(ud.get("competenze_avanzate", "")))
    righe.append(
        MULTIDISCIPLINARE[4]
        if 5 in [int(n) for n in ud.get("multidisciplinare") or []]
        else ""
    )
    righe.append("@".join(str(v).strip() for v in (ud.get("ec_voci") or []) if str(v).strip()))
    righe.append((ud.get("ec_ore") or "").strip())
    righe.append((ud.get("ec_periodo") or "").strip())
    righe.append((ud.get("ec_quadrimestre") or "").strip())
    return righe


def _righe_modulo(modulo: dict[str, Any]) -> list[str]:
    spazi = [int(n) for n in modulo.get("spazi") or []]
    quante_ud = len(modulo.get("unita") or [])
    return [
        (modulo.get("titolo") or "").strip(),
        (modulo.get("periodo") or "").strip(),
        *[SPAZI_MODULO[i - 1] if i in spazi else "" for i in range(1, 5)],
        (modulo.get("spazi_altro") or "").strip(),
        str(quante_ud),
        (modulo.get("unita_in_uso") or "").strip() or str(quante_ud or 1),
    ]


def _righe_datibase(dati: dict[str, Any]) -> list[str]:
    def gruppo(chiave: str, chiave_altro: str) -> list[str]:
        scelte = [int(n) for n in dati.get(chiave) or []]
        altri = list(dati.get(chiave_altro) or [])[:MAX_OPZIONI_ALTRO]
        altri += [""] * (MAX_OPZIONI_ALTRO - len(altri))
        # Il tracciato conserva la posizione: si riscrive il testo dell'opzione scelta.
        # Le posizioni dopo l'elenco sono le due scelte "ALTRO".
        elenco = ETICHETTE_OPZIONI[chiave]
        voci = list(elenco) + ["ALTRO..."] * (MAX_OPZIONI_ELENCO - len(elenco))
        return [
            (voci[i - 1] if i in scelte else "") for i in range(1, MAX_OPZIONI_ELENCO + 1)
        ] + [(v or "").strip() for v in altri]

    return [
        (dati.get("ore_settimanali") or "").strip(),
        (dati.get("verifiche_indistinte") or "").strip(),
        (dati.get("verifiche_orali") or "").strip(),
        (dati.get("verifiche_pratiche") or "").strip(),
        *gruppo("strategie", "strategie_altro"),
        *gruppo("mezzi", "mezzi_altro"),
        *gruppo("strumenti", "strumenti_altro"),
    ]


ETICHETTE_OPZIONI: dict[str, list[str]] = {}


def _carica_etichette() -> None:
    from . import catalogo

    ETICHETTE_OPZIONI.update(
        {
            "strategie": catalogo.opzioni("strategia"),
            "mezzi": catalogo.opzioni("mezzo"),
            "strumenti": catalogo.opzioni("strumento"),
        }
    )


def scrivi_lavoro(dati: dict[str, Any]) -> Path:
    _carica_etichette()
    base = cartella_corso(
        dati["cognome"], dati["nome"], dati["classe"], dati["indirizzo"], dati["disciplina"]
    )
    (base / "output").mkdir(parents=True, exist_ok=True)
    (cartella_docente(dati["cognome"], dati["nome"]) / "da_inviare").mkdir(
        parents=True, exist_ok=True
    )

    _scrivi(base / "do_not_use" / "datibase_programmazione.ini", _righe_datibase(dati))

    moduli = dati.get("moduli") or []
    cartella_moduli = _cartella_moduli(base)
    in_uso = (dati.get("modulo_in_uso") or "").strip() or str(len(moduli) or 1)
    _scrivi(cartella_moduli / "datibasemoduli.ini", [str(len(moduli)), in_uso])

    for n, modulo in enumerate(moduli, start=1):
        cartella = cartella_moduli / f"modulo{n}"
        _scrivi(cartella / "datispecificimodulo.ini", _righe_modulo(modulo))
        for u, ud in enumerate(modulo.get("unita") or [], start=1):
            _scrivi(cartella / f"ud{u}" / "datispecificiud.ini", _righe_unita(ud))

    _ripulisci_residui(cartella_moduli, moduli)
    return base


def _ripulisci_residui(cartella_moduli: Path, moduli: list[dict[str, Any]]) -> None:
    """Svuota i file dei moduli/UDA eliminati, senza rimuovere le cartelle."""
    if not cartella_moduli.exists():
        return
    for cartella in cartella_moduli.glob("modulo*"):
        numero = _numero(cartella.name.removeprefix("modulo"))
        if not numero:
            continue
        if numero > len(moduli):
            (cartella / "datispecificimodulo.ini").unlink(missing_ok=True)
            quante_ud = 0
        else:
            quante_ud = len(moduli[numero - 1].get("unita") or [])
        for cartella_ud in cartella.glob("ud*"):
            indice = _numero(cartella_ud.name.removeprefix("ud"))
            if indice and indice > quante_ud:
                (cartella_ud / "datispecificiud.ini").unlink(missing_ok=True)


# --------------------------------------------------------------------------- ricerca


def elenca_lavori() -> list[dict[str, str]]:
    """Programmazioni gia' presenti su disco, comprese quelle create dal VB6."""
    trovati: list[dict[str, str]] = []
    if not CARTELLA_LAVORI.exists():
        return trovati

    for cartella in sorted(CARTELLA_LAVORI.iterdir()):
        if not cartella.is_dir() or cartella.name.lower() in CARTELLE_RISERVATE:
            continue
        if "_" not in cartella.name:
            continue
        cognome, nome = cartella.name.split("_", 1)

        for corso in sorted(cartella.iterdir()):
            if not corso.is_dir():
                continue
            if not (corso / "do_not_use" / "datibase_programmazione.ini").exists():
                continue
            parti = corso.name.split("_", 2)
            if len(parti) != 3 or parti[0] not in CLASSI or parti[1] not in INDIRIZZI:
                continue
            trovati.append(
                {
                    "cognome": cognome,
                    "nome": nome,
                    "classe": parti[0],
                    "indirizzo": parti[1],
                    "disciplina": parti[2],
                }
            )
    return trovati


def elimina_cartelle_lavoro() -> int:
    """Elimina le cartelle utente create dal programma e restituisce il conteggio."""
    eliminate = 0
    if not CARTELLA_LAVORI.exists():
        return eliminate

    for cartella in CARTELLA_LAVORI.iterdir():
        if not cartella.is_dir() or cartella.name.lower() in CARTELLE_RISERVATE:
            continue
        if "_" not in cartella.name:
            continue
        contiene_dati = any(
            (corso / "do_not_use").is_dir() or (corso / "da_inviare").is_dir()
            for corso in cartella.iterdir()
            if corso.is_dir()
        )
        if contiene_dati:
            shutil.rmtree(cartella)
            eliminate += 1
    return eliminate
