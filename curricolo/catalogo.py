"""Interrogazioni sui cataloghi usate dalle pagine dei quattro step."""

from __future__ import annotations

import json
import re

from . import db
from .db import connessione


def nome_disciplina_visualizzato(nome: str) -> str:
    """Rimuove dai nomi mostrati le note descrittive dell'offerta formativa."""
    return re.sub(r"\s*\(solo se specifica per (?:indirizzo|articolazione)\)$", "", nome, flags=re.IGNORECASE).strip()


def discipline_normalizzate(classe: str, indirizzi: list[str]) -> list[str]:
    """Unisce le discipline di piu' indirizzi senza duplicare le varianti testuali."""
    nomi = []
    for indirizzo in indirizzi:
        nomi.extend(discipline(classe, indirizzo))
    return sorted({nome_disciplina_visualizzato(nome) for nome in nomi})


def disciplina_presente(classe: str, indirizzo: str, nome: str) -> bool:
    nome = nome_disciplina_visualizzato(nome).casefold()
    return any(nome_disciplina_visualizzato(voce).casefold() == nome for voce in discipline(classe, indirizzo))


# Materie storiche valide senza una terna completa nel catalogo PECUP legacy.
SIGLE_PECUP_OPZIONALI = {"EST", "REL"}
TIPI_PECUP = ("abilita", "conoscenza", "competenza")
PREFISSI_PECUP = {"abilita": "AB", "conoscenza": "CS", "competenza": "CT"}
MATERIE_STORICHE_IN_EVIDENZA = {"ALTERNATIVA IRC", "BIOTECNOLOGIE AGRARIE"}


def classi() -> list[str]:
    with connessione() as conn:
        return [r["nome"] for r in conn.execute("SELECT nome FROM classi ORDER BY numero")]


def indirizzi() -> list[str]:
    with connessione() as conn:
        return [r["nome"] for r in conn.execute("SELECT nome FROM indirizzi ORDER BY posizione")]


def numero_classe(classe: str) -> int | None:
    with connessione() as conn:
        riga = conn.execute("SELECT numero FROM classi WHERE nome = ?", (classe,)).fetchone()
        return int(riga["numero"]) if riga else None


def discipline(classe: str, indirizzo: str) -> list[str]:
    with connessione() as conn:
        righe = conn.execute(
            """
            SELECT DISTINCT d.nome
              FROM discipline d
              JOIN offerta_formativa o ON o.disciplina_id = d.id
              JOIN indirizzi i ON i.id = o.indirizzo_id
              JOIN classi c ON c.numero = o.classe
             WHERE c.nome = ? AND i.nome = ?
             ORDER BY d.nome
            """,
            (classe, indirizzo),
        )
        return [r["nome"] for r in righe]


def sigla_disciplina(nome: str) -> str:
    with connessione() as conn:
        riga = conn.execute(
            "SELECT sigla FROM discipline WHERE upper(trim(nome)) = upper(trim(?))", (nome,)
        ).fetchone()
        return riga["sigla"] if riga else nome[:5].upper()


def sigla_ini_disciplina(nome: str) -> str:
    with connessione() as conn:
        riga = conn.execute(
            "SELECT sigla_ini FROM discipline WHERE upper(trim(nome)) = upper(trim(?))", (nome,)
        ).fetchone()
    return str(riga["sigla_ini"] or db.sigla_ini_da_nome(nome)) if riga else db.sigla_ini_da_nome(nome)


def offerta() -> list[dict[str, str]]:
    """Tutte le combinazioni disciplina/classe/indirizzo previste dall'ordinamento."""
    with connessione() as conn:
        righe = conn.execute(
            """
            SELECT d.nome AS disciplina, d.sigla AS sigla, c.nome AS classe, i.nome AS indirizzo
              FROM offerta_formativa o
              JOIN discipline d ON d.id = o.disciplina_id
              JOIN indirizzi i ON i.id = o.indirizzo_id
              JOIN classi c ON c.numero = o.classe
             ORDER BY d.sigla, c.numero, i.posizione
            """
        )
        return [dict(r) for r in righe]


