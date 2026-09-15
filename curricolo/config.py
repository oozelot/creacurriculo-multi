"""Percorsi e costanti condivise del progetto."""

from pathlib import Path
import sys

RADICE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
RISORSE = Path(getattr(sys, "_MEIPASS", RADICE))

CARTELLA_LEGACY = RISORSE / "do_not_use"
CARTELLA_DISCIPLINE = CARTELLA_LEGACY / "discipline"
CARTELLA_PROGRAMMAZIONE = CARTELLA_LEGACY / "programmazione"

CARTELLA_DATI = RADICE / "dati"
FILE_DB = CARTELLA_DATI / "curricolo.db"
FILE_DB_FACTORY = RISORSE / "curricolobak.db"
FILE_DB_FACTORY_ALTERNATIVO = RADICE / "curricolobak.db"

CARTELLA_ADMIN = RADICE / "ADMIN"
CARTELLA_RICEVUTI = CARTELLA_ADMIN / "file_ricevuti"
CARTELLA_ADMIN_INPUT = CARTELLA_ADMIN / "input"
CARTELLA_ADMIN_OUTPUT = CARTELLA_ADMIN / "output"

# Le cartelle dei docenti stanno accanto al programma, come nel VB6:
# <COGNOME_NOME>/<CLASSE_INDIRIZZO_DISCIPLINA>/do_not_use/...
CARTELLA_LAVORI = RADICE

# Il VB6 scriveva e leggeva tutto in ANSI Windows con fine riga CRLF.
ENCODING_INI = "cp1252"
SEPARATORE_INI = "\xa7"

CLASSI = ["PRIMA", "SECONDA", "TERZA", "QUARTA", "QUINTA"]

# Ordine significativo: la posizione e' usata come indice nelle maschere di bit PECUP.
INDIRIZZI = [
    "COMUNE",
    "CAT",
    "GRAFICO",
    "AGRARIO (tutte le articolazioni)",
    "AGRARIO (g.a.t.)",
    "AGRARIO (p.t.)",
    "AGRARIO (eno)",
]

SIGLE_INDIRIZZO = {
    "COMUNE": "COM",
    "CAT": "CAT",
    "GRAFICO": "GRA",
    "AGRARIO (tutte le articolazioni)": "AGR",
    "AGRARIO (g.a.t.)": "GAT",
    "AGRARIO (p.t.)": "P T",
    "AGRARIO (eno)": "ENO",
}

COMPETENZE_EUROPEE = [
    "COMUNICARE IN MADRELINGUA",
    "COMUNICARE IN LINGUE STRANIERE",
    "COMPETENZE MATEMAT. E DI BASE SCIENTIFICA",
    "COMPETENZE DIGITALI",
    "IMPARARE AD IMPARARE",
    "COMPETENZE SOCIALI E CIVICHE",
    "SPIRITO DI INIZIATIVA E IMPRENDITORIALITA'",
    "CONSAPEVOLEZZA ED ESPRESSIONE CULTURALE",
]

COMPETENZE_CITTADINANZA = [
    "IMPARARE AD IMPARARE",
    "PROGETTARE",
    "COMUNICARE",
    "COLLABORARE E PARTECIPARE",
    "AGIRE IN MODO AUTONOMO E RESPONSABILE",
    "RISOLVERE PROBLEMI",
    "INDIVIDUARE COLLEGAMENTI E RELAZIONI",
    "ACQUISIRE E INTERPRETARE L'INFORMAZIONE",
]

SPAZI_MODULO = ["AULA", "LABORATORI", "PALESTRA", "ALTRO"]

MULTIDISCIPLINARE = [
    "NO",
    'SI MULTIDISCIPLINARE "ED CIVICA"',
    'SI MULTIDISCIPLINARE "SICUREZZA"',
    "SI IN ALTRO QUADRO MULTIDISCIPLINARE",
    'SI MULTIDISCIPLINARE "SCIENZE SPERIMENTALI"',
]

MAX_MODULI = 10
MAX_UD = 10
MAX_ABILITA = 9
MAX_CONOSCENZE = 9
MAX_COMPETENZE_PECUP = 5
MAX_OPZIONI_ELENCO = 15
MAX_OPZIONI_ALTRO = 2

# Limiti ereditati dai MaxLength dei controlli VB6.
LIMITI = {
    "cognome": 40,
    "nome": 40,
    "titolo_modulo": 75,
    "periodo_modulo": 120,
    "spazi_altro": 50,
    "titolo_ud": 80,
    "argomenti": 2400,
    "prerequisiti": 1200,
    "abilita": 900,
    "conoscenza": 900,
    "competenza_pecup": 900,
    "codice_pecup": 12,
    "competenze_livello": 900,
    "multidisciplinare_altro": 50,
    "opzione_altro": 60,
}
