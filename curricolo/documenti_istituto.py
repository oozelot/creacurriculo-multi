"""Documenti d'istituto prodotti in modalita' ADMIN.

Riproduce i due documenti del Form5 del VB6 (modelli 13/14/15 e 17/18):
il curricolo orizzontale delle competenze in chiave europea e la progettazione
per competenze per aree multidisciplinari. Sono generati con python-docx,
senza campi modulo, e salvati in ADMIN/output.
"""

from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable

from docx.shared import Cm

from . import archivio, catalogo, educazione_civica
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
Avanzamento = Callable[[str], None]

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
    etichetta_valore(doc, "UNITA' DI APPRENDIMENTO:", unita.titolo)
    etichetta_valore(doc, "FACENTE PARTE DEL MODULO:", modulo.titolo)

    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE COMPETENZE PECUP "
        "DELLA DISCIPLINA",
        unita.competenze_pecup,
        unita.codici_competenze_pecup,
        solo_codici=solo_codici,
    )
    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE ABILITA' PECUP "
        "DELLA DISCIPLINA",
        unita.abilita,
        unita.codici_abilita,
        solo_codici=solo_codici,
    )
    blocco_elenco(
        doc,
        "CONTRIBUTO DELL'UNITA' DI APPRENDIMENTO AL CONSEGUIMENTO DELLE CONOSCENZE PECUP "
        "DELLA DISCIPLINA",
        unita.conoscenze,
        unita.codici_conoscenze,
        solo_codici=solo_codici,
    )
    _tabella_livelli(doc, unita)


