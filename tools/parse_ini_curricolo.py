"""Parser di sola lettura per i file INI generati dal VB6 (ADMIN/file_ricevuti).

Formato reale verificato sui file prodotti dall'applicazione:
- encoding sorgente: cp1252
- separatore chiave/valore: byte 0xA7 ("§"), non il tilde '~' documentato nei commenti VB6
- ogni riga dato ha un codice di 6 cifre NNMMYY: NN=modulo (00=sezione base),
  MM=unita' di apprendimento (00=dati generali del modulo), YY=progressivo campo
- i testi multiriga usano '@' come separatore di riga (vedi Module3.bas risolvimultiline)

Questo script non modifica alcun file: legge e riporta soltanto.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENCODING = "cp1252"
DELIMITER = "\xa7"

# --- mappe posizionali dei campi, dedotte e verificate sui file reali ---

BASE_FIELDS = {
    1: "data", 2: "cognome", 3: "nome", 4: "classe", 5: "indirizzo", 6: "disciplina",
    7: "ore_settimanali", 8: "min_verifiche_indistinte", 9: "min_verifiche_orali",
    10: "min_verifiche_pratiche",
    **{10 + n: f"strategia_{n}" for n in range(1, 16)},
    26: "strategia_altro_1", 27: "strategia_altro_2",
    **{27 + n: f"mezzo_{n}" for n in range(1, 16)},
    43: "mezzo_altro_1", 44: "mezzo_altro_2",
    **{44 + n: f"strumento_{n}" for n in range(1, 16)},
    60: "strumento_altro_1", 61: "strumento_altro_2",
    62: "n_moduli_utilizzati", 63: "modulo_in_uso",
}

MODULE_FIELDS = {
    1: "titolo", 2: "periodo", 3: "opzione_aule", 4: "opzione_laboratori",
    5: "opzione_palestra", 6: "opzione_altri_spazi", 7: "specificazione_spazi",
    8: "n_ud_utilizzate", 9: "unita_in_uso",
}

UNIT_FIELDS = {
    1: "titolo", 2: "argomenti", 3: "prerequisiti",
    4: "multidisciplinare_si_no", 5: "multidisciplinare_educazione_civica",
    6: "multidisciplinare_sicurezza", 7: "altro_quadro_multidisciplinare",
    8: "quale_altro_quadro",
    **{8 + n: f"abilita_{n}" for n in range(1, 10)},
    **{17 + n: f"codice_abilita_{n}" for n in range(1, 10)},
    **{26 + n: f"conoscenza_{n}" for n in range(1, 10)},
    **{35 + n: f"codice_conoscenza_{n}" for n in range(1, 10)},
    **{44 + n: f"competenza_europea_{n}" for n in range(1, 9)},
    **{52 + n: f"competenza_cittadinanza_{n}" for n in range(1, 9)},
    **{60 + n: f"competenza_pecup_{n}" for n in range(1, 6)},
    **{65 + n: f"codice_competenza_pecup_{n}" for n in range(1, 6)},
    71: "competenze_minime", 72: "competenze_intermedie", 73: "competenze_avanzate",
}

MULTILINE_UNIT_FIELDS = {
    "argomenti", "prerequisiti",
    "competenze_minime", "competenze_intermedie", "competenze_avanzate",
}


def split_multiline(value: str) -> list[str]:
    if not value:
        return []
    return [part for part in value.split("@") if part != ""]


@dataclass
class UnitaDidattica:
    modulo: int
    unita: int
    campi: dict[str, str] = field(default_factory=dict)
    sconosciuti: dict[int, tuple[str, str]] = field(default_factory=dict)


@dataclass
class Modulo:
    numero: int
    campi: dict[str, str] = field(default_factory=dict)
    unita: dict[int, UnitaDidattica] = field(default_factory=dict)
    sconosciuti: dict[int, tuple[str, str]] = field(default_factory=dict)


@dataclass
class Programmazione:
    file: Path
    campi: dict[str, str] = field(default_factory=dict)
    moduli: dict[int, Modulo] = field(default_factory=dict)
    sconosciuti: list[tuple[int, int, int, str, str]] = field(default_factory=list)
    righe_ignorate: int = 0
    righe_con_byte_non_valido: list[int] = field(default_factory=list)


def iter_record_lines(path: Path):
    # Bug noto del generatore VB6: quando l'unita' di apprendimento e' la decima,
    # il codice campo diventa di 7 cifre invece di 6 (viene scritto "0" & CStr(unita)
    # senza troncare a 2 cifre, es. unita=10 -> "010" invece di "10").
    # Si gestiscono quindi entrambe le lunghezze valide (6 e 7).
    with path.open("r", encoding=ENCODING, errors="replace") as handle:
        for numero_riga, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            digit_run = 0
            while digit_run < len(line) and line[digit_run].isdigit():
                digit_run += 1

            if digit_run not in (6, 7):
                yield None
                continue

            code = line[:digit_run]
            rest = line[digit_run:]
            if DELIMITER in rest:
                label, _, value = rest.partition(DELIMITER)
            else:
                label, value = rest, ""

            if "\ufffd" in label or "\ufffd" in value:
                yield "BYTE_NON_VALIDO", numero_riga
                continue

            if digit_run == 6:
                modulo, unita, campo = int(code[0:2]), int(code[2:4]), int(code[4:6])
            else:
                modulo, unita, campo = int(code[0:2]), int(code[2:5]), int(code[5:7])
            yield modulo, unita, campo, label, value


def parse_file(path: Path) -> Programmazione:
    prog = Programmazione(file=path)
    for record in iter_record_lines(path):
        if record is None:
            prog.righe_ignorate += 1
            continue
        if record[0] == "BYTE_NON_VALIDO":
            prog.righe_con_byte_non_valido.append(record[1])
            continue
        modulo, unita, campo, label, value = record

        if modulo == 0 and unita == 0:
            nome_campo = BASE_FIELDS.get(campo)
            if nome_campo is None:
                prog.sconosciuti.append((modulo, unita, campo, label, value))
            else:
                prog.campi[nome_campo] = value
            continue

        mod = prog.moduli.setdefault(modulo, Modulo(numero=modulo))

        if unita == 0:
            nome_campo = MODULE_FIELDS.get(campo)
            if nome_campo is None:
                mod.sconosciuti[campo] = (label, value)
            else:
                mod.campi[nome_campo] = value
            continue

        ud = mod.unita.setdefault(unita, UnitaDidattica(modulo=modulo, unita=unita))
        nome_campo = UNIT_FIELDS.get(campo)
        if nome_campo is None:
            ud.sconosciuti[campo] = (label, value)
        else:
            ud.campi[nome_campo] = value

    return prog


def validate_directory(directory: Path) -> int:
    files = sorted(directory.glob("*.ini"))
    if not files:
        print(f"Nessun file .ini trovato in {directory}")
        return 1

    totale_moduli = 0
    totale_unita = 0
    file_con_problemi = 0

    for path in files:
        try:
            prog = parse_file(path)
        except UnicodeDecodeError as exc:
            file_con_problemi += 1
            print(f"[ENCODING] {path.name}: {exc}")
            continue

        n_moduli = len(prog.moduli)
        n_unita = sum(len(m.unita) for m in prog.moduli.values())
        totale_moduli += n_moduli
        totale_unita += n_unita

        problemi = []
        if prog.righe_con_byte_non_valido:
            righe = ", ".join(str(n) for n in prog.righe_con_byte_non_valido)
            problemi.append(f"byte non validi cp1252 alle righe {righe}")
        if prog.sconosciuti:
            problemi.append(f"{len(prog.sconosciuti)} campi base sconosciuti")
        for mod in prog.moduli.values():
            if mod.sconosciuti:
                problemi.append(f"modulo {mod.numero}: {len(mod.sconosciuti)} campi sconosciuti")
            for ud in mod.unita.values():
                if ud.sconosciuti:
                    problemi.append(
                        f"modulo {mod.numero} UDA {ud.unita}: {len(ud.sconosciuti)} campi sconosciuti"
                    )
        if not prog.campi.get("cognome") or not prog.campi.get("disciplina"):
            problemi.append("dati anagrafici base incompleti (cognome/disciplina)")

        if problemi:
            file_con_problemi += 1
            print(f"[AVVISO] {path.name}: " + "; ".join(problemi))

    print("\n--- RIEPILOGO ---")
    print(f"File analizzati: {len(files)}")
    print(f"File con avvisi: {file_con_problemi}")
    print(f"Totale moduli:   {totale_moduli}")
    print(f"Totale unita' di apprendimento: {totale_unita}")
    return 0 if file_con_problemi == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(Path(__file__).resolve().parent.parent / "ADMIN" / "file_ricevuti"),
        help="Cartella contenente i file .ini da validare (sola lettura)",
    )
    args = parser.parse_args()
    return validate_directory(Path(args.directory))


if __name__ == "__main__":
    sys.exit(main())
