"""Catalogo e persistenza del piano di educazione civica."""

from __future__ import annotations

import json
from typing import Any

from .config import CARTELLA_LEGACY
from .db import connessione

MACROAREE = (
    "COSTITUZIONE",
    "EDUCAZIONE SOSTENIBILE",
    "CITTADINANZA DIGITALE",
)

ARTICOLAZIONI_AGRARIO = ("PT", "GAT", "ENO")


def quadrimestre_periodo(periodo: str) -> str:
    """Restituisce il quadrimestre in base alla sezione del catalogo dei periodi."""
    valore = periodo.strip().lower()
    if not valore:
        return ""
    percorso_periodi = CARTELLA_LEGACY / "moduli" / "periodi.ini"
    periodi = [
        riga.strip().lower()
        for riga in percorso_periodi.read_text(encoding="cp1252").splitlines()
        if riga.strip()
    ]
    try:
        indice_periodo = periodi.index(valore)
        indice_secondo_quadrimestre = periodi.index("secondo quadrimestre")
    except ValueError:
        return ""
    return "I" if indice_periodo < indice_secondo_quadrimestre else "II"


def contesto(indirizzo: str) -> tuple[str, str]:
    """Traduce l'indirizzo della programmazione nel corso Admin e nell'articolazione."""
    valore = indirizzo.upper()
    if "CAT" in valore:
        return "CAT", "COMUNE"
    if "GRAFICO" in valore:
        return "GRAFICO", "COMUNE"
    if "G.A.T" in valore:
        return "AGRARIO", "GAT"
    if "P.T." in valore:
        return "AGRARIO", "PT"
    if "ENO" in valore:
        return "AGRARIO", "ENO"
    if "AGRARIO" in valore:
        return "AGRARIO", "COMUNE"
    return valore, "COMUNE"


def _corsi_piano(corso: str) -> tuple[str, ...]:
    return (corso,) if corso != "COMUNE" else ("CAT", "GRAFICO", "AGRARIO")


def contesti_per_percorsi(
    classe: str, percorsi: list[tuple[str, str]]
) -> list[tuple[str, str, str]]:
    """Contesti EC interessati dai percorsi scolastici di una materia."""
    corsi = set()
    articolazioni = set()
    for classe_percorso, indirizzo in percorsi:
        if classe_percorso != classe:
            continue
        if indirizzo == "COMUNE":
            corsi.update(("CAT", "GRAFICO"))
            if classe in ("PRIMA", "SECONDA"):
                corsi.add("AGRARIO")
        elif indirizzo == "CAT":
            corsi.add("CAT")
        elif indirizzo == "GRAFICO":
            corsi.add("GRAFICO")
        elif indirizzo == "AGRARIO (tutte le articolazioni)":
            corsi.add("AGRARIO")
            articolazioni.add("COMUNE")
        elif indirizzo == "AGRARIO (p.t.)":
            corsi.add("AGRARIO")
            articolazioni.add("PT")
        elif indirizzo == "AGRARIO (g.a.t.)":
            corsi.add("AGRARIO")
            articolazioni.add("GAT")
        elif indirizzo == "AGRARIO (eno)":
            corsi.add("AGRARIO")
            articolazioni.add("ENO")
    risultati = []
    for corso in ("CAT", "GRAFICO", "AGRARIO"):
        if corso not in corsi:
            continue
        if corso != "AGRARIO" or classe in ("PRIMA", "SECONDA"):
            risultati.append((corso, classe, "COMUNE"))
        else:
            specifiche = articolazioni.intersection(ARTICOLAZIONI_AGRARIO)
            if "COMUNE" in articolazioni or not specifiche:
                risultati.append((corso, classe, "COMUNE"))
            risultati.extend(
                (corso, classe, articolazione)
                for articolazione in ARTICOLAZIONI_AGRARIO
                if articolazione in specifiche
            )
    return risultati