def _tabella_livelli(doc, unita) -> None:
    livelli = tabella(doc, 1)
    riga_unita(livelli, "LIVELLI DI COMPETENZA DELLA UNITA' DI APPRENDIMENTO")
    voci = [
        ("BASE (determina gli obiettivi fondanti dell'unita' di apprendimento):", unita.competenze_minime),
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
    avanzamento: Avanzamento | None = None,
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
            paragrafo(doc, "Nessuna unita' di apprendimento dichiara questa competenza.", corpo=10)
            continue
        for voce in voci:
            prog, modulo, unita = voce["programmazione"], voce["modulo"], voce["unita"]
            numero_modulo = next(i for i, voce_modulo in enumerate(prog.moduli, 1) if voce_modulo is modulo)
            numero_unita = next(i for i, voce_unita in enumerate(modulo.unita, 1) if voce_unita is unita)
            if avanzamento is not None:
                avanzamento(f"Sviluppo modulo {numero_modulo} - unita' {numero_unita}")
            paragrafo(doc)
            _scheda_unita(doc, voce, solo_codici=solo_codici)

    sigle = "_".join(SIGLE_COMPETENZE[p] for p in sorted(competenze) if p in SIGLE_COMPETENZE)
    nome = f"curr_orizz_{sigle}_{classe}_{_sigle(indirizzi)}_{giorno:%d_%m_%y}.docx"
    return _salva(doc, nome)


def genera_multidisciplinare(
    classe: str,
    indirizzi: list[str],
    aree: list[str],
    giorno: date | None = None,
    avanzamento: Avanzamento | None = None,
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
            paragrafo(doc, "Nessuna unita' di apprendimento dichiara questa area.", corpo=10)
            continue
        for voce in voci:
            prog, modulo, unita = voce["programmazione"], voce["modulo"], voce["unita"]
            numero_modulo = next(i for i, voce_modulo in enumerate(prog.moduli, 1) if voce_modulo is modulo)
            numero_unita = next(i for i, voce_unita in enumerate(modulo.unita, 1) if voce_unita is unita)
            if avanzamento is not None:
                avanzamento(f"Sviluppo modulo {numero_modulo} - unita' {numero_unita}")
            paragrafo(doc)
            etichetta_valore(doc, "DISCIPLINA:", prog.disciplina, 12)
            etichetta_valore(doc, "UNITA' DI APPRENDIMENTO:", unita.titolo)
            etichetta_valore(doc, "FACENTE PARTE DEL MODULO:", modulo.titolo)
            etichetta_valore(doc, "Svolto di norma nel periodo:", modulo.periodo)
            _dettaglio_educazione_civica(doc, prog, unita)
            paragrafo(doc, "ARGOMENTI TRATTATI:", grassetto=True)
            testo_multiriga(doc, unita.argomenti)
            _tabella_livelli(doc, unita)

    sigla_area = "".join((aree[0][:4] if aree else "area").split()).lower()
    nome = f"program_multidisc_{sigla_area}_{classe}_{_sigle(indirizzi)}_{giorno:%d_%m_%y}.docx"
    return _salva(doc, nome)


def _dettaglio_educazione_civica(doc: Document, prog, unita) -> None:
    """Scrive i dati Ed. civica solo quando presenti anche nei vecchi archivi."""
    voci_selezionate = [str(voce).strip() for voce in (unita.ec_voci or []) if str(voce).strip()]
    ore = str(unita.ec_ore or "").strip()
    if not voci_selezionate or not ore:
        return

    piano = educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina)
    if not piano:
        return
    voci_piano = {
        str(voce.get("voce", "")).strip(): voce
        for voce in piano.get("voci", [])
        if str(voce.get("voce", "")).strip()
    }
    gruppi: dict[str, list[str]] = {}
    for nome_voce in voci_selezionate:
        voce = voci_piano.get(nome_voce)
        if not voce:
            continue
        macroarea = str(voce.get("macroarea") or piano.get("macroarea") or "").strip()
        if not macroarea:
            continue
        gruppi.setdefault(macroarea, []).append(nome_voce)

    for macroarea, tematiche in gruppi.items():
        paragrafo(
            doc,
            f"MACROAREA: {macroarea}, Tematica: {', '.join(tematiche)}, ore svolte = {ore}",
        )


def genera_educazione_civica(
    corso: str,
    classe: str,
    *,
    giorno: date | None = None,
    avanzamento: Avanzamento | None = None,
) -> Path:
    giorno = giorno or date.today()
    indirizzi = {
        "CAT": ("COSTRUZIONI, AMBIENTE E TERRITORIO", "CAT"),
        "GRAFICO": ("GRAFICA E COMUNICAZIONE", "GRAFICO"),
        "AGRARIO": ("AGRARIA, AGROALIMENTARE E AGROINDUSTRIA", "AGRARIO"),
    }
    doc = crea_documento()
    for indice_classe, classe_corrente in enumerate(("PRIMA", "SECONDA", "TERZA", "QUARTA", "QUINTA")):
        for indice_corso, (corso_corrente, (indirizzo_testo, corso_db)) in enumerate(indirizzi.items()):
            if indice_classe or indice_corso:
                doc.add_page_break()
            paragrafo(doc, "PROSPETTO ORARIO EDUCAZIONE CIVICA", grassetto=True, centrato=True, corpo=14)
            paragrafo(doc, f"INDIRIZZO: {indirizzo_testo}", grassetto=True, centrato=True, corpo=12)
            anno = ("1°", "2°", "3°", "4°", "5°")[indice_classe]
            paragrafo(doc, f"{anno} ANNO", grassetto=True, centrato=True, corpo=12)

            indirizzi_catalogo = (
                ("AGRARIO (tutte le articolazioni)", "AGRARIO (p.t.)", "AGRARIO (g.a.t.)", "AGRARIO (eno)")
                if corso_db == "AGRARIO" else (corso_db,)
            )
            discipline = catalogo.discipline_normalizzate(classe_corrente, list(indirizzi_catalogo))
            piani = {
                catalogo.nome_disciplina_visualizzato(piano["disciplina"]): piano
                for piano in educazione_civica.piani_contesto(corso_db, classe_corrente, "COMUNE")
            }
            tabella_piano = tabella(doc, 4)
            tabella_piano._larghezze_personalizzate = [Cm(6.3), Cm(1.0), Cm(5.5), Cm(2.2)]
            riga_tabella(
                tabella_piano,
                ["DISCIPLINE", "ORE", "TEMATICA", "PERIODO"],
                grassetto=True,
                corpo=10,
                corpi=(10, 8, 10, 10),
            )
            for disciplina in discipline:
                piano = piani.get(disciplina)
                if not piano or not piano.get("voci"):
                    continue
                voci = [voce for voce in piano["voci"] if int(voce.get("ore", 0) or 0) > 0]
                if not voci:
                    continue
                gruppi = {}
                for voce in voci:
                    gruppi.setdefault(voce.get("macroarea") or piano.get("macroarea", ""), []).append(voce)
                conferme = list(piano.get("conferme", {}).values())
                prima_disciplina = True
                for macroarea, voci_macroarea in gruppi.items():
                    riga_tabella(tabella_piano, [disciplina if prima_disciplina else "", str(piano.get("ore_disciplina", "")) if prima_disciplina else "", macroarea, ""], grassetto=True, corpo=10)
                    prima_disciplina = False
                    for voce in voci_macroarea:
                        conferma = next(
                            (dati for dati in conferme if voce.get("voce") in dati.get("voci", [])),
                            next(iter(conferme), None) if conferme and not any("voci" in dati for dati in conferme) else None,
                        )
                        periodo = f"{conferma.get('quadrimestre')} quadrimestre" if conferma and conferma.get("quadrimestre") else "DA CONF."
                        riga_tabella(tabella_piano, ["", "", f"- {voce.get('voce', '')} ({voce.get('ore', 0)})", periodo], corpo=8)
    momento = datetime.now()
    nome = f"program_educazione_civica_{momento:%d_%m_%y-%H.%M}.docx"
    return _salva(doc, nome)


def _salva(doc: Document, nome: str) -> Path:
    CARTELLA_ADMIN_OUTPUT.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA_ADMIN_OUTPUT / nome
    doc.save(str(percorso))
    return percorso


def converti_pdf(percorso_word: Path) -> Path:
    """Converte un documento Word in PDF usando LibreOffice o Microsoft Word."""
    percorso_word = Path(percorso_word).resolve()
    if not percorso_word.is_file():
        raise FileNotFoundError(f"File Word non trovato: {percorso_word}")

    percorso_pdf = percorso_word.with_suffix(".pdf").resolve()
    percorso_pdf.unlink(missing_ok=True)

    comandi = [shutil.which("soffice"), shutil.which("libreoffice")]
    comandi.extend(
        str(percorso)
        for percorso in (
            Path("C:/Program Files/LibreOffice/program/soffice.exe"),
            Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
            Path.home() / "AppData/Local/Programs/LibreOffice/program/soffice.exe",
        )
        if percorso.is_file()
    )
    if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").is_file():
        comandi.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    eseguibile = next((comando for comando in comandi if comando), None)
    if eseguibile is not None:
        with tempfile.TemporaryDirectory(prefix="creacurricolo-lo-") as profilo:
            comando = [
                eseguibile,
                "--headless",
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", str(percorso_pdf.parent),
                f"-env:UserInstallation={Path(profilo).as_uri()}",
                str(percorso_word),
            ]
            risultato = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        if risultato.returncode == 0 and percorso_pdf.is_file():
            return percorso_pdf
        dettaglio = (risultato.stderr or risultato.stdout).strip()
    else:
        dettaglio = ""

    if os.name == "nt":
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            pass
        else:
            pythoncom.CoInitialize()
            word = None
            documento = None
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                documento = word.Documents.Open(str(percorso_word))
                documento.SaveAs2(str(percorso_pdf), FileFormat=17)
                if percorso_pdf.is_file():
                    return percorso_pdf
            except Exception as errore:
                dettaglio = str(errore)
            finally:
                if documento is not None:
                    documento.Close(False)
                if word is not None:
                    word.Quit()
                pythoncom.CoUninitialize()

    raise RuntimeError(
        "Impossibile convertire il documento Word in PDF. "
        "Installare LibreOffice oppure Microsoft Word. Il documento Word "
        "e' stato comunque creato."
        + (f" Dettaglio: {dettaglio}" if dettaglio else "")
    )
