"""Griglia del livello di completamento della raccolta dati (Form5 del VB6).

Righe: sigle delle discipline. Colonne: una per classe, suddivisa negli indirizzi.
Colore delle celle: grigio = non prevista, rosso = prevista ma non ricevuta,
verde = ricevuta (con il numero di programmazioni arrivate).
"""

from __future__ import annotations

from typing import Any

from . import archivio, catalogo
from .config import CLASSI, INDIRIZZI

# Iniziali delle colonne come nella griglia originale.
COLONNE = ["c", "C", "G", "A", "g", "p", "e"]
# Le articolazioni agrarie esistono solo dal triennio.
COLONNE_BIENNIO = 4


def colonne_classe(classe: str) -> list[dict[str, str]]:
    quante = COLONNE_BIENNIO if classe in CLASSI[:2] else len(COLONNE)
    return [
        {"iniziale": COLONNE[i], "indirizzo": INDIRIZZI[i]} for i in range(quante)
    ]


def griglia() -> dict[str, Any]:
    conteggi = archivio.completamento()
    previste: dict[tuple[str, str, str], bool] = {}
    nomi: dict[str, set[str]] = {}

    def registra(disciplina: str, classe: str, indirizzo: str, sigla: str) -> None:
        previste[(sigla, classe, indirizzo)] = True
        nomi.setdefault(sigla, set()).add(disciplina)

    for voce in catalogo.offerta():
        registra(voce["disciplina"], voce["classe"], voce["indirizzo"], voce["sigla"])

    # Le varianti "solo se specifica per..." condividono la sigla e quindi la stessa riga.
    ricevuti: dict[tuple[str, str, str], int] = {}
    for (disciplina, classe, indirizzo), quanti in conteggi.items():
        sigla = catalogo.sigla_disciplina(disciplina)
        chiave = (sigla, classe, indirizzo)
        ricevuti[chiave] = ricevuti.get(chiave, 0) + quanti
        registra(disciplina, classe, indirizzo, sigla)

        # Una programmazione comune copre anche CAT, Grafico e Agrario della stessa classe.
        if indirizzo == "COMUNE":
            percorsi_comuni = INDIRIZZI[1:]
            if classe in CLASSI[:2]:
                percorsi_comuni = INDIRIZZI[1:4]
            for percorso in percorsi_comuni:
                chiave_coperta = (sigla, classe, percorso)
                ricevuti[chiave_coperta] = ricevuti.get(chiave_coperta, 0) + quanti

        # Nel triennio la programmazione agraria comune copre tutte le articolazioni.
        if indirizzo == "AGRARIO (tutte le articolazioni)" and classe in CLASSI[2:]:
            for percorso in INDIRIZZI[4:]:
                chiave_coperta = (sigla, classe, percorso)
                ricevuti[chiave_coperta] = ricevuti.get(chiave_coperta, 0) + quanti

    # La colonna "c" del triennio diventa verde quando sono coperte tutte le
    # combinazioni previste per la materia nell'anno, senza inventare un conteggio.
    comuni_completi: set[tuple[str, str, str]] = set()
    agrari_completi: set[tuple[str, str, str]] = set()
    for sigla in nomi:
        for classe in CLASSI:
            indirizzi_classe = INDIRIZZI[1:4] if classe in CLASSI[:2] else INDIRIZZI[1:]
            percorsi_previsti = [
                indirizzo for indirizzo in indirizzi_classe
                if previste.get((sigla, classe, indirizzo))
            ]
            if percorsi_previsti and all(ricevuti.get((sigla, classe, indirizzo))
                                          for indirizzo in percorsi_previsti):
                comuni_completi.add((sigla, classe, "COMUNE"))

            if classe not in CLASSI[2:]:
                continue
            articolazioni_agrarie = [
                indirizzo for indirizzo in INDIRIZZI[4:]
                if previste.get((sigla, classe, indirizzo))
            ]
            if articolazioni_agrarie and all(ricevuti.get((sigla, classe, indirizzo))
                                              for indirizzo in articolazioni_agrarie):
                agrari_completi.add((sigla, classe, "AGRARIO (tutte le articolazioni)"))

    righe = []
    for sigla in sorted(nomi):
        celle_per_classe = []
        for classe in CLASSI:
            celle = []
            for colonna in colonne_classe(classe):
                chiave = (sigla, classe, colonna["indirizzo"])
                quanti = ricevuti.get(chiave, 0)
                if quanti or chiave in comuni_completi or chiave in agrari_completi:
                    stato = "presente"
                elif not previste.get(chiave):
                    stato = "inattivo"
                else:
                    stato = "mancante"
                celle.append({"stato": stato, "quanti": quanti, **colonna})
            celle_per_classe.append({"classe": classe, "celle": celle})
        righe.append(
            {
                "disciplina": " / ".join(sorted(nomi[sigla])),
                "sigla": sigla,
                "classi": celle_per_classe,
            }
        )

    attese = len(previste)
    ricevute = sum(1 for chiave in previste if ricevuti.get(chiave))
    return {
        "classi": [{"nome": c, "colonne": colonne_classe(c)} for c in CLASSI],
        "righe": righe,
        "attese": attese,
        "ricevute": ricevute,
        "programmazioni": sum(conteggi.values()),
    }