def materia_compatibile_con_contesto(
    percorsi: list[tuple[str, str]], corso: str, classe: str, articolazione: str
) -> bool:
    """Verifica che una materia sia insegnata nel contesto di Educazione civica."""
    indirizzi = {indirizzo for classe_percorso, indirizzo in percorsi if classe_percorso == classe}
    if corso == "CAT":
        return bool(indirizzi.intersection({"COMUNE", "CAT"}))
    if corso == "GRAFICO":
        return bool(indirizzi.intersection({"COMUNE", "GRAFICO"}))
    if corso != "AGRARIO":
        return False
    comune_agrario = "AGRARIO (tutte le articolazioni)" in indirizzi
    specifiche = {
        articolazione_indirizzo
        for articolazione_indirizzo, sigla in (
            ("AGRARIO (p.t.)", "PT"),
            ("AGRARIO (g.a.t.)", "GAT"),
            ("AGRARIO (eno)", "ENO"),
        )
        if articolazione_indirizzo in indirizzi
    }
    if classe in ("PRIMA", "SECONDA"):
        return comune_agrario or "COMUNE" in indirizzi
    if articolazione == "COMUNE":
        return comune_agrario
    indirizzo_per_articolazione = {
        "PT": "AGRARIO (p.t.)",
        "GAT": "AGRARIO (g.a.t.)",
        "ENO": "AGRARIO (eno)",
    }.get(articolazione)
    if indirizzo_per_articolazione is None:
        return False
    if indirizzo_per_articolazione in specifiche:
        return True
    return comune_agrario and not specifiche