def materie() -> list[dict[str, object]]:
    """Materie configurate, con gli abbinamenti ai percorsi formativi."""
    with connessione() as conn:
        righe = conn.execute(
            """
            SELECT d.id, d.nome, d.sigla, d.attende_ini, c.nome AS classe, i.nome AS indirizzo
              FROM discipline d
              LEFT JOIN offerta_formativa o ON o.disciplina_id = d.id
              LEFT JOIN classi c ON c.numero = o.classe
              LEFT JOIN indirizzi i ON i.id = o.indirizzo_id
             ORDER BY d.nome, c.numero, i.posizione
            """
        )
        discipline_importate = {
            sigla_disciplina(riga["disciplina"]).upper()
            for riga in conn.execute("SELECT DISTINCT disciplina FROM ricevuti")
        }
        raggruppate: dict[str, dict[str, object]] = {}
        for riga in righe:
            identificativo = int(riga["id"])
            sigla = riga["sigla"]
            voce = raggruppate.setdefault(
                sigla,
                {
                    "id": identificativo,
                    "nome": riga["nome"],
                    "sigla": riga["sigla"],
                    "attende_ini": bool(riga["attende_ini"]),
                    "percorsi": [],
                },
            )
            voce["attende_ini"] = bool(voce["attende_ini"]) or bool(riga["attende_ini"])
            if riga["classe"] and riga["indirizzo"]:
                voce["percorsi"].append((riga["classe"], riga["indirizzo"]))  # type: ignore[index]

    risultato = []
    for voce in raggruppate.values():
        percorsi = list(dict.fromkeys(voce["percorsi"]))  # type: ignore[arg-type]
        voce["percorsi"] = percorsi
        voce["completa"] = str(voce["sigla"]) in SIGLE_PECUP_OPZIONALI or (bool(percorsi) and all(
            codici_pecup(tipo, str(voce["nome"]), classe, indirizzo)
            for classe, indirizzo in percorsi
            for tipo in ("abilita", "conoscenza", "competenza")
        ))
        voce["avviso"] = (
            "arancione" if not voce["completa"]
            else "giallo" if (
                str(voce["sigla"]).upper() not in discipline_importate
            )
            else ""
        )
        risultato.append(voce)
    return risultato


