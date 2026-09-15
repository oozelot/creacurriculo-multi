"""Modello dati della programmazione.

La persistenza usa le stesse cartelle e gli stessi file INI del VB6 (vedi legacy.py),
cosi' i lavori prodotti dal vecchio programma restano leggibili e viceversa.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import legacy
from .config import (
    MAX_ABILITA,
    MAX_COMPETENZE_PECUP,
    MAX_CONOSCENZE,
    MAX_OPZIONI_ALTRO,
)


def _lista(valore: Any, lunghezza: int) -> list[str]:
    voci = list(valore or [])[:lunghezza]
    return [str(v or "") for v in voci] + [""] * (lunghezza - len(voci))


@dataclass
class UnitaDidattica:
    titolo: str = ""
    argomenti: str = ""
    prerequisiti: str = ""
    # Posizioni valorizzate fra 1=NO, 2=ed. civica, 3=sicurezza, 4=altro, 5=scienze sperimentali. E' una lista
    # perche' il VB6 poteva lasciarne piu' d'una scritta nel file e non va alterata.
    multidisciplinare: list[int] = field(default_factory=lambda: [1])
    multidisciplinare_altro: str = ""
    ec_voci: list[str] = field(default_factory=list)
    ec_ore: str = ""
    ec_periodo: str = ""
    ec_quadrimestre: str = ""
    abilita: list[str] = field(default_factory=lambda: [""] * MAX_ABILITA)
    codici_abilita: list[str] = field(default_factory=lambda: [""] * MAX_ABILITA)
    conoscenze: list[str] = field(default_factory=lambda: [""] * MAX_CONOSCENZE)
    codici_conoscenze: list[str] = field(default_factory=lambda: [""] * MAX_CONOSCENZE)
    competenze_europee: list[int] = field(default_factory=list)
    competenze_cittadinanza: list[int] = field(default_factory=list)
    competenze_pecup: list[str] = field(default_factory=lambda: [""] * MAX_COMPETENZE_PECUP)
    codici_competenze_pecup: list[str] = field(default_factory=lambda: [""] * MAX_COMPETENZE_PECUP)
    competenze_minime: str = ""
    competenze_intermedie: str = ""
    competenze_avanzate: str = ""

    @property
    def completa(self) -> bool:
        return bool(
            len(self.titolo.strip()) >= 3
            and self.argomenti.strip()
            and any(a.strip() for a in self.abilita)
            and any(c.strip() for c in self.conoscenze)
            and self.competenze_minime.strip()
        )

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> "UnitaDidattica":
        return cls(
            titolo=dati.get("titolo", ""),
            argomenti=dati.get("argomenti", ""),
            prerequisiti=dati.get("prerequisiti", ""),
            multidisciplinare=[int(n) for n in dati.get("multidisciplinare") or [1]],
            multidisciplinare_altro=dati.get("multidisciplinare_altro", ""),
            ec_voci=[str(v) for v in dati.get("ec_voci", [])],
            ec_ore=str(dati.get("ec_ore", "")),
            ec_periodo=str(dati.get("ec_periodo", "")),
            ec_quadrimestre=str(dati.get("ec_quadrimestre", "")),
            abilita=_lista(dati.get("abilita"), MAX_ABILITA),
            codici_abilita=_lista(dati.get("codici_abilita"), MAX_ABILITA),
            conoscenze=_lista(dati.get("conoscenze"), MAX_CONOSCENZE),
            codici_conoscenze=_lista(dati.get("codici_conoscenze"), MAX_CONOSCENZE),
            competenze_europee=[int(n) for n in dati.get("competenze_europee", [])],
            competenze_cittadinanza=[int(n) for n in dati.get("competenze_cittadinanza", [])],
            competenze_pecup=_lista(dati.get("competenze_pecup"), MAX_COMPETENZE_PECUP),
            codici_competenze_pecup=_lista(
                dati.get("codici_competenze_pecup"), MAX_COMPETENZE_PECUP
            ),
            competenze_minime=dati.get("competenze_minime", ""),
            competenze_intermedie=dati.get("competenze_intermedie", ""),
            competenze_avanzate=dati.get("competenze_avanzate", ""),
        )


@dataclass
class Modulo:
    titolo: str = ""
    periodo: str = ""
    spazi: list[int] = field(default_factory=list)  # posizioni 1..4 selezionate
    spazi_altro: str = ""
    unita_in_uso: str = ""
    unita: list[UnitaDidattica] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return bool(
            len(self.titolo.strip()) >= 3
            and self.periodo.strip()
            and self.spazi
            and self.unita
            and all(u.completa for u in self.unita)
        )

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> "Modulo":
        return cls(
            titolo=dati.get("titolo", ""),
            periodo=dati.get("periodo", ""),
            spazi=[int(n) for n in dati.get("spazi", [])],
            spazi_altro=dati.get("spazi_altro", ""),
            unita_in_uso=str(dati.get("unita_in_uso", "")),
            unita=[UnitaDidattica.da_dict(u) for u in dati.get("unita", [])],
        )


@dataclass
class Programmazione:
    cognome: str = ""
    nome: str = ""
    classe: str = ""
    indirizzo: str = ""
    disciplina: str = ""
    ore_settimanali: str = ""
    verifiche_indistinte: str = ""
    verifiche_orali: str = ""
    verifiche_pratiche: str = ""
    strategie: list[int] = field(default_factory=list)
    strategie_altro: list[str] = field(default_factory=lambda: [""] * MAX_OPZIONI_ALTRO)
    mezzi: list[int] = field(default_factory=list)
    mezzi_altro: list[str] = field(default_factory=lambda: [""] * MAX_OPZIONI_ALTRO)
    strumenti: list[int] = field(default_factory=list)
    strumenti_altro: list[str] = field(default_factory=lambda: [""] * MAX_OPZIONI_ALTRO)
    modulo_in_uso: str = ""
    moduli: list[Modulo] = field(default_factory=list)

    @property
    def cartella_docente(self) -> str:
        return f"{self.cognome.strip().upper()}_{self.nome.strip().upper()}"

    @property
    def cartella_corso(self) -> str:
        return f"{self.classe.strip()}_{self.indirizzo.strip()}_{self.disciplina.strip()}"

    @property
    def step2_completo(self) -> bool:
        return bool(
            self.ore_settimanali
            and self.verifiche_indistinte
            and self.strategie
            and self.mezzi
            and self.strumenti
        )

    @property
    def step3_completo(self) -> bool:
        return bool(self.moduli) and all(m.completo for m in self.moduli)

    def come_dict(self) -> dict[str, Any]:
        return {
            "cognome": self.cognome,
            "nome": self.nome,
            "classe": self.classe,
            "indirizzo": self.indirizzo,
            "disciplina": self.disciplina,
            "ore_settimanali": self.ore_settimanali,
            "verifiche_indistinte": self.verifiche_indistinte,
            "verifiche_orali": self.verifiche_orali,
            "verifiche_pratiche": self.verifiche_pratiche,
            "strategie": self.strategie,
            "strategie_altro": self.strategie_altro,
            "mezzi": self.mezzi,
            "mezzi_altro": self.mezzi_altro,
            "strumenti": self.strumenti,
            "strumenti_altro": self.strumenti_altro,
            "modulo_in_uso": self.modulo_in_uso,
            "moduli": [
                {
                    "titolo": m.titolo,
                    "periodo": m.periodo,
                    "spazi": m.spazi,
                    "spazi_altro": m.spazi_altro,
                    "unita_in_uso": m.unita_in_uso,
                    "unita": [vars(u) for u in m.unita],
                }
                for m in self.moduli
            ],
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> "Programmazione":
        return cls(
            cognome=dati.get("cognome", ""),
            nome=dati.get("nome", ""),
            classe=dati.get("classe", ""),
            indirizzo=dati.get("indirizzo", ""),
            disciplina=dati.get("disciplina", ""),
            ore_settimanali=str(dati.get("ore_settimanali", "")),
            verifiche_indistinte=str(dati.get("verifiche_indistinte", "")),
            verifiche_orali=str(dati.get("verifiche_orali", "")),
            verifiche_pratiche=str(dati.get("verifiche_pratiche", "")),
            strategie=[int(n) for n in dati.get("strategie", [])],
            strategie_altro=_lista(dati.get("strategie_altro"), MAX_OPZIONI_ALTRO),
            mezzi=[int(n) for n in dati.get("mezzi", [])],
            mezzi_altro=_lista(dati.get("mezzi_altro"), MAX_OPZIONI_ALTRO),
            strumenti=[int(n) for n in dati.get("strumenti", [])],
            strumenti_altro=_lista(dati.get("strumenti_altro"), MAX_OPZIONI_ALTRO),
            modulo_in_uso=str(dati.get("modulo_in_uso", "")),
            moduli=[Modulo.da_dict(m) for m in dati.get("moduli", [])],
        )


def percorso_lavoro(prog: Programmazione) -> Path:
    return legacy.cartella_corso(
        prog.cognome, prog.nome, prog.classe, prog.indirizzo, prog.disciplina
    )


def esiste(prog: Programmazione) -> bool:
    return legacy.esiste_lavoro(
        prog.cognome, prog.nome, prog.classe, prog.indirizzo, prog.disciplina
    )


def salva(prog: Programmazione) -> Path:
    return legacy.scrivi_lavoro(prog.come_dict())


def carica(cognome: str, nome: str, classe: str, indirizzo: str, disciplina: str) -> Programmazione:
    if not legacy.esiste_lavoro(cognome, nome, classe, indirizzo, disciplina):
        return Programmazione(
            cognome=cognome, nome=nome, classe=classe, indirizzo=indirizzo, disciplina=disciplina
        )
    return Programmazione.da_dict(
        legacy.leggi_lavoro(cognome, nome, classe, indirizzo, disciplina)
    )


def elenca() -> list[dict[str, str]]:
    return legacy.elenca_lavori()


def elimina(dati: dict[str, str]) -> bool:
    """Elimina la sola cartella della programmazione indicata."""
    if dati not in elenca():
        return False
    percorso = percorso_lavoro(carica(**dati))
    if not percorso.is_dir():
        return False
    shutil.rmtree(percorso)
    return True