def piani_materia_nei_contesti(
    disciplina: str, contesti: list[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    """Restituisce i piani civici della materia nei soli contesti interessati."""
    if not contesti:
        return []
    from .catalogo import nome_disciplina_visualizzato

    nome = nome_disciplina_visualizzato(disciplina).casefold()
    risultato = []
    with connessione() as conn:
        for corso, classe, articolazione in contesti:
            righe = conn.execute(
                "SELECT disciplina, dati FROM educazione_civica_piani "
                "WHERE corso = ? AND classe = ? AND articolazione = ? ORDER BY disciplina",
                (corso, classe, articolazione),
            )
            for riga in righe:
                if nome_disciplina_visualizzato(riga["disciplina"]).casefold() != nome:
                    continue
                risultato.append({
                    "corso": corso,
                    "classe": classe,
                    "articolazione": articolazione,
                    "disciplina": riga["disciplina"],
                    "dati": json.loads(riga["dati"]),
                })
    return risultato


def _piano_per_docente(
    classe: str, indirizzo: str, disciplina: str
) -> tuple[str, dict[str, Any]] | None:
    corso, articolazione = contesto(indirizzo)
    from .catalogo import nome_disciplina_visualizzato

    nome = nome_disciplina_visualizzato(disciplina).casefold()
    contesti = (articolazione, "COMUNE") if articolazione != "COMUNE" else ("COMUNE",)
    for corso_piano in _corsi_piano(corso):
        for contesto_piano in contesti:
            for candidato in piani_contesto(corso_piano, classe, contesto_piano):
                if nome_disciplina_visualizzato(candidato["disciplina"]).casefold() == nome:
                    return corso_piano, candidato
    return None


def conferme_per_articolazione(
    dati: dict[str, Any] | None,
    articolazione: str,
    ambiti_archiviati: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Filtra le conferme di un piano comune per l'articolazione richiesta."""
    conferme = (dati or {}).get("conferme", {})
    if articolazione not in ARTICOLAZIONI_AGRARIO:
        return dict(conferme)
    ambiti_archiviati = ambiti_archiviati or {}
    risultato = {}
    for chiave, conferma in conferme.items():
        if not isinstance(conferma, dict):
            continue
        ambito = conferma.get("ambito_articolazioni")
        if not isinstance(ambito, list):
            ambito = ambiti_archiviati.get(chiave, [])
        if "TUTTE" in ambito or articolazione in ambito:
            risultato[chiave] = conferma
    return risultato


def ambiti_conferme_archiviate(classe: str) -> dict[str, list[str]]:
    """Ricostruisce l'ambito delle conferme legacy dai file INI archiviati."""
    ambiti: dict[str, set[tuple[str, ...]]] = {}
    with connessione() as conn:
        righe = conn.execute(
            "SELECT cognome, nome, classe, indirizzo, disciplina, contenuto "
            "FROM ricevuti WHERE classe = ?",
            (classe,),
        ).fetchall()
    for riga in righe:
        corso, articolazione = contesto(riga["indirizzo"])
        if corso == "AGRARIO" and articolazione in ARTICOLAZIONI_AGRARIO:
            ambito = (articolazione,)
        elif corso in ("AGRARIO", "COMUNE"):
            ambito = ("TUTTE",)
        else:
            continue
        try:
            moduli = json.loads(riga["contenuto"]).get("moduli", [])
        except (TypeError, json.JSONDecodeError):
            continue
        for numero_modulo, modulo in enumerate(moduli, 1):
            for indice_ud, unita in enumerate(modulo.get("unita", []), 1):
                try:
                    multidisciplinare = [
                        int(valore) for valore in unita.get("multidisciplinare", [])
                    ]
                except (TypeError, ValueError):
                    continue
                if (
                    2 not in multidisciplinare
                    or not unita.get("ec_voci")
                    or not unita.get("ec_ore")
                ):
                    continue
                chiave = chiave_conferma(
                    riga["cognome"], riga["nome"], riga["disciplina"],
                    numero_modulo, indice_ud,
                )
                ambiti.setdefault(chiave, set()).add(ambito)
    return {
        chiave: list(ambito)
        for chiave, valori in ambiti.items()
        if len(valori) == 1
        for ambito in valori
    }


def piano_per_docente(classe: str, indirizzo: str, disciplina: str) -> dict[str, Any] | None:
    risultato = _piano_per_docente(classe, indirizzo, disciplina)
    if not risultato:
        return None
    corso, dati = risultato
    corso_indirizzo, articolazione = contesto(indirizzo)
    if (
        corso == "AGRARIO"
        and corso_indirizzo == "AGRARIO"
        and classe not in ("PRIMA", "SECONDA")
        and articolazione in ARTICOLAZIONI_AGRARIO
    ):
        dati = dict(dati)
        dati["conferme"] = conferme_per_articolazione(
            dati, articolazione, ambiti_conferme_archiviate(classe)
        )
    return dati


def piano_completo(dati: dict[str, Any] | None) -> bool:
    if not dati or not dati.get("voci"):
        return False
    return all(int(voce.get("ore", 0) or 0) >= 33 for voce in dati["voci"])


def piano_disponibile(dati: dict[str, Any] | None) -> bool:
    return bool(dati and any(int(voce.get("ore", 0) or 0) > 0 for voce in dati.get("voci", [])))


def catalogo_voci() -> dict[str, list[str]]:
    """Legge il catalogo persistente, aggiornato eventualmente all'avvio dal file Excel."""
    risultato = {macroarea: [] for macroarea in MACROAREE}
    with connessione() as conn:
        righe = conn.execute(
            "SELECT macroarea, voce FROM educazione_civica_catalogo ORDER BY macroarea, posizione"
        ).fetchall()
    for riga in righe:
        if riga["macroarea"] in risultato:
            risultato[riga["macroarea"]].append(riga["voce"])
    return risultato


def _leggi_catalogo_excel() -> dict[str, list[str]] | None:
    percorso = CARTELLA_LEGACY / "modelli_doc" / "edcivica.xlsx"
    if not percorso.is_file():
        return None
    from openpyxl import load_workbook

    risultato = {macroarea: [] for macroarea in MACROAREE}
    viste = {macroarea: set() for macroarea in MACROAREE}
    proprietari: set[str] = set()
    macroarea: str | None = None
    foglio = load_workbook(percorso, data_only=True, read_only=True).active
    for riga in foglio.iter_rows(min_col=1, max_col=1, values_only=True):
        valore = str(riga[0] or "").strip()
        if not valore:
            continue
        normalizzato = valore.upper()
        if normalizzato in MACROAREE and normalizzato != macroarea:
            macroarea = normalizzato
        elif macroarea is not None:
            chiave = " ".join(valore.casefold().split())
            if chiave not in viste[macroarea] and chiave not in proprietari:
                risultato[macroarea].append(valore)
                viste[macroarea].add(chiave)
                proprietari.add(chiave)
    return risultato


def sincronizza_catalogo_file() -> None:
    """Sostituisce il catalogo DB solo se il file aggiornabile è disponibile."""
    catalogo = _leggi_catalogo_excel()
    if catalogo is None:
        return
    with connessione() as conn:
        conn.execute("DELETE FROM educazione_civica_catalogo")
        conn.executemany(
            "INSERT INTO educazione_civica_catalogo (macroarea, voce, posizione) VALUES (?, ?, ?)",
            [
                (macroarea, voce, posizione)
                for macroarea, voci in catalogo.items()
                for posizione, voce in enumerate(voci, 1)
            ],
        )
        conn.commit()


def normalizza_piano(dati: dict[str, Any] | None) -> dict[str, Any] | None:
    """Allinea ogni voce alla macroarea ufficiale e rimuove duplicati storici."""
    if dati is None:
        return None
    catalogo = catalogo_voci()
    associazioni = {
        " ".join(voce.casefold().split()): macroarea
        for macroarea, voci in catalogo.items()
        for voce in voci
    }
    voci_normalizzate: dict[str, dict[str, Any]] = {}
    for voce in dati.get("voci", []):
        nome = " ".join(str(voce.get("voce", "")).strip().split())
        if not nome:
            continue
        macroarea = associazioni.get(nome.casefold())
        if not macroarea:
            continue
        chiave = nome.casefold()
        ore = int(voce.get("ore", 0) or 0)
        precedente = voci_normalizzate.get(chiave)
        if precedente is None or ore > int(precedente.get("ore", 0) or 0):
            voci_normalizzate[chiave] = {"macroarea": macroarea, "voce": nome, "ore": ore}
    risultato = dict(dati)
    risultato["voci"] = list(voci_normalizzate.values())
    risultato["ore_disciplina"] = sum(int(voce.get("ore", 0) or 0) for voce in risultato["voci"])
    return risultato


def piano(corso: str, classe: str, articolazione: str, disciplina: str) -> dict[str, Any] | None:
    with connessione() as conn:
        riga = conn.execute(
            "SELECT dati FROM educazione_civica_piani WHERE corso = ? AND classe = ? AND articolazione = ? AND disciplina = ?",
            (corso, classe, articolazione, disciplina),
        ).fetchone()
    return normalizza_piano(json.loads(riga["dati"])) if riga else None


def salva_piano(corso: str, classe: str, articolazione: str, disciplina: str, dati: dict[str, Any]) -> None:
    dati = normalizza_piano(dati) or dati
    contenuto = json.dumps(dati, ensure_ascii=False)
    with connessione() as conn:
        conn.execute(
            """
            INSERT INTO educazione_civica_piani
                (corso, classe, articolazione, disciplina, dati, aggiornato_il)
            VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(corso, classe, articolazione, disciplina) DO UPDATE SET
                dati = excluded.dati,
                aggiornato_il = excluded.aggiornato_il
            """,
            (corso, classe, articolazione, disciplina, contenuto),
        )
        conn.commit()


def elimina_piano(corso: str, classe: str, articolazione: str, disciplina: str) -> None:
    with connessione() as conn:
        conn.execute(
            "DELETE FROM educazione_civica_piani WHERE corso = ? AND classe = ? AND articolazione = ? AND disciplina = ?",
            (corso, classe, articolazione, disciplina),
        )
        conn.commit()


def registra_conferma(classe: str, indirizzo: str, disciplina: str, chiave: str, dati: dict[str, Any]) -> bool:
    corso, articolazione = contesto(indirizzo)
    from .catalogo import nome_disciplina_visualizzato

    nome_disciplina = nome_disciplina_visualizzato(disciplina).casefold()
    corsi = _corsi_piano(corso)
    salvata = False
    for corso_piano in corsi:
        piano_selezionato = None
        for articolazione_piano in dict.fromkeys((articolazione, "COMUNE")):
            piano_selezionato = next(
                (
                    candidato
                    for candidato in piani_contesto(corso_piano, classe, articolazione_piano)
                    if nome_disciplina_visualizzato(candidato["disciplina"]).casefold()
                    == nome_disciplina
                ),
                None,
            )
            if piano_selezionato is not None:
                break
        if piano_selezionato is None:
            continue
        articolazione_piano = piano_selezionato["articolazione"]
        disciplina_piano = piano_selezionato["disciplina"]
        piano_dati = piano(corso_piano, classe, articolazione_piano, disciplina_piano)
        if not piano_disponibile(piano_dati):
            continue
        conferme = dict(piano_dati.get("conferme", {}))
        conferma = dict(dati)
        if corso_piano == "AGRARIO" and classe not in ("PRIMA", "SECONDA"):
            conferma["ambito_articolazioni"] = (
                [articolazione]
                if corso == "AGRARIO" and articolazione in ARTICOLAZIONI_AGRARIO
                else ["TUTTE"]
            )
        conferme[chiave] = conferma
        piano_dati["conferme"] = conferme
        salva_piano(corso_piano, classe, articolazione_piano, disciplina_piano, piano_dati)
        salvata = True
    return salvata


def chiave_conferma(
    cognome: str,
    nome: str,
    disciplina: str,
    numero_modulo: int,
    indice_ud: int,
    classe: str = "",
    indirizzo: str = "",
) -> str:
    chiave = f"{cognome} {nome}|{disciplina}"
    if classe or indirizzo:
        chiave += f"|{classe}|{indirizzo}"
    return f"{chiave}|M{numero_modulo}|UD{indice_ud}"


def rimuovi_conferme_programmazione(prog: Any) -> None:
    corso, articolazione = contesto(prog.indirizzo)
    from .catalogo import nome_disciplina_visualizzato

    nome_disciplina = nome_disciplina_visualizzato(prog.disciplina).casefold()
    chiavi = set()
    for numero_modulo, modulo in enumerate(prog.moduli, 1):
        for indice_ud, _ in enumerate(modulo.unita, 1):
            chiavi.add(
                chiave_conferma(
                    prog.cognome, prog.nome, prog.disciplina,
                    numero_modulo, indice_ud, prog.classe, prog.indirizzo,
                )
            )
            chiavi.add(
                chiave_conferma(
                    prog.cognome, prog.nome, prog.disciplina,
                    numero_modulo, indice_ud,
                )
            )
            chiavi.add(f"{prog.cognome} {prog.nome}|M{numero_modulo}|UD{indice_ud}")
    for corso_piano in _corsi_piano(corso):
        for articolazione_piano in {articolazione, "COMUNE"}:
            for candidato in piani_contesto(corso_piano, prog.classe, articolazione_piano):
                if (
                    nome_disciplina_visualizzato(candidato["disciplina"]).casefold()
                    != nome_disciplina
                ):
                    continue
                disciplina_piano = candidato["disciplina"]
                piano_dati = piano(
                    corso_piano, prog.classe, articolazione_piano, disciplina_piano
                )
                conferme = dict(piano_dati.get("conferme", {}))
                nuove_conferme = {
                    chiave: dati for chiave, dati in conferme.items() if chiave not in chiavi
                }
                if nuove_conferme != conferme:
                    piano_dati["conferme"] = nuove_conferme
                    salva_piano(
                        corso_piano,
                        prog.classe,
                        articolazione_piano,
                        disciplina_piano,
                        piano_dati,
                    )


def sincronizza_conferme_programmazione(prog: Any) -> None:
    rimuovi_conferme_programmazione(prog)
    for numero_modulo, modulo in enumerate(prog.moduli, 1):
        for indice_ud, unita in enumerate(modulo.unita, 1):
            if 2 not in unita.multidisciplinare or not unita.ec_voci or not unita.ec_ore:
                continue
            registra_conferma(
                prog.classe,
                prog.indirizzo,
                prog.disciplina,
                chiave_conferma(
                    prog.cognome, prog.nome, prog.disciplina,
                    numero_modulo, indice_ud, prog.classe, prog.indirizzo,
                ),
                {
                    "voci": list(unita.ec_voci),
                    "quadrimestre": unita.ec_quadrimestre,
                    "periodo": unita.ec_periodo,
                    "ore": unita.ec_ore,
                },
            )


def ore_utilizzate_per_voce(dati: dict[str, Any] | None) -> dict[str, int]:
    """Somma le ore confermate per ogni voce nella materia e nella classe."""
    risultato: dict[str, int] = {}
    for conferma in (dati or {}).get("conferme", {}).values():
        try:
            ore = int(conferma.get("ore", 0) or 0)
        except (TypeError, ValueError):
            continue
        for voce in conferma.get("voci", []):
            risultato[voce] = risultato.get(voce, 0) + ore
    return risultato


def piani_contesto(corso: str, classe: str, articolazione: str = "") -> list[dict[str, Any]]:
    with connessione() as conn:
        righe = conn.execute(
            "SELECT disciplina, articolazione, dati FROM educazione_civica_piani WHERE corso = ? AND classe = ? AND articolazione = ? ORDER BY disciplina",
            (corso, classe, articolazione),
        ).fetchall()
    risultato = []
    for riga in righe:
        dati_originali = json.loads(riga["dati"])
        dati_normalizzati = normalizza_piano(dati_originali) or {}
        if dati_normalizzati != dati_originali:
            salva_piano(corso, classe, riga["articolazione"], riga["disciplina"], dati_normalizzati)
        risultato.append({
            "disciplina": riga["disciplina"],
            "articolazione": riga["articolazione"],
            **dati_normalizzati,
        })
    return risultato


def stato_piano(dati: dict[str, Any] | None) -> str:
    if not dati:
        return "inattivo"
    return "verde" if piano_completo(dati) else "rosso"