"""Generazione dei documenti Word prodotti dallo Step 4.

Riproduce i quattro documenti del VB6 (modelli 01-12) scrivendo pero' paragrafi e
tabelle diretti con python-docx: niente campi modulo FORMTEXT ne' bookmark, quindi
i file si aprono e si stampano anche senza Word installato.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import catalogo, legacy
from .config import COMPETENZE_CITTADINANZA, SPAZI_MODULO
from .esporta_ini import nome_file_invio
from .modello import Modulo, Programmazione, UnitaDidattica
from .word import (
    blocco_elenco as _blocco_elenco,
    crea_documento as _crea_documento,
    etichetta_valore as _etichetta_valore,
    paragrafo as _paragrafo,
    riga_tabella as _riga_tabella,
    separatore_blocco as _separatore_blocco,
    riga_unita as _intestazione_unita,
    tabella as _tabella,
    testo_multiriga as _testo_multiriga,
)

DOCUMENTI = {
    "programmazione": ("programmazione_per_competenze", "Programmazione per competenze"),
    "preventivo": ("programma_preventivo", "Programma preventivo"),
    "fondanti": ("contenuti_fondanti", "Competenze fondanti (obiettivi minimi)"),
    "certificazione": ("certificazione_competenze", "Certificazione delle competenze"),
}

SEPARATORE = "-" * 100


def cartella_output(prog: Programmazione) -> Path:
    return legacy.cartella_corso(
        prog.cognome, prog.nome, prog.classe, prog.indirizzo, prog.disciplina
    ) / "output"


def nome_file(prog: Programmazione, tipo: str, quando: datetime | None = None) -> str:
    quando = quando or datetime.now()
    base = nome_file_invio(prog, quando.date()).removesuffix(".ini")
    return f"{DOCUMENTI[tipo][0]}_{base}_{quando:%H_%M}.docx"


# --------------------------------------------------------------------------- utilita'


def _tabella_scelte(doc, titolo: str, voci: list[str], scelte: list[int], altri: list[str]) -> None:
    tabella = _tabella(doc, 2, colonne_strette=(1,))
    _intestazione_unita(tabella, titolo)
    for posizione, voce in enumerate(voci, start=1):
        _riga_tabella(tabella, [voce, "X" if posizione in scelte else ""])
    for indice, testo in enumerate(altri, start=1):
        segnata = (len(voci) + indice) in scelte or bool(testo.strip())
        _riga_tabella(tabella, [f"ALTRO {indice} \u2026...", "X" if segnata else ""])
        if testo.strip():
            _intestazione_unita(tabella, testo.strip())


def _dati_docente(doc, prog: Programmazione, giorno: str) -> None:
    _etichetta_valore(doc, "CLASSE:", prog.classe, corpo=12)
    _etichetta_valore(doc, "INDIRIZZO:", prog.indirizzo, corpo=12)
    _etichetta_valore(doc, "DISCIPLINA:", prog.disciplina, corpo=12)
    _etichetta_valore(doc, "DOCUMENTO CREATO DA:", f"{prog.cognome} {prog.nome}", corpo=12)
    _etichetta_valore(doc, "In data:", giorno, corpo=12)


def _titolo_unita(modulo: int, unita: int) -> str:
    return f"UNITA' DI APPRENDIMENTO N\u00b0{unita} DEL MODULO N\u00b0{modulo}"


# --------------------------------------------------------------------------- documenti


def _sezione_modulo(doc, mod: Modulo, numero: int, *, con_spazi: bool) -> None:
    _etichetta_valore(doc, "MODULO NUMERO:", str(numero), corpo=12)
    _etichetta_valore(doc, "TITOLO DEL MODULO:", mod.titolo, corpo=12)
    if not con_spazi:
        return
    _paragrafo(
        doc,
        f"Il presente modulo costituito da {len(mod.unita)} unita' di apprendimento viene eseguito "
        f"nel seguente periodo dell'anno: {mod.periodo}",
    )
    tabella = _tabella(doc, 2, colonne_strette=(1,))
    _intestazione_unita(tabella, "SPAZI PREVISTI PER L'ESECUZIONE DEL MODULO")
    for posizione, spazio in enumerate(SPAZI_MODULO[:3], start=1):
        _riga_tabella(tabella, [spazio, "X" if posizione in mod.spazi else ""])
    _riga_tabella(tabella, ["ALTRO \u2026...", "X" if 4 in mod.spazi else ""])
    if 4 in mod.spazi and mod.spazi_altro.strip():
        _intestazione_unita(tabella, mod.spazi_altro.strip())


def _sezione_unita(doc, ud: UnitaDidattica, modulo: int, indice: int) -> None:
    _paragrafo(doc, _titolo_unita(modulo, indice), grassetto=True, centrato=True, corpo=12)
    _etichetta_valore(doc, "TITOLO:", ud.titolo, corpo=12)

    _paragrafo(doc, "PREREQUISITI:", grassetto=True)
    _testo_multiriga(doc, ud.prerequisiti)
    _paragrafo(doc, "ARGOMENTI TRATTATI:", grassetto=True)
    _testo_multiriga(doc, ud.argomenti)

    tabella = _tabella(doc, 2, colonne_strette=(1,))
    _intestazione_unita(tabella, "IN QUALE QUADRO MULTIDISCIPLINARE E' INSERITA L'U.D")
    diciture = [
        "NESSUNO",
        "EDUCAZIONE CIVICA",
        "SICUREZZA CLASSI PRIME",
        "ALTRO \u2026...",
        "SCIENZE SPERIMENTALI",
    ]
    for posizione, dicitura in enumerate(diciture, start=1):
        _riga_tabella(tabella, [dicitura, "X" if posizione in ud.multidisciplinare else ""])
    if 4 in ud.multidisciplinare and ud.multidisciplinare_altro.strip():
        _intestazione_unita(tabella, ud.multidisciplinare_altro.strip())

    _paragrafo(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE COMPETENZE CHIAVE EUROPA",
        grassetto=True,
    )
    tabella = _tabella(doc, 3, colonne_strette=(0, 2))
    for scheda in catalogo.competenze_ue():
        posizione = int(scheda["posizione"])
        _riga_tabella(
            tabella,
            [
                str(posizione),
                str(scheda["titolo"]),
                "X" if posizione in ud.competenze_europee else "",
            ],
        )

    _paragrafo(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE COMPETENZE CHIAVE "
        "DI CITTADINANZA",
        grassetto=True,
    )
    tabella = _tabella(doc, 3, colonne_strette=(0, 2))
    for posizione, voce in enumerate(COMPETENZE_CITTADINANZA, start=1):
        _riga_tabella(
            tabella,
            [str(posizione), voce, "X" if posizione in ud.competenze_cittadinanza else ""],
        )

    _blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE COMPETENZE RELATIVE AL "
        "PROFILO EDUCATIVO CULTURALE E PROFESSIONALE (PECUP) DELLA DISCIPLINA",
        ud.competenze_pecup,
        ud.codici_competenze_pecup,
    )
    _blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE ABILITA' RELATIVE AL "
        "PROFILO EDUCATIVO CULTURALE E PROFESSIONALE (PECUP) DELLA DISCIPLINA",
        ud.abilita,
        ud.codici_abilita,
    )
    _blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE CONOSCENZE RELATIVE AL "
        "PROFILO EDUCATIVO CULTURALE E PROFESSIONALE (PECUP) DELLA DISCIPLINA",
        ud.conoscenze,
        ud.codici_conoscenze,
    )

    tabella = _tabella(doc, 1)
    _intestazione_unita(tabella, "LIVELLI DI COMPETENZA DELLA UNITA' DI APPRENDIMENTO")
    livelli = [
        ("BASE (determina gli obiettivi fondanti dell'unita' di apprendimento):", ud.competenze_minime),
        (
            "INTERMEDIO (in aggiunta a quanto descritto per il livello BASE):",
            ud.competenze_intermedie,
        ),
        (
            "AVANZATO (in aggiunta a quanto descritto per il livello INTERMEDIO):",
            ud.competenze_avanzate,
        ),
    ]
    for etichetta, contenuto in livelli:
        _riga_tabella(tabella, [f"{etichetta}\n{contenuto}"])


def _documento_programmazione(prog: Programmazione, giorno: str) -> Document:
    doc = _crea_documento()
    _paragrafo(doc, "PROGRAMMAZIONE PER COMPETENZE", grassetto=True, centrato=True, corpo=16)
    _dati_docente(doc, prog, giorno)
    _separatore_blocco(doc)
    _paragrafo(doc, "ASPETTI GENERALI DELLA PROGRAMMAZIONE", grassetto=True, centrato=True, corpo=13)
    _etichetta_valore(doc, "ORE SETTIMANALI DELLA DISCIPLINA:", prog.ore_settimanali)
    _etichetta_valore(
        doc,
        "NUMERO MINIMO DI VERIFICHE INDIFFERENZIATE AL QUADRIMESTRE (*) =",
        prog.verifiche_indistinte,
    )
    _etichetta_valore(
        doc, "NUMERO MINIMO DI VERIFICHE ORALI AL QUADRIMESTRE (*) =", prog.verifiche_orali
    )
    _etichetta_valore(
        doc, "NUMERO MINIMO DI VERIFICHE PRATICHE AL QUADRIMESTRE (*) =", prog.verifiche_pratiche
    )
    _paragrafo(doc, "(*) in base a quanto deliberato dai dipartimenti/collegio dei docenti", corpo=9)
    _paragrafo(
        doc,
        f"LA PRESENTE PROGRAMMAZIONE SI ARTICOLA IN {len(prog.moduli)} MODULI",
        grassetto=True,
    )

    _tabella_scelte(
        doc,
        "STRATEGIE DI MEDIAZIONE DIDATTICA",
        catalogo.opzioni_documento("strategia"),
        prog.strategie,
        prog.strategie_altro,
    )
    _tabella_scelte(
        doc, "MEZZI", catalogo.opzioni_documento("mezzo"), prog.mezzi, prog.mezzi_altro
    )
    _tabella_scelte(
        doc,
        "STRUMENTI DI VALUTAZIONE",
        catalogo.opzioni_documento("strumento"),
        prog.strumenti,
        prog.strumenti_altro,
    )

    for numero, mod in enumerate(prog.moduli, start=1):
        doc.add_page_break()
        _sezione_modulo(doc, mod, numero, con_spazi=True)
        for indice, ud in enumerate(mod.unita, start=1):
            doc.add_page_break()
            _sezione_unita(doc, ud, numero, indice)
    return doc


def _documento_preventivo(prog: Programmazione, giorno: str) -> Document:
    doc = _crea_documento()
    _paragrafo(doc, "PROGRAMMA PREVENTIVO", grassetto=True, centrato=True, corpo=16)
    _dati_docente(doc, prog, giorno)
    _separatore_blocco(doc)
    _paragrafo(doc, SEPARATORE)
    for numero, mod in enumerate(prog.moduli, start=1):
        _sezione_modulo(doc, mod, numero, con_spazi=False)
        for indice, ud in enumerate(mod.unita, start=1):
            _etichetta_valore(doc, f"{_titolo_unita(numero, indice)}:", ud.titolo)
            _paragrafo(doc, "ARGOMENTI TRATTATI:", grassetto=True)
            _testo_multiriga(doc, ud.argomenti)
        _paragrafo(doc, SEPARATORE)
    return doc


def _documento_fondanti(prog: Programmazione, giorno: str) -> Document:
    doc = _crea_documento()
    _paragrafo(doc, "COMPETENZE FONDANTI DEL PROGRAMMA", grassetto=True, centrato=True, corpo=16)
    _paragrafo(doc, '("OBIETTIVI MINIMI")', grassetto=True, centrato=True, corpo=13)
    _dati_docente(doc, prog, giorno)
    _separatore_blocco(doc)
    _paragrafo(doc, SEPARATORE)
    for numero, mod in enumerate(prog.moduli, start=1):
        _sezione_modulo(doc, mod, numero, con_spazi=False)
        for indice, ud in enumerate(mod.unita, start=1):
            tabella = _tabella(doc, 1)
            _riga_tabella(
                tabella,
                [f"COMPETENZE FONDANTI DELLA {_titolo_unita(numero, indice)}:\n{ud.titolo}"],
                grassetto=True,
            )
            _riga_tabella(tabella, [ud.competenze_minime])
        _paragrafo(doc, SEPARATORE)
    return doc


def _documento_certificazione(prog: Programmazione, giorno: str) -> Document:
    doc = _crea_documento()
    schede = {int(s["posizione"]): s for s in catalogo.competenze_ue()}

    _paragrafo(
        doc,
        "CERTIFICAZIONE DELLE COMPETENZE IN CHIAVE EUROPEA",
        grassetto=True,
        centrato=True,
        corpo=16,
    )
    _dati_docente(doc, prog, giorno)
    _separatore_blocco(doc)
    _paragrafo(doc, "COMPETENZE IN CHIAVE EUROPEA VALUTATE (*)", grassetto=True, centrato=True)
    tabella = _tabella(doc, 2)
    for posizione, scheda in schede.items():
        _riga_tabella(tabella, [str(posizione), str(scheda["titolo"])])
    _paragrafo(
        doc,
        "(*) Le competenze prese in considerazione possono essere differenti tra le diverse "
        "unita' di apprendimento",
        corpo=9,
    )
    _paragrafo(
        doc,
        f"LA PRESENTE CERTIFICAZIONE E' RIFERITA AI {len(prog.moduli)} MODULI DELLA "
        "DISCIPLINA IN OGGETTO",
        grassetto=True,
    )

    for numero, mod in enumerate(prog.moduli, start=1):
        doc.add_page_break()
        _sezione_modulo(doc, mod, numero, con_spazi=False)
        for indice, ud in enumerate(mod.unita, start=1):
            _paragrafo(
                doc,
                f"COMPETENZE IN CHIAVE EUROPEA CERTIFICATE NELL'UNITA' DI APPRENDIMENTO N\u00b0{indice}",
                grassetto=True,
                centrato=True,
                corpo=12,
                sottolineato=True,
            )
            _paragrafo(doc, "TITOLO UNITA DI APPRENDIMENTO:", grassetto=True)
            _paragrafo(doc, ud.titolo)
            _paragrafo(doc, "ARGOMENTI TRATTATI", grassetto=True)
            _testo_multiriga(doc, ud.argomenti)
            for posizione in sorted(ud.competenze_europee):
                scheda = schede.get(posizione)
                if scheda is None:
                    continue
                _paragrafo(doc, str(scheda["titolo"]), grassetto=True)
                _paragrafo(doc, str(scheda["descrizione"]), corpo=9)
                tabella = _tabella(doc, 2)
                for livello in scheda["livelli"]:  # type: ignore[index]
                    _riga_tabella(
                        tabella, [livello["etichetta"], livello["descrizione"]], corpo=9
                    )
    return doc


COSTRUTTORI = {
    "programmazione": _documento_programmazione,
    "preventivo": _documento_preventivo,
    "fondanti": _documento_fondanti,
    "certificazione": _documento_certificazione,
}


def genera(prog: Programmazione, tipo: str, quando: datetime | None = None) -> Path:
    return genera_in(prog, tipo, cartella_output(prog), quando)


def genera_in(
    prog: Programmazione, tipo: str, cartella: Path, quando: datetime | None = None
) -> Path:
    if tipo not in COSTRUTTORI:
        raise ValueError(f"tipo di documento sconosciuto: {tipo}")
    quando = quando or datetime.now()
    documento = COSTRUTTORI[tipo](prog, f"{quando:%d_%m_%y}")
    cartella.mkdir(parents=True, exist_ok=True)
    percorso = cartella / nome_file(prog, tipo, quando)
    documento.save(str(percorso))
    return percorso
