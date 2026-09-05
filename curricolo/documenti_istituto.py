"""Documenti d'istituto prodotti in modalita' ADMIN.

Riproduce i due documenti del Form5 del VB6 (modelli 13/14/15 e 17/18):
il curricolo orizzontale delle competenze in chiave europea e la progettazione
per competenze per aree multidisciplinari. Sono generati con python-docx,
senza campi modulo, e salvati in ADMIN/output.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import archivio, catalogo
from .config import CARTELLA_ADMIN_OUTPUT, INDIRIZZI, SIGLE_INDIRIZZO
from .word import (
    blocco_elenco,
    crea_documento,
    etichetta_valore,
    paragrafo,
    riga_tabella,
    riga_unita,
    separatore_blocco,
    tabella,
    testo_multiriga,
)

TITOLO_CURRICOLO = "CURRICOLO DI ISTITUTO ORIZZONTALE DELLE COMPETENZE IN CHIAVE EUROPEA"

# Abbreviazioni usate dal VB6 nel nome del file del curricolo.
SIGLE_COMPETENZE = {
    1: "mling",
    2: "lings",
    3: "matsc",
    4: "digit",
    5: "impar",
    6: "civic",
    7: "impre",
    8: "espre",
}

DICITURE_INDIRIZZO = [
    "COMUNE",
    "CAT",
    "GRAFICO",
    "AGRARIO (tutte le articolazioni)",
    "Articolazione GAT",
    "Articolazione P&T",
    "Articolazione ENO",
]


def _sigle(indirizzi: list[str]) -> str:
    return "_".join(SIGLE_INDIRIZZO.get(i, i[:3]).replace(" ", "") for i in indirizzi)


def _intestazione_classe(doc, classe: str, indirizzi: list[str]) -> None:
    etichetta_valore(doc, "CLASSE:", classe, corpo=12)
    paragrafo(doc, "INDIRIZZO/ARTICOLAZIONI:", grassetto=True)
    elenco = tabella(doc, 2, colonne_strette=(1,))
    for posizione, dicitura in enumerate(DICITURE_INDIRIZZO, start=1):
        segnato = INDIRIZZI[posizione - 1] in indirizzi
        riga_tabella(elenco, [dicitura, "X" if segnato else ""])


def _scheda_unita(doc, voce: dict[str, Any], *, solo_codici: bool) -> None:
    prog, modulo, unita = voce["programmazione"], voce["modulo"], voce["unita"]
    paragrafo(doc, f"DISCIPLINA: {prog.disciplina}", grassetto=True, centrato=True, corpo=12,
              sottolineato=True)
    etichetta_valore(doc, "UNITA' DIDATTICA:", unita.titolo)
    etichetta_valore(doc, "FACENTE PARTE DEL MODULO:", modulo.titolo)

    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DIDATTICA AL CONSEGUIMENTO DELLE COMPETENZE PECUP "
        "DELLA DISCIPLINA",
        unita.competenze_pecup,
        unita.codici_competenze_pecup,
        solo_codici=solo_codici,
    )
    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DIDATTICA AL CONSEGUIMENTO DELLE ABILITA' PECUP "
        "DELLA DISCIPLINA",
        unita.abilita,
        unita.codici_abilita,
        solo_codici=solo_codici,
    )
    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DIDATTICA AL CONSEGUIMENTO DELLE CONOSCENZE PECUP "
        "DELLA DISCIPLINA",
        unita.conoscenze,
        unita.codici_conoscenze,
        solo_codici=solo_codici,
    )
    _tabella_livelli(doc, unita)


def _tabella_livelli(doc, unita) -> None:
    livelli = tabella(doc, 1)
    riga_unita(livelli, "LIVELLI DI COMPETENZA DELLA UNITA' DIDATTICA")
    voci = [
        ("BASE (determina gli obiettivi fondanti dell'unita' didattica):", unita.competenze_minime),
        (
            "INTERMEDIO (in aggiunta a quanto descritto per il livello BASE):",
            unita.competenze_intermedie,
        ),
        (
            "AVANZATO (in aggiunta a quanto descritto per il livello INTERMEDIO):",
            unita.competenze_avanzate,
        ),
    ]
    for etichetta, contenuto in voci:
        riga_tabella(livelli, [f"{etichetta}\n{contenuto}"])


def genera_curricolo(
    classe: str,
    indirizzi: list[str],
    competenze: list[int],
    *,
    solo_codici: bool = False,
    giorno: date | None = None,
) -> Path:
    giorno = giorno or date.today()
    schede = {int(s["posizione"]): s for s in catalogo.competenze_ue()}
    trovate = archivio.unita_per_competenza(classe, indirizzi)

    doc = crea_documento()
    paragrafo(doc, TITOLO_CURRICOLO, grassetto=True, centrato=True, corpo=16)
    separatore_blocco(doc)
    paragrafo(doc, "COMPETENZE IN CHIAVE EUROPEA VALUTATE", grassetto=True, centrato=True, corpo=12)
    elenco = tabella(doc, 2, colonne_strette=(0,))
    for posizione, scheda in schede.items():
        riga_tabella(elenco, [str(posizione), str(scheda["titolo_esteso"])])

    paragrafo(
        doc,
        "PARAMETRI DI VALUTAZIONE PER ACCERTAMENTO DELLA COMPETENZA",
        grassetto=True,
        centrato=True,
        corpo=12,
    )
    parametri = tabella(doc, 2)
    for livello in schede[1]["livelli"]:  # type: ignore[index]
        riga_tabella(parametri, [livello["etichetta"], livello["descrizione"]], corpo=9)

    for posizione in sorted(competenze):
        scheda = schede.get(posizione)
        if scheda is None:
            continue
        doc.add_page_break()
        _intestazione_classe(doc, classe, indirizzi)
        etichetta_valore(doc, "COMPETENZA IN CHIAVE EUROPEA:", str(scheda["titolo_esteso"]), 12)
        paragrafo(doc, "DESCRIZIONE:", grassetto=True)
        paragrafo(doc, str(scheda["descrizione"]), corpo=10)

        voci = trovate.get(posizione, [])
        if not voci:
            paragrafo(doc, "Nessuna unita' didattica dichiara questa competenza.", corpo=10)
            continue
        for voce in voci:
            paragrafo(doc)
            _scheda_unita(doc, voce, solo_codici=solo_codici)

    sigle = "_".join(SIGLE_COMPETENZE[p] for p in sorted(competenze) if p in SIGLE_COMPETENZE)
    nome = f"curr_orizz_{sigle}_{classe}_{_sigle(indirizzi)}_{giorno:%d_%m_%y}.docx"
    return _salva(doc, nome)


def genera_multidisciplinare(
    classe: str, indirizzi: list[str], aree: list[str], giorno: date | None = None
) -> Path:
    giorno = giorno or date.today()
    trovate = archivio.aree_multidisciplinari(classe, indirizzi)

    doc = crea_documento()
    paragrafo(doc, "PROGRAMMAZIONE PER COMPETENZE", grassetto=True, centrato=True, corpo=16)
    _intestazione_classe(doc, classe, indirizzi)
    separatore_blocco(doc)
    paragrafo(doc, "MATERIA MULTIDISCIPLINARE:", grassetto=True)
    paragrafo(doc, " - ".join(aree), grassetto=True, centrato=True, corpo=12)

    for area in aree:
        doc.add_page_break()
        paragrafo(doc, area, grassetto=True, centrato=True, corpo=14)
        voci = trovate.get(area, [])
        if not voci:
            paragrafo(doc, "Nessuna unita' didattica dichiara questa area.", corpo=10)
            continue
        for voce in voci:
            prog, modulo, unita = voce["programmazione"], voce["modulo"], voce["unita"]
            paragrafo(doc)
            etichetta_valore(doc, "DISCIPLINA:", prog.disciplina, 12)
            etichetta_valore(doc, "UNITA' DIDATTICA:", unita.titolo)
            etichetta_valore(doc, "FACENTE PARTE DEL MODULO:", modulo.titolo)
            etichetta_valore(doc, "Svolto di norma nel periodo:", modulo.periodo)
            paragrafo(doc, "ARGOMENTI TRATTATI:", grassetto=True)
            testo_multiriga(doc, unita.argomenti)
            _tabella_livelli(doc, unita)

    sigla_area = "".join((aree[0][:4] if aree else "area").split()).lower()
    nome = f"program_multidisc_{sigla_area}_{classe}_{_sigle(indirizzi)}_{giorno:%d_%m_%y}.docx"
    return _salva(doc, nome)


def _salva(doc: Document, nome: str) -> Path:
    CARTELLA_ADMIN_OUTPUT.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA_ADMIN_OUTPUT / nome
    doc.save(str(percorso))
    return percorso