def valida_sigla_tecnica(sigla: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{3}", str(sigla or "").strip().upper()))


def sigla_tecnica_in_uso(sigla: str, identificativo: int | None = None) -> bool:
    sigla = str(sigla or "").strip().upper()
    if not valida_sigla_tecnica(sigla):
        return False
    with connessione() as conn:
        riga = conn.execute(
            "SELECT id FROM discipline WHERE upper(sigla) = upper(?) AND (? IS NULL OR id != ?)",
            (sigla, identificativo, identificativo),
        ).fetchone()
        return riga is not None


def aggiorna_sigla_materia(identificativo: int, sigla: str) -> bool:
    """Aggiorna la sigla tecnica di una materia, se la nuova sigla e' valida."""
    sigla = str(sigla or "").strip().upper()
    if not valida_sigla_tecnica(sigla):
        return False
    with connessione() as conn:
        conn.execute("UPDATE discipline SET sigla = ? WHERE id = ?", (sigla, identificativo))
        conn.commit()
    return True


def materia(identificativo: int) -> dict[str, object] | None:
    """Materia raggruppata per sigla, pronta per il riquadro di modifica."""
    for voce in materie():
        if voce["id"] == identificativo:
            return voce
    return None


def aggiorna_percorsi_materia(identificativo: int, percorsi: list[tuple[str, str]]) -> bool:
    """Sostituisce gli abbinamenti attivi di tutte le varianti della stessa sigla."""
    with connessione() as conn:
        riga = conn.execute("SELECT sigla FROM discipline WHERE id = ?", (identificativo,)).fetchone()
        if riga is None:
            return False
        sigla = riga["sigla"]
        discipline = conn.execute(
            "SELECT id FROM discipline WHERE sigla = ? ORDER BY id", (sigla,)
        ).fetchall()
        ids = [r["id"] for r in discipline]
        segnaposto = ",".join("?" for _ in ids)
        esistenti = {
            (r["classe"], r["indirizzo_id"]): r["disciplina_id"]
            for r in conn.execute(
                f"SELECT disciplina_id, classe, indirizzo_id FROM offerta_formativa "
                f"WHERE disciplina_id IN ({segnaposto})", ids
            )
        }
        conn.execute(f"DELETE FROM offerta_formativa WHERE disciplina_id IN ({segnaposto})", ids)
        for classe, indirizzo in percorsi:
            riga_classe = conn.execute("SELECT numero FROM classi WHERE nome = ?", (classe,)).fetchone()
            riga_indirizzo = conn.execute("SELECT id FROM indirizzi WHERE nome = ?", (indirizzo,)).fetchone()
            if riga_classe is None or riga_indirizzo is None:
                continue
            chiave = (riga_classe["numero"], riga_indirizzo["id"])
            disciplina_id = esistenti.get(chiave, ids[0])
            conn.execute(
                "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (?, ?, ?)",
                (disciplina_id, riga_indirizzo["id"], riga_classe["numero"]),
            )
        conn.commit()
    return True


def percorsi_pecup_mancanti(identificativo: int) -> list[tuple[str, str]]:
    materia_selezionata = materia(identificativo)
    if materia_selezionata is None or str(materia_selezionata["sigla"]) in SIGLE_PECUP_OPZIONALI:
        return []
    mancanti = []
    for classe, indirizzo in materia_selezionata["percorsi"]:  # type: ignore[index]
        if any(not codici_pecup(tipo, str(materia_selezionata["nome"]), classe, indirizzo)
               for tipo in TIPI_PECUP):
            mancanti.append((classe, indirizzo))
    return mancanti


def percorsi_pecup_mancanti_percorsi(
    nome: str, sigla: str, percorsi: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    if sigla in SIGLE_PECUP_OPZIONALI:
        return []
    return [
        (classe, indirizzo) for classe, indirizzo in percorsi
        if any(not codici_pecup(tipo, nome, classe, indirizzo) for tipo in TIPI_PECUP)
    ]


def classi_pecup_mancanti(identificativo: int) -> list[str]:
    return list(dict.fromkeys(classe for classe, _ in percorsi_pecup_mancanti(identificativo)))


def testi_pecup(tipo: str) -> list[str]:
    if tipo not in TIPI_PECUP:
        return []
    with connessione() as conn:
        righe = conn.execute(
            "SELECT DISTINCT descrizione FROM pecup WHERE tipo = ? ORDER BY descrizione", (tipo,)
        )
        return [riga["descrizione"] for riga in righe]


def testi_pecup_da_fonti(tipo: str, fonti: list[int], anni: list[str]) -> list[str]:
    """Testi PECUP delle sole materie e classi sorgente scelte dall'Admin."""
    if tipo not in TIPI_PECUP or not fonti or not anni:
        return []
    with connessione() as conn:
        sigle = [
            riga["sigla"] for riga in conn.execute(
                f"SELECT DISTINCT sigla FROM discipline WHERE id IN ({','.join('?' for _ in fonti)})", fonti
            )
        ]
        if not sigle:
            return []
        righe = conn.execute(
            f"""
            SELECT DISTINCT p.descrizione
              FROM pecup p
              JOIN pecup_validita v ON v.pecup_id = p.id
              JOIN discipline d ON upper(d.nome) = upper(v.disciplina)
              JOIN classi c ON c.numero = v.classe
             WHERE p.tipo = ? AND d.sigla IN ({','.join('?' for _ in sigle)})
               AND c.nome IN ({','.join('?' for _ in anni)})
             ORDER BY p.descrizione
            """,
            [tipo, *sigle, *anni],
        )
        return [riga["descrizione"] for riga in righe]


def _codice_pecup(sigla: str, classe: str, indirizzo: str, tipo: str, progressivo: int) -> str:
    indirizzo_codice = {
        "COMUNE": "T", "CAT": "C", "GRAFICO": "R", "AGRARIO (tutte le articolazioni)": "A",
        "AGRARIO (g.a.t.)": "G", "AGRARIO (p.t.)": "P", "AGRARIO (eno)": "E",
    }[indirizzo]
    anni = {"PRIMA": "BIE", "SECONDA": "BIE", "TERZA": "345", "QUARTA": "345", "QUINTA": "005"}[classe]
    return f"{sigla[:3].upper():<3}{indirizzo_codice}{anni}{PREFISSI_PECUP[tipo]}P{progressivo:02d}".replace(" ", "X")


def salva_pecup(identificativo: int, classe_destinazione: str, selezioni: dict[str, list[str]]) -> bool:
    """Crea codici PECUP per una classe e gli indirizzi attivi della materia."""
    materia_selezionata = materia(identificativo)
    if materia_selezionata is None:
        return False
    if any(not selezioni.get(tipo) for tipo in TIPI_PECUP):
        raise ValueError("Selezionare almeno una voce per abilita', conoscenze e competenze.")
    with connessione() as conn:
        for tipo in TIPI_PECUP:
            for testo in dict.fromkeys(selezioni[tipo]):
                testo = testo.strip()
                if not testo:
                    continue
                for classe, indirizzo in materia_selezionata["percorsi"]:  # type: ignore[index]
                    if classe != classe_destinazione:
                        continue
                    prossimo = conn.execute(
                        "SELECT COUNT(*) FROM pecup WHERE tipo = ? AND codice LIKE ?",
                        (tipo, f"{str(materia_selezionata['sigla'])[:3].upper()}%"),
                    ).fetchone()[0] + 1
                    codice = _codice_pecup(str(materia_selezionata["sigla"]), classe, indirizzo, tipo, prossimo)
                    riga = conn.execute(
                        "SELECT id FROM pecup WHERE tipo = ? AND codice = ?", (tipo, codice)
                    ).fetchone()
                    if riga is None:
                        pecup_id = conn.execute(
                            "INSERT INTO pecup (tipo, codice, descrizione) VALUES (?, ?, ?)",
                            (tipo, codice, testo),
                        ).lastrowid
                    else:
                        pecup_id = riga["id"]
                    indirizzo_id = conn.execute(
                        "SELECT id FROM indirizzi WHERE nome = ?", (indirizzo,)
                    ).fetchone()["id"]
                    classe_numero = conn.execute(
                        "SELECT numero FROM classi WHERE nome = ?", (classe,)
                    ).fetchone()["numero"]
                    conn.execute(
                        "INSERT OR IGNORE INTO pecup_validita (pecup_id, disciplina, classe, indirizzo_id) VALUES (?, ?, ?, ?)",
                        (pecup_id, str(materia_selezionata["nome"]).upper(), classe_numero, indirizzo_id),
                    )
        conn.commit()
    return True


def piani_educazione_per_rimozione(
    identificativo: int, percorsi_rimossi: list[tuple[str, str]] | None = None
) -> list[dict[str, object]]:
    """Piani civici che saranno interessati dall'eliminazione della materia o dei percorsi."""
    materia_selezionata = materia(identificativo)
    if materia_selezionata is None:
        return []
    from . import educazione_civica

    with connessione() as conn:
        varianti = conn.execute(
            "SELECT id, nome FROM discipline WHERE sigla = ? ORDER BY id",
            (materia_selezionata["sigla"],),
        ).fetchall()
        percorsi_per_id = {}
        for variante in varianti:
            percorsi_per_id[int(variante["id"])] = [
                (riga["classe"], riga["indirizzo"])
                for riga in conn.execute(
                    """
                    SELECT c.nome AS classe, i.nome AS indirizzo
                      FROM offerta_formativa o
                      JOIN classi c ON c.numero = o.classe
                      JOIN indirizzi i ON i.id = o.indirizzo_id
                     WHERE o.disciplina_id = ?
                    """,
                    (variante["id"],),
                )
            ]
    piani = []
    for variante in varianti:
        percorsi = percorsi_per_id[int(variante["id"])]
        if percorsi_rimossi is not None:
            percorsi = [percorso for percorso in percorsi if percorso in percorsi_rimossi]
        contesti = []
        for classe in classi():
            contesti.extend(educazione_civica.contesti_per_percorsi(classe, percorsi))
        piani.extend(
            educazione_civica.piani_materia_nei_contesti(str(variante["nome"]), contesti)
        )
    return [
        {"indice": indice, **piano}
        for indice, piano in enumerate(
            sorted(piani, key=lambda piano: (
                classi().index(str(piano["classe"])),
                ("CAT", "GRAFICO", "AGRARIO").index(str(piano["corso"])),
                ("COMUNE", "PT", "GAT", "ENO").index(str(piano["articolazione"])),
                str(piano["disciplina"]).casefold(),
            ))
        )
    ]


def materie_destinazione_educazione(
    identificativo_escluso: int,
    piano: dict[str, object],
    percorsi_disponibili: list[tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Materie attive compatibili con il contesto del piano civico."""
    from . import educazione_civica

    risultato = []
    for voce in materie():
        if int(voce["id"]) == identificativo_escluso:
            continue
        percorsi = (
            percorsi_disponibili
            if int(voce["id"]) == identificativo_escluso and percorsi_disponibili is not None
            else voce["percorsi"]
        )
        if educazione_civica.materia_compatibile_con_contesto(
            list(percorsi), str(piano["corso"]), str(piano["classe"]), str(piano["articolazione"])
        ):
            risultato.append(voce)
    return risultato


def applica_rimozione_materia(
    identificativo: int,
    destinatari: dict[str, int] | None = None,
    percorsi_nuovi: list[tuple[str, str]] | None = None,
    sigla_nuova: str = "",
) -> bool:
    """Rimuove una materia o alcuni percorsi e i relativi piani civici in modo atomico."""
    materia_selezionata = materia(identificativo)
    if materia_selezionata is None:
        return False
    percorsi_attuali = list(materia_selezionata["percorsi"])  # type: ignore[arg-type]
    rimozione_totale = percorsi_nuovi is None
    percorsi_destinazione = [] if rimozione_totale else list(dict.fromkeys(percorsi_nuovi))
    if not rimozione_totale and not percorsi_destinazione:
        raise ValueError("Una materia deve mantenere almeno un percorso.")
    rimossi = percorsi_attuali if rimozione_totale else [
        percorso for percorso in percorsi_attuali if percorso not in percorsi_destinazione
    ]
    piani = piani_educazione_per_rimozione(identificativo, rimossi)
    destinatari = destinatari or {}
    if destinatari and set(destinatari) != {str(piano["indice"]) for piano in piani}:
        raise ValueError("Selezionare una materia destinataria per ogni contesto interessato.")
    if not destinatari and piani:
        pass

    from . import educazione_civica

    with connessione() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for piano in piani:
            indice = str(piano["indice"])
            destinazione_id = destinatari.get(indice)
            if destinazione_id is not None:
                destinazione = conn.execute(
                    "SELECT id, nome FROM discipline WHERE id = ?", (destinazione_id,)
                ).fetchone()
                if destinazione is None or destinazione_id == identificativo:
                    raise ValueError("Materia destinataria non valida.")
                percorsi_target = [
                    (riga["classe"], riga["indirizzo"])
                    for riga in conn.execute(
                        """
                        SELECT c.nome AS classe, i.nome AS indirizzo
                          FROM offerta_formativa o
                          JOIN classi c ON c.numero = o.classe
                          JOIN indirizzi i ON i.id = o.indirizzo_id
                         WHERE o.disciplina_id = ?
                        """,
                        (destinazione_id,),
                    )
                ]
                if not educazione_civica.materia_compatibile_con_contesto(
                    percorsi_target, str(piano["corso"]), str(piano["classe"]),
                    str(piano["articolazione"]),
                ):
                    raise ValueError("La materia destinataria non appartiene al contesto selezionato.")
                piano_esistente = conn.execute(
                    """
                    SELECT dati FROM educazione_civica_piani
                     WHERE corso = ? AND classe = ? AND articolazione = ?
                       AND upper(trim(disciplina)) = upper(trim(?))
                    """,
                    (
                        piano["corso"], piano["classe"], piano["articolazione"],
                        destinazione["nome"],
                    ),
                ).fetchone()
                dati_destinazione = (
                    json.loads(piano_esistente["dati"]) if piano_esistente else {}
                )
                voci = {}
                for voce in [*(dati_destinazione.get("voci") or []), *(piano["dati"].get("voci") or [])]:  # type: ignore[union-attr]
                    chiave = (
                        str(voce.get("macroarea", "")),
                        " ".join(str(voce.get("voce", "")).split()),
                    )
                    if not chiave[1]:
                        continue
                    voci[chiave] = voci.get(chiave, 0) + int(voce.get("ore", 0) or 0)
                dati_destinazione.update({
                    "voci": [
                        {"macroarea": macroarea, "voce": voce, "ore": ore}
                        for (macroarea, voce), ore in voci.items()
                        if ore > 0
                    ],
                    "ore_disciplina": sum(voci.values()),
                    "conferme": {},
                })
                conn.execute(
                    """
                    INSERT INTO educazione_civica_piani
                        (corso, classe, articolazione, disciplina, dati)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(corso, classe, articolazione, disciplina) DO UPDATE SET
                        dati = excluded.dati,
                        aggiornato_il = datetime('now', 'localtime')
                    """,
                    (
                        piano["corso"], piano["classe"], piano["articolazione"],
                        destinazione["nome"], json.dumps(dati_destinazione, ensure_ascii=False),
                    ),
                )
            conn.execute(
                "DELETE FROM educazione_civica_piani "
                "WHERE corso = ? AND classe = ? AND articolazione = ? "
                "AND upper(trim(disciplina)) = upper(trim(?))",
                (piano["corso"], piano["classe"], piano["articolazione"], piano["disciplina"]),
            )

        sigla = str(materia_selezionata["sigla"])
        nomi_materia = [
            str(riga["nome"])
            for riga in conn.execute("SELECT nome FROM discipline WHERE sigla = ?", (sigla,))
        ]
        for classe, indirizzo in rimossi:
            numero = conn.execute("SELECT numero FROM classi WHERE nome = ?", (classe,)).fetchone()
            percorso_indirizzo = conn.execute(
                "SELECT id FROM indirizzi WHERE nome = ?", (indirizzo,)
            ).fetchone()
            if numero and percorso_indirizzo:
                for nome in nomi_materia:
                    conn.execute(
                        "DELETE FROM pecup_validita WHERE upper(trim(disciplina)) = upper(trim(?)) "
                        "AND classe = ? AND indirizzo_id = ?",
                        (nome, numero["numero"], percorso_indirizzo["id"]),
                    )
        identificativi = [
            int(riga["id"])
            for riga in conn.execute("SELECT id FROM discipline WHERE sigla = ?", (sigla,))
        ]
        if rimozione_totale:
            conn.executemany(
                "DELETE FROM offerta_formativa WHERE disciplina_id = ?",
                [(voce,) for voce in identificativi],
            )
            for nome in nomi_materia:
                conn.execute(
                    "DELETE FROM pecup_validita WHERE upper(trim(disciplina)) = upper(trim(?))",
                    (nome,),
                )
            conn.execute("DELETE FROM discipline WHERE sigla = ?", (sigla,))
        else:
            identificativo_riga = conn.execute(
                "SELECT id FROM discipline WHERE id = ?", (identificativo,)
            ).fetchone()
            if identificativo_riga is None:
                return False
            indirizzi = {
                riga["nome"]: int(riga["id"])
                for riga in conn.execute("SELECT id, nome FROM indirizzi")
            }
            classi_numeri = {
                riga["nome"]: int(riga["numero"])
                for riga in conn.execute("SELECT numero, nome FROM classi")
            }
            nuovi_id = {
                (classi_numeri[classe], indirizzi[indirizzo])
                for classe, indirizzo in percorsi_destinazione
                if classe in classi_numeri and indirizzo in indirizzi
            }
            ids = [
                int(riga["id"])
                for riga in conn.execute(
                    "SELECT id FROM discipline WHERE sigla = ? ORDER BY id",
                    (str(materia_selezionata["sigla"]),),
                )
            ]
            segnaposto = ",".join("?" for _ in ids)
            esistenti = {
                (riga["classe"], riga["indirizzo_id"]): int(riga["disciplina_id"])
                for riga in conn.execute(
                    f"SELECT disciplina_id, classe, indirizzo_id FROM offerta_formativa "
                    f"WHERE disciplina_id IN ({segnaposto})",
                    ids,
                )
            }
            conn.execute(
                f"DELETE FROM offerta_formativa WHERE disciplina_id IN ({segnaposto})",
                ids,
            )
            conn.executemany(
                "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (?, ?, ?)",
                [
                    (esistenti.get((classe_numero, indirizzo_id), ids[0]), indirizzo_id, classe_numero)
                    for classe_numero, indirizzo_id in sorted(nuovi_id)
                ],
            )
            if sigla_nuova:
                conn.execute(
                    "UPDATE discipline SET sigla = ?, sigla_ini = ? WHERE id = ?",
                    (sigla_nuova.upper(), db.sigla_ini_da_nome(str(materia_selezionata["nome"])), identificativo),
                )
        conn.commit()
    return True


def aggiungi_materia(nome: str, sigla: str, percorsi: list[tuple[str, str]]) -> int:
    """Inserisce una materia e tutti i suoi abbinamenti classe/indirizzo."""
    with connessione() as conn:
        esistente = conn.execute(
            "SELECT 1 FROM discipline WHERE upper(nome) = upper(?) OR upper(sigla) = upper(?)",
            (nome, sigla),
        ).fetchone()
        if esistente:
            raise ValueError("Esiste gia' una materia con lo stesso nome o la stessa sigla.")
        materia_id = conn.execute(
            "INSERT INTO discipline (nome, sigla, sigla_ini, attende_ini) VALUES (?, ?, ?, 1)",
            (nome, sigla, db.sigla_ini_da_nome(nome)),
        ).lastrowid
        for classe, indirizzo in percorsi:
            riga_classe = conn.execute("SELECT numero FROM classi WHERE nome = ?", (classe,)).fetchone()
            riga_indirizzo = conn.execute("SELECT id FROM indirizzi WHERE nome = ?", (indirizzo,)).fetchone()
            if riga_classe is None or riga_indirizzo is None:
                continue
            conn.execute(
                "INSERT INTO offerta_formativa (disciplina_id, indirizzo_id, classe) VALUES (?, ?, ?)",
                (materia_id, riga_indirizzo["id"], riga_classe["numero"]),
            )
        conn.commit()
        return int(materia_id)


def elimina_materia(identificativo: int) -> bool:
    """Elimina materia e abbinamenti, preservando record ricevuti gia' storicizzati."""
    return applica_rimozione_materia(identificativo)


def sigla_indirizzo(nome: str) -> str:
    with connessione() as conn:
        riga = conn.execute("SELECT sigla FROM indirizzi WHERE nome = ?", (nome,)).fetchone()
        return riga["sigla"] if riga else nome[:3].upper()


def opzioni(gruppo: str) -> list[str]:
    with connessione() as conn:
        righe = conn.execute(
            "SELECT testo FROM opzioni WHERE gruppo = ? ORDER BY posizione", (gruppo,)
        )
        return [r["testo"] for r in righe]


def opzioni_documento(gruppo: str) -> list[str]:
    """Diciture estese usate nelle tabelle dei documenti Word."""
    with connessione() as conn:
        righe = conn.execute(
            "SELECT testo, testo_documento FROM opzioni WHERE gruppo = ? ORDER BY posizione",
            (gruppo,),
        )
        return [r["testo_documento"] or r["testo"] for r in righe]


def competenze_ue() -> list[dict[str, object]]:
    """Schede delle competenze in chiave europea con i livelli di certificazione."""
    with connessione() as conn:
        schede = []
        for riga in conn.execute("SELECT * FROM competenze_ue ORDER BY posizione"):
            livelli = conn.execute(
                "SELECT etichetta, descrizione FROM livelli_ue WHERE posizione = ? ORDER BY ordine",
                (riga["posizione"],),
            )
            schede.append(
                {
                    "posizione": riga["posizione"],
                    "etichetta": riga["etichetta"],
                    "titolo": riga["titolo_documento"],
                    "titolo_esteso": riga["titolo_esteso"] or riga["titolo_documento"],
                    "descrizione": riga["descrizione"],
                    "livelli": [
                        {"etichetta": r["etichetta"], "descrizione": r["descrizione"]}
                        for r in livelli
                    ],
                }
            )
        return schede

def codici_pecup(
    tipo: str,
    disciplina: str | None = None,
    classe: str | None = None,
    indirizzo: str | None = None,
) -> list[dict[str, str]]:
    """Codici validi per disciplina/classe/indirizzo oppure globali se i parametri sono None."""
    with connessione() as conn:
        if disciplina is None and classe is None and indirizzo is None:
            righe = conn.execute(
                """
                SELECT codice, descrizione
                  FROM pecup
                 WHERE tipo = ?
                 ORDER BY codice
                """,
                (tipo,),
            ).fetchall()
        else:
            righe = conn.execute(
                """
                SELECT DISTINCT p.codice, p.descrizione
                  FROM pecup p
                  JOIN pecup_validita v ON v.pecup_id = p.id
                  JOIN indirizzi i ON i.id = v.indirizzo_id
                  JOIN classi c ON c.numero = v.classe
                 WHERE p.tipo = ?
                   AND (upper(?) = upper(v.disciplina)
                        OR upper(?) LIKE upper(v.disciplina) || ' %')
                   AND c.nome = ?
                   AND i.nome IN (?, 'COMUNE')
                 ORDER BY p.codice
                """,
                (tipo, disciplina, disciplina, classe, indirizzo),
            ).fetchall()

        return [
            {"codice": r["codice"], "descrizione": r["descrizione"]}
            for r in righe
        ]


def codici_pecup_materie(tipo: str) -> list[dict[str, object]]:
    """Codici globali con disciplina, classe e articolazione dal database."""
    with connessione() as conn:
        righe = conn.execute(
            """
            SELECT p.codice, p.descrizione, v.disciplina, v.classe,
                   i.posizione AS posizione_indirizzo
              FROM pecup p
              JOIN pecup_validita v ON v.pecup_id = p.id
              JOIN indirizzi i ON i.id = v.indirizzo_id
             WHERE p.tipo = ?
             ORDER BY p.codice, v.disciplina, v.classe, i.posizione
            """,
            (tipo,),
        ).fetchall()

    voci: dict[str, dict[str, object]] = {}
    for riga in righe:
        voce = voci.setdefault(
            riga["codice"],
            {
                "codice": riga["codice"],
                "descrizione": riga["descrizione"],
                "materie": [],
                "classi": [],
                "indirizzi": [],
            },
        )
        materie = voce["materie"]
        if riga["disciplina"] not in materie:  # type: ignore[operator]
            materie.append(riga["disciplina"])  # type: ignore[union-attr]
        classi = voce["classi"]
        if riga["classe"] not in classi:  # type: ignore[operator]
            classi.append(riga["classe"])  # type: ignore[union-attr]
        indirizzi = voce["indirizzi"]
        posizione = str(riga["posizione_indirizzo"])
        if posizione not in indirizzi:  # type: ignore[operator]
            indirizzi.append(posizione)  # type: ignore[union-attr]

    for voce in voci.values():
        codice = str(voce["codice"])
        voce["articolazione"] = codice[3] if len(codice) == 12 else ""
    return list(voci.values())


def codici_sicurezza_biennio(tipo: str) -> list[dict[str, object]]:
    """Voci con sigla SIC valide per il biennio."""
    with connessione() as conn:
        righe = conn.execute(
            """
            SELECT DISTINCT p.codice, p.descrizione
              FROM pecup p
              JOIN pecup_validita v ON v.pecup_id = p.id
             WHERE p.tipo = ?
               AND v.classe IN (1, 2)
               AND upper(p.codice) LIKE 'SIC%'
             ORDER BY p.codice
            """,
            (tipo,),
        ).fetchall()
        return [
            {
                "codice": r["codice"],
                "descrizione": r["descrizione"],
                "materie": ["Sicurezza biennio"],
                "classi": [1, 2],
                "articolazione": str(r["codice"])[3] if len(str(r["codice"])) == 12 else "",
            }
            for r in righe
        ]