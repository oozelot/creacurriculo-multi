"""Applicazione web che riproduce il flusso del programma VB6 (Step 1-4)."""

from __future__ import annotations

import os
import json
import shutil
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

ADMIN_PASSWORD = os.environ.get("CURRICOLO_ADMIN_PASSWORD", "admin")

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from curricolo import (
    archivio,
    catalogo,
    completamento,
    db,
    documenti_istituto,
    educazione_civica,
    elenco_codici,
    esporta_ini,
    esporta_word,
    legacy,
    modello,
)
from curricolo.config import (
    CARTELLA_ADMIN,
    CARTELLA_ADMIN_INPUT,
    CARTELLA_ADMIN_OUTPUT,
    CARTELLA_DATI,
    CARTELLA_LAVORI,
    CARTELLA_RICEVUTI,
    CARTELLA_RICEVUTI_SEME,
    CLASSI,
    COMPETENZE_CITTADINANZA,
    COMPETENZE_EUROPEE,
    INDIRIZZI,
    LIMITI,
    MAX_ABILITA,
    MAX_COMPETENZE_PECUP,
    MAX_CONOSCENZE,
    MAX_MODULI,
    MAX_OPZIONI_ALTRO,
    MAX_UD,
    MULTIDISCIPLINARE,
    SPAZI_MODULO,
)
from curricolo.modello import Modulo, Programmazione, UnitaDidattica
from curricolo.testo import ripara_mojibake

# Diciture del pannello ADMIN, al plurale come nel programma originale.
NOMI_CLASSI = ["PRIME", "SECONDE", "TERZE", "QUARTE", "QUINTE"]

app = Flask(__name__)
app.secret_key = "curricolo-sviluppo-locale"
app.jinja_env.filters["pulito"] = ripara_mojibake
app.config["ESEGUIBILE"] = getattr(sys, "frozen", False)

_CREAZIONI: dict[str, dict[str, object]] = {}
_CREAZIONI_LOCK = threading.Lock()
_ULTIMO_HEARTBEAT = time.monotonic()
_HEARTBEAT_LOCK = threading.Lock()


def prepara_cartelle_admin() -> None:
    for cartella in (CARTELLA_ADMIN, CARTELLA_ADMIN_INPUT, CARTELLA_RICEVUTI, CARTELLA_ADMIN_OUTPUT):
        cartella.mkdir(parents=True, exist_ok=True)
    if CARTELLA_RICEVUTI_SEME.resolve() != CARTELLA_RICEVUTI.resolve():
        for sorgente in CARTELLA_RICEVUTI_SEME.glob("*.ini"):
            destinazione = CARTELLA_RICEVUTI / sorgente.name
            if not destinazione.exists():
                shutil.copy2(sorgente, destinazione)
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    CARTELLA_LAVORI.mkdir(parents=True, exist_ok=True)


def prepara_sistema() -> None:
    prepara_cartelle_admin()
    db.inizializza_database()


def periodi() -> list[str]:
    percorso = Path(__file__).resolve().parent / "do_not_use" / "moduli" / "periodi.ini"
    if not percorso.exists():
        return []
    return [riga.strip() for riga in percorso.read_text(encoding="cp1252", errors="replace").splitlines() if riga.strip()]


_sessione_inizializzata = False


@app.before_request
def inizializza_sessione() -> None:
    global _sessione_inizializzata
    if not _sessione_inizializzata:
        prepara_sistema()
        session.clear()
        _sessione_inizializzata = True


@app.context_processor
def stato_navigazione() -> dict[str, bool]:
    prog = _programmazione()
    referente_completo = bool(prog.cognome.strip() and prog.nome.strip() and prog.classe.strip()
                              and prog.indirizzo.strip() and prog.disciplina.strip())
    return {
        "accesso_step2": referente_completo,
        "accesso_step3": referente_completo and prog.step2_completo,
        "accesso_step4": referente_completo and prog.step2_completo and prog.step3_completo,
        "accesso_nuovo_modulo": len(prog.moduli) < MAX_MODULI,
        "ritorno_admin": bool(session.get("modalita_admin")),
    }


def _programmazione() -> Programmazione:
    dati = session.get("contesto")
    if not dati:
        return Programmazione()
    return modello.carica(**dati)


def _campi(prefisso: str, quantita: int) -> list[str]:
    return [request.form.get(f"{prefisso}{i}", "").strip() for i in range(1, quantita + 1)]


def _interi(nome: str) -> list[int]:
    return [int(v) for v in request.form.getlist(nome) if v.isdigit()]


def _percorso_file(prog: Programmazione, cartella: str, nome: str) -> Path | None:
    """Percorso di un file generato, solo dentro le cartelle del docente in sessione."""
    cartelle = {
        "da_inviare": legacy.cartella_docente(prog.cognome, prog.nome) / "da_inviare",
        "output": esporta_word.cartella_output(prog),
    }
    if cartella not in cartelle or Path(nome).name != nome:
        return None
    percorso = cartelle[cartella] / nome
    return percorso if percorso.is_file() else None


@app.route("/", methods=["GET", "POST"])
def step1():
    classi = catalogo.classi()
    indirizzi = catalogo.indirizzi()

    if request.method == "POST":
        cognome_inserito = request.form.get("cognome", "").strip()
        nome_inserito = request.form.get("nome", "").strip()
        if cognome_inserito == "MASTER" and nome_inserito == "MASTER":
            session["accesso_master"] = True
            return redirect(url_for("master_factory"))
        cognome = cognome_inserito.upper()
        nome = nome_inserito.upper()
        classe = request.form.get("classe", "").strip()
        indirizzo = request.form.get("indirizzo", "").strip()
        disciplina = request.form.get("disciplina", "").strip()

        if cognome.upper() == "ADMIN" and nome.upper() == "ADMIN":
            session.pop("contesto", None)
            session["modalita_admin"] = True
            return redirect(url_for("admin"))

        if not (cognome and nome and classe and indirizzo and disciplina):
            flash("Compilare cognome, nome, classe, indirizzo e disciplina.", "errore")
        elif disciplina not in catalogo.discipline(classe, indirizzo):
            flash("La disciplina scelta non appartiene a questa classe/indirizzo.", "errore")
        else:
            contesto = {
                "cognome": cognome,
                "nome": nome,
                "classe": classe,
                "indirizzo": indirizzo,
                "disciplina": disciplina,
            }
            prog = modello.carica(**contesto)
            gia_presente = modello.esiste(prog)
            if not gia_presente:
                try:
                    percorso = modello.salva(prog)
                except OSError as errore:
                    flash(f"Impossibile creare la cartella di lavoro: {errore}", "errore")
                    return redirect(url_for("step1"))
                flash(f"Cartella di lavoro creata in: {percorso}", "info")
            session["contesto"] = contesto
            session["stato_step2"] = (
                "Dati esistenti ricaricati." if gia_presente else "Nuova programmazione creata."
            )
            flash(
                session["stato_step2"],
                "info",
            )
            return redirect(url_for("step2"))

    contesto = session.get("contesto") or {}
    discipline = (
        catalogo.discipline(contesto.get("classe", ""), contesto.get("indirizzo", ""))
        if contesto
        else []
    )
    return render_template(
        "step1.html",
        classi=classi,
        indirizzi=indirizzi,
        discipline=discipline,
        contesto=contesto,
        lavori=modello.elenca(),
        limiti=LIMITI,
    )


@app.route("/master/factory", methods=["GET", "POST"])
def master_factory():
    if not session.get("accesso_master"):
        return redirect(url_for("step1"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if password != "MASTER":
            flash("Password MASTER non valida. Nessuna modifica applicata.", "errore")
            return redirect(url_for("master_factory"))
        if not db.ripristina_database_factory():
            flash("Database factory assente o non valido. Nessuna modifica applicata.", "errore")
            return redirect(url_for("master_factory"))
        session.clear()
        flash("Database factory ripristinato correttamente.", "info")
        return redirect(url_for("step1"))
    return render_template("master_factory.html")


@app.route("/admin/educazione-civica/crea", methods=["POST"])
def admin_crea_educazione_civica():
    corso = request.form.get("corso", "").strip()
    classe = request.form.get("classe", "").strip()
    formato = request.args.get("formato") or request.form.get("formato", "word")

    def lavoro(avanzamento):
        percorso_word = documenti_istituto.genera_educazione_civica(corso, classe, avanzamento=avanzamento)
        risultato = {"percorso_word": str(percorso_word), "percorso": str(percorso_word)}
        if formato == "pdf":
            percorso_pdf = documenti_istituto.converti_pdf(percorso_word)
            risultato.update(percorso_pdf=str(percorso_pdf), percorso=str(percorso_pdf))
        return risultato

    return _avvia_creazione(lavoro, endpoint="admin_educazione_civica", classe=classe, indirizzi=[corso])


@app.route("/apri", methods=["POST"])
def apri():
    contesto = {
        chiave: request.form.get(chiave, "").strip().upper()
        if chiave in ("cognome", "nome")
        else request.form.get(chiave, "").strip()
        for chiave in ("cognome", "nome", "classe", "indirizzo", "disciplina")
    }
    prog = modello.carica(**contesto)
    if not modello.esiste(prog):
        flash("Programmazione non trovata sul disco.", "errore")
        return redirect(url_for("step1"))
    session["contesto"] = contesto
    session["stato_step2"] = "Dati esistenti ricaricati."
    flash("Programmazione esistente aperta.", "info")
    return redirect(url_for("step2"))


@app.route("/elimina", methods=["POST"])
def elimina():
    dati = {
        chiave: request.form.get(chiave, "").strip()
        for chiave in ("cognome", "nome", "classe", "indirizzo", "disciplina")
    }
    if modello.elimina(dati):
        if session.get("contesto") == dati:
            session.pop("contesto", None)
        flash("Programmazione eliminata dal disco.", "info")
    else:
        flash("Programmazione non trovata sul disco.", "errore")
    return redirect(url_for("step1"))


@app.route("/api/discipline")
def api_discipline():
    classe = request.args.get("classe", "")
    indirizzo = request.args.get("indirizzo", "")
    return jsonify(catalogo.discipline(classe, indirizzo))


@app.route("/step2", methods=["GET", "POST"])
def step2():
    if not session.get("contesto") or not stato_navigazione()["accesso_step2"]:
        return redirect(url_for("step1"))
    session.setdefault("stato_step2", "Dati esistenti ricaricati.")
    prog = _programmazione()

    if request.method == "POST":
        prog.ore_settimanali = request.form.get("ore_settimanali", "").strip()
        prog.verifiche_indistinte = request.form.get("verifiche_indistinte", "").strip()
        prog.verifiche_orali = request.form.get("verifiche_orali", "").strip() or "0"
        prog.verifiche_pratiche = request.form.get("verifiche_pratiche", "").strip() or "0"
        prog.strategie = _interi("strategie")
        prog.mezzi = _interi("mezzi")
        prog.strumenti = _interi("strumenti")
        prog.strategie_altro = _campi("strategie_altro_", MAX_OPZIONI_ALTRO)
        prog.mezzi_altro = _campi("mezzi_altro_", MAX_OPZIONI_ALTRO)
        prog.strumenti_altro = _campi("strumenti_altro_", MAX_OPZIONI_ALTRO)
        selezioni = (prog.strategie, prog.mezzi, prog.strumenti)
        gruppi_completi = all(bool(gruppo) for gruppo in selezioni)
        altro_non_completo = any(
            valore in scelte and len(testo.strip()) < 3
            for scelte, testo, valore in (
                (prog.strategie, prog.strategie_altro[0], len(catalogo.opzioni("strategia")) + 1),
                (prog.strategie, prog.strategie_altro[1], len(catalogo.opzioni("strategia")) + 2),
                (prog.mezzi, prog.mezzi_altro[0], len(catalogo.opzioni("mezzo")) + 1),
                (prog.mezzi, prog.mezzi_altro[1], len(catalogo.opzioni("mezzo")) + 2),
                (prog.strumenti, prog.strumenti_altro[0], len(catalogo.opzioni("strumento")) + 1),
                (prog.strumenti, prog.strumenti_altro[1], len(catalogo.opzioni("strumento")) + 2),
            )
        )
        ore_valide = prog.ore_settimanali.isdigit() and int(prog.ore_settimanali) > 0
        totale_verifiche = int(prog.verifiche_indistinte) if prog.verifiche_indistinte.isdigit() else 0
        orali = int(prog.verifiche_orali) if prog.verifiche_orali.isdigit() else 0
        pratiche = int(prog.verifiche_pratiche) if prog.verifiche_pratiche.isdigit() else 0
        somma_verifiche = orali + pratiche
        if not ore_valide or totale_verifiche <= 0 or not gruppi_completi or altro_non_completo or somma_verifiche > totale_verifiche:
            flash("Alcuni campi non sono stati completati: le modifiche non saranno salvate.", "errore")
            return redirect(url_for("step2"))
        modello.salva(prog)
        flash("Dati generali salvati.", "info")
        return redirect(url_for("step3"))

    return render_template(
        "step2.html",
        prog=prog,
        strategie=catalogo.opzioni("strategia"),
        mezzi=catalogo.opzioni("mezzo"),
        strumenti=catalogo.opzioni("strumento"),
        limiti=LIMITI,
        max_altro=MAX_OPZIONI_ALTRO,
    )


@app.route("/step3")
def step3():
    if not session.get("contesto") or not stato_navigazione()["accesso_step3"]:
        return redirect(url_for("step1"))
    return render_template(
        "step3.html",
        prog=_programmazione(),
        max_moduli=MAX_MODULI,
        accesso_step4=stato_navigazione()["accesso_step4"],
    )


@app.route("/step3/modulo/nuovo", methods=["POST"])
def nuovo_modulo():
    prog = _programmazione()
    if len(prog.moduli) >= MAX_MODULI:
        flash(f"Massimo {MAX_MODULI} moduli.", "errore")
        return redirect(url_for("step3"))
    prog.moduli.append(Modulo())
    modello.salva(prog)
    return redirect(url_for("modulo", numero=len(prog.moduli)))


@app.route("/step3/modulo/<int:numero>/elimina", methods=["POST"])
def elimina_modulo(numero: int):
    prog = _programmazione()
    if 1 <= numero <= len(prog.moduli):
        prog.moduli.pop(numero - 1)
        modello.salva(prog)
    return redirect(url_for("step3"))


@app.route("/step3/modulo/<int:numero>", methods=["GET", "POST"])
def modulo(numero: int):
    if not session.get("contesto"):
        return redirect(url_for("step1"))
    prog = _programmazione()
    if not 1 <= numero <= len(prog.moduli):
        abort(404)
    mod = prog.moduli[numero - 1]

    if request.method == "POST":
        mod.titolo = request.form.get("titolo", "").strip()
        mod.periodo = request.form.get("periodo", "").strip()
        mod.spazi = _interi("spazi")
        mod.spazi_altro = request.form.get("spazi_altro", "").strip()
        altro_attivo = 4 in mod.spazi
        if len(mod.titolo) < 3 or not mod.periodo or not mod.spazi or (altro_attivo and len(mod.spazi_altro) < 3):
            flash("Completare titolo, periodo e almeno uno spazio prima di salvare il modulo.", "errore")
            return render_template(
                "modulo.html",
                prog=prog,
                mod=mod,
                numero=numero,
                spazi=SPAZI_MODULO,
                periodi=periodi(),
                limiti=LIMITI,
                max_ud=MAX_UD,
            )
        modello.salva(prog)
        flash(f"Modulo {numero} salvato.", "info")
        return redirect(url_for("modulo", numero=numero))

    return render_template(
        "modulo.html",
        prog=prog,
        mod=mod,
        numero=numero,
        spazi=SPAZI_MODULO,
        periodi=periodi(),
        limiti=LIMITI,
        max_ud=MAX_UD,
    )


@app.route("/step3/modulo/<int:numero>/ud/nuova", methods=["POST"])
def nuova_ud(numero: int):
    prog = _programmazione()
    if not 1 <= numero <= len(prog.moduli):
        abort(404)
    mod = prog.moduli[numero - 1]
    if len(mod.unita) >= MAX_UD:
        flash(f"Massimo {MAX_UD} unita' di apprendimento per modulo.", "errore")
        return redirect(url_for("modulo", numero=numero))
    mod.unita.append(UnitaDidattica())
    modello.salva(prog)
    return redirect(url_for("unita", numero=numero, indice=len(mod.unita)))


@app.route("/step3/modulo/<int:numero>/ud/<int:indice>/elimina", methods=["POST"])
def elimina_ud(numero: int, indice: int):
    prog = _programmazione()
    if not 1 <= numero <= len(prog.moduli):
        abort(404)
    mod = prog.moduli[numero - 1]
    if 1 <= indice <= len(mod.unita):
        mod.unita.pop(indice - 1)
        modello.salva(prog)
    return redirect(url_for("modulo", numero=numero))


@app.route("/step3/modulo/<int:numero>/ud/<int:indice>", methods=["GET", "POST"])
def unita(numero: int, indice: int):
    if not session.get("contesto"):
        return redirect(url_for("step1"))
    prog = _programmazione()
    if not 1 <= numero <= len(prog.moduli):
        abort(404)
    mod = prog.moduli[numero - 1]
    if not 1 <= indice <= len(mod.unita):
        abort(404)
    ud = mod.unita[indice - 1]

    chiave = (prog.disciplina, prog.classe, prog.indirizzo)
    piano_ec = educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina)
    ore_utilizzate_ec = educazione_civica.ore_utilizzate_per_voce(piano_ec)

    if request.method == "POST":
        ud.titolo = request.form.get("titolo", "").strip()
        ud.argomenti = request.form.get("argomenti", "")
        ud.prerequisiti = request.form.get("prerequisiti", "")
        scelte_multidisciplinari = [
            int(valore)
            for valore in request.form.getlist("multidisciplinare")
            if valore.isdigit()
        ]
        scelte_multidisciplinari = sorted(set(scelte_multidisciplinari))
        if any(posizione > 1 for posizione in scelte_multidisciplinari):
            scelte_multidisciplinari = [
                posizione for posizione in scelte_multidisciplinari if posizione != 1
            ]
        ud.multidisciplinare = scelte_multidisciplinari or [1]
        ud.multidisciplinare_altro = request.form.get("multidisciplinare_altro", "").strip()
        educazione_civica_valida = True
        if 2 in ud.multidisciplinare and piano_ec is None:
            flash("La materia selezionata non ha UDA indicate nel piano dell'educazione civica per la classe e l'indirizzo assegnato.", "errore")
            educazione_civica_valida = False
        ud.ec_voci = request.form.getlist("ec_voci")
        ud.ec_ore = request.form.get("ec_ore", "").strip()
        ud.ec_periodo = request.form.get("ec_periodo", "").strip()
        ud.ec_quadrimestre = request.form.get("ec_quadrimestre", "").strip()
        if 2 in ud.multidisciplinare and piano_ec is not None:
            ud.ec_periodo = mod.periodo
            if (
                not ud.ec_ore.isdigit()
                or not ud.ec_voci
                or ud.ec_quadrimestre not in ("I", "II")
            ):
                flash("Completare i dati di Educazione civica nella finestra dedicata.", "errore")
                educazione_civica_valida = False
            elif educazione_civica.quadrimestre_periodo(mod.periodo) != ud.ec_quadrimestre:
                flash("Il periodo di Educazione civica deve appartenere al quadrimestre del modulo.", "errore")
                educazione_civica_valida = False
        ud.abilita = _campi("abilita_", MAX_ABILITA)
        ud.codici_abilita = _campi("codice_abilita_", MAX_ABILITA)
        ud.conoscenze = _campi("conoscenza_", MAX_CONOSCENZE)
        ud.codici_conoscenze = _campi("codice_conoscenza_", MAX_CONOSCENZE)
        ud.competenze_europee = _interi("competenze_europee")
        ud.competenze_cittadinanza = _interi("competenze_cittadinanza")
        ud.competenze_pecup = _campi("competenza_pecup_", MAX_COMPETENZE_PECUP)
        ud.codici_competenze_pecup = _campi("codice_competenza_pecup_", MAX_COMPETENZE_PECUP)
        ud.competenze_minime = request.form.get("competenze_minime", "")
        ud.competenze_intermedie = request.form.get("competenze_intermedie", "")
        ud.competenze_avanzate = request.form.get("competenze_avanzate", "")
        primo_codice_valido = all(
            codici[0].strip() and testi[0].strip()
            for codici, testi in (
                (ud.codici_abilita, ud.abilita),
                (ud.codici_conoscenze, ud.conoscenze),
                (ud.codici_competenze_pecup, ud.competenze_pecup),
            )
        )
        quadro_valido = bool(ud.multidisciplinare)
        quadro_altro_valido = 4 not in ud.multidisciplinare or len(ud.multidisciplinare_altro.strip()) >= 3
        if not (
            len(ud.titolo.strip()) >= 3
            and ud.argomenti.strip()
            and ud.prerequisiti.strip()
            and primo_codice_valido
            and quadro_valido
            and quadro_altro_valido
            and ud.competenze_europee
            and ud.competenze_cittadinanza
            and ud.competenze_minime.strip()
            and educazione_civica_valida
        ):
            flash("Completare tutti i campi obbligatori dell'unita' di apprendimento.", "errore")
            return render_template(
                "unita.html",
                prog=prog,
                mod=mod,
                ud=ud,
                numero=numero,
                indice=indice,
                multidisciplinare=MULTIDISCIPLINARE,
                competenze_europee=COMPETENZE_EUROPEE,
                competenze_cittadinanza=COMPETENZE_CITTADINANZA,
                elenco_abilita=catalogo.codici_pecup("abilita", *chiave),
                elenco_conoscenze=catalogo.codici_pecup("conoscenza", *chiave),
                elenco_competenze=catalogo.codici_pecup("competenza", *chiave),
                elenco_abilita_globale=catalogo.codici_pecup("abilita"),
                elenco_conoscenze_globale=catalogo.codici_pecup("conoscenza"),
                elenco_competenze_globale=catalogo.codici_pecup("competenza"),
                elenco_abilita_materie=catalogo.codici_pecup_materie("abilita"),
                elenco_conoscenze_materie=catalogo.codici_pecup_materie("conoscenza"),
                elenco_competenze_materie=catalogo.codici_pecup_materie("competenza"),
                elenco_sicurezza_biennio={tipo: catalogo.codici_sicurezza_biennio(tipo) for tipo in ("abilita", "conoscenza", "competenza")},
                materie_filtro=catalogo.materie(),
                limiti=LIMITI,
                intervallo_abilita=range(1, MAX_ABILITA + 1),
                intervallo_conoscenze=range(1, MAX_CONOSCENZE + 1),
                intervallo_competenze=range(1, MAX_COMPETENZE_PECUP + 1),
                educazione_piano=educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina),
                educazione_piano_pronto=educazione_civica.piano_disponibile(educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina)),
                educazione_ore_utilizzate=ore_utilizzate_ec,
                educazione_ore_ud_corrente=ud.ec_ore,
                periodi=periodi(),
                quadrimestre_modulo=educazione_civica.quadrimestre_periodo(mod.periodo),
            )
        modello.salva(prog)
        if 2 in ud.multidisciplinare and educazione_civica_valida:
            chiave_conferma = educazione_civica.chiave_conferma(
                prog.cognome, prog.nome, prog.disciplina, numero, indice
            )
            educazione_civica.registra_conferma(
                prog.classe,
                prog.indirizzo,
                prog.disciplina,
                chiave_conferma,
                {
                    "voci": list(ud.ec_voci),
                    "quadrimestre": ud.ec_quadrimestre,
                    "periodo": ud.ec_periodo,
                    "ore": ud.ec_ore,
                },
            )
        flash("Unita' di apprendimento salvata.", "info")
        return redirect(url_for("unita", numero=numero, indice=indice))

    return render_template(
        "unita.html",
        prog=prog,
        mod=mod,
        ud=ud,
        numero=numero,
        indice=indice,
        multidisciplinare=MULTIDISCIPLINARE,
        competenze_europee=COMPETENZE_EUROPEE,
        competenze_cittadinanza=COMPETENZE_CITTADINANZA,
        elenco_abilita=catalogo.codici_pecup("abilita", *chiave),
        elenco_conoscenze=catalogo.codici_pecup("conoscenza", *chiave),
        elenco_competenze=catalogo.codici_pecup("competenza", *chiave),
        elenco_abilita_globale=catalogo.codici_pecup("abilita"),
        elenco_conoscenze_globale=catalogo.codici_pecup("conoscenza"),
        elenco_competenze_globale=catalogo.codici_pecup("competenza"),
        elenco_abilita_materie=catalogo.codici_pecup_materie("abilita"),
        elenco_conoscenze_materie=catalogo.codici_pecup_materie("conoscenza"),
        elenco_competenze_materie=catalogo.codici_pecup_materie("competenza"),
        elenco_sicurezza_biennio={tipo: catalogo.codici_sicurezza_biennio(tipo) for tipo in ("abilita", "conoscenza", "competenza")},
        materie_filtro=catalogo.materie(),
        limiti=LIMITI,
        intervallo_abilita=range(1, MAX_ABILITA + 1),
        intervallo_conoscenze=range(1, MAX_CONOSCENZE + 1),
        intervallo_competenze=range(1, MAX_COMPETENZE_PECUP + 1),
        educazione_piano=educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina),
        educazione_piano_pronto=educazione_civica.piano_disponibile(educazione_civica.piano_per_docente(prog.classe, prog.indirizzo, prog.disciplina)),
        educazione_ore_utilizzate=ore_utilizzate_ec,
        educazione_ore_ud_corrente=ud.ec_ore,
        periodi=periodi(),
        quadrimestre_modulo=educazione_civica.quadrimestre_periodo(mod.periodo),
    )


@app.route("/step4")
def step4():
    if not session.get("contesto") or not stato_navigazione()["accesso_step4"]:
        return redirect(url_for("step1"))
    prog = _programmazione()
    cartella_invio = legacy.cartella_docente(prog.cognome, prog.nome) / "da_inviare"
    referente = f"{prog.nome.strip()} {prog.cognome.strip()}".strip()
    nome = esporta_ini.nome_file_invio(prog, referente=referente)
    cartella_output = esporta_word.cartella_output(prog)
    creati = sorted(p.name for p in cartella_output.glob("*.docx")) if cartella_output.exists() else []
    return render_template(
        "step4.html",
        prog=prog,
        nome_file=nome,
        cartella_invio=cartella_invio,
        ini_esistente=(cartella_invio / nome).exists(),
        cartella_output=cartella_output,
        documenti=esporta_word.DOCUMENTI,
        documenti_creati=creati,
        documento_creato=session.pop("documento_creato", None),
        completo=prog.step2_completo and prog.step3_completo,
    )


@app.route("/step4/genera-ini", methods=["POST"])
def genera_ini():
    prog = _programmazione()
    if not (prog.step2_completo and prog.step3_completo):
        flash("Completare gli step 2 e 3 prima di generare il file.", "errore")
        return redirect(url_for("step4"))

    cartella = legacy.cartella_docente(prog.cognome, prog.nome) / "da_inviare"
    referente = f"{prog.nome.strip()} {prog.cognome.strip()}".strip()
    percorso = cartella / esporta_ini.nome_file_invio(prog, referente=referente)
    if percorso.exists() and request.form.get("conferma") != "1":
        flash(
            f"Il file {percorso.name} esiste gia': confermare la sovrascrittura per procedere.",
            "errore",
        )
        return redirect(url_for("step4"))

    percorso = esporta_ini.scrivi_file(prog)
    flash(f"File creato e salvato in: {percorso}", "info")
    return redirect(url_for("step4"))


@app.route("/step4/genera-word/<tipo>", methods=["POST"])
def genera_word(tipo: str):
    prog = _programmazione()
    if tipo not in esporta_word.DOCUMENTI:
        abort(404)
    if not (prog.step2_completo and prog.step3_completo):
        flash("Completare gli step 2 e 3 prima di generare i documenti.", "errore")
        return redirect(url_for("step4"))

    percorso = esporta_word.genera(prog, tipo)
    session["documento_creato"] = percorso.name
    flash(f"Documento creato e salvato in: {percorso}", "info")
    return redirect(url_for("step4"))


@app.route("/step4/apri", methods=["POST"])
def apri_documento():
    prog = _programmazione()
    percorso = _percorso_file(prog, "output", request.form.get("nome", ""))
    if percorso is None:
        abort(404)
    session.pop("documento_creato", None)
    if not hasattr(os, "startfile"):
        flash("Apertura automatica non disponibile su questo sistema.", "errore")
        return redirect(url_for("step4"))
    os.startfile(percorso)
    flash(f"Documento aperto: {percorso.name}", "info")
    return redirect(url_for("step4"))


@app.route("/step4/scarica/<cartella>/<nome>")
def scarica(cartella: str, nome: str):
    percorso = _percorso_file(_programmazione(), cartella, nome)
    if percorso is None:
        abort(404)
    return send_file(percorso, as_attachment=True)


@app.route("/admin")
def admin():
    session["modalita_admin"] = True
    return redirect(url_for("admin_database"))


@app.route("/chiudi", methods=["POST"])
def chiudi():
    if not app.config["ESEGUIBILE"]:
        return ("", 204)
    threading.Timer(0.2, os._exit, args=(0,)).start()
    return ("Applicazione chiusa.", 200)


@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    global _ULTIMO_HEARTBEAT
    with _HEARTBEAT_LOCK:
        _ULTIMO_HEARTBEAT = time.monotonic()
    return ("", 204)


def controlla_heartbeat() -> None:
    while True:
        time.sleep(5)
        with _HEARTBEAT_LOCK:
            inattiva = time.monotonic() - _ULTIMO_HEARTBEAT > 60
        if inattiva:
            os._exit(0)


def _password_admin_valida(password: str | None) -> bool:
    return bool(password) and password == ADMIN_PASSWORD


@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    password = request.form.get("password")
    if not _password_admin_valida(password):
        flash("Password amministrativa non valida. Nessuna modifica applicata.", "errore")
        return redirect(request.referrer or url_for("admin_database"))
    global _sessione_inizializzata
    session.clear()
    legacy.elimina_cartelle_lavoro()
    if CARTELLA_ADMIN.exists():
        for cartella in (CARTELLA_ADMIN_INPUT, CARTELLA_ADMIN_OUTPUT):
            if cartella.exists():
                shutil.rmtree(cartella)
    db.resetta_database()
    prepara_cartelle_admin()
    _sessione_inizializzata = True
    flash(
        "Lavoro e dati locali azzerati. Il catalogo e la configurazione iniziale "
        "di Educazione civica sono stati ripristinati.",
        "info",
    )
    return redirect(url_for("step1"))


@app.route("/admin/reset-pecup", methods=["POST"])
def admin_reset_pecup():
    password = request.form.get("password")
    if not _password_admin_valida(password):
        flash("Password amministrativa non valida. Nessuna modifica applicata.", "errore")
        return redirect(request.referrer or url_for("admin_database"))
    if not db.ripristina_pecup_backup():
        db.backup_pecup_attuali()
        db.ripristina_pecup_backup()
    if not db.ripristina_educazione_civica_factory():
        flash("Impossibile ripristinare la situazione iniziale di Educazione civica dal factory.", "errore")
    else:
        flash("Codici PECUP e situazione Educazione civica ripristinati allo stato iniziale.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/memorizza-pecup", methods=["POST"])
def admin_memorizza_pecup():
    password = request.form.get("password")
    if not _password_admin_valida(password):
        flash("Password amministrativa non valida. Nessuna modifica applicata.", "errore")
        return redirect(request.referrer or url_for("admin_database"))
    db.backup_pecup_attuali()
    flash("Codici PECUP attuali memorizzati come nuovo stato iniziale.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/memorizza-educazione-civica", methods=["POST"])
def admin_memorizza_educazione_civica():
    password = request.form.get("password")
    if not _password_admin_valida(password):
        flash("Password amministrativa non valida. Nessuna modifica applicata.", "errore")
        return redirect(request.referrer or url_for(
            "admin_educazione_civica",
            corso=request.form.get("corso", ""),
            classe=request.form.get("classe", ""),
        ))
    corso = request.form.get("corso", "").strip()
    classe = request.form.get("classe", "").strip()
    if corso not in ("CAT", "GRAFICO", "AGRARIO") or classe not in CLASSI:
        flash("Corso o anno scolastico non validi. Nessuna modifica applicata.", "errore")
        return redirect(request.referrer or url_for("admin_educazione_civica"))
    db.backup_educazione_civica(corso, classe)
    flash(f"Situazione Educazione civica memorizzata per {corso} {classe}.", "info")
    return redirect(url_for("admin_educazione_civica", corso=corso, classe=classe))


@app.route("/admin/database")
def admin_database():
    importati = archivio.gia_importati()
    return render_template(
        "admin_database.html",
        sezione="database",
        file_ricevuti=[
            {"nome": p.name, "importato": p.name in importati} for p in archivio.file_ricevuti()
        ],
        record=archivio.elenca(),
        cartella_output=CARTELLA_ADMIN_OUTPUT,
    )


@app.route("/admin/materie")
def admin_materie():
    identificativo = request.args.get("materia", "")
    materia_selezionata = catalogo.materia(int(identificativo)) if identificativo.isdigit() else None
    return render_template(
        "admin_materie.html",
        sezione="materie",
        materie=catalogo.materie(),
        materia_selezionata=materia_selezionata,
        classi=CLASSI,
        indirizzi=INDIRIZZI,
    )


@app.route("/admin/materie/aggiungi", methods=["POST"])
def admin_aggiungi_materia():
    nome = request.form.get("nome", "").strip().upper()
    sigla = request.form.get("sigla", "").strip().upper()
    percorsi = []
    for valore in request.form.getlist("percorso"):
        classe, separatore, indirizzo = valore.partition("|")
        if separatore and classe in CLASSI and indirizzo in INDIRIZZI:
            percorsi.append((classe, indirizzo))
    if len(nome) < 3 or not catalogo.valida_sigla_tecnica(sigla) or not percorsi:
        flash("Inserire nome, sigla tecnica valida (3 caratteri, lettere o numeri, senza spazi) e almeno un percorso di studio.", "errore")
    elif catalogo.sigla_tecnica_in_uso(sigla):
        flash("Sigla già in uso da un'altra materia.", "errore")
    else:
        try:
            identificativo = catalogo.aggiungi_materia(nome, sigla, percorsi)
            mancanti = catalogo.percorsi_pecup_mancanti(identificativo)
            if mancanti:
                session["pecup_mancanti"] = mancanti
                return redirect(url_for("admin_materie", materia=identificativo, pecup="mancanti"))
            flash("Materia aggiunta.", "info")
        except ValueError as errore:
            flash(str(errore), "errore")
    return redirect(url_for("admin_materie"))


@app.route("/admin/materie/<int:identificativo>/elimina", methods=["POST"])
def admin_elimina_materia(identificativo: int):
    if not catalogo.elimina_materia(identificativo):
        abort(404)
    flash("Materia eliminata dal quadro attivo.", "info")
    return redirect(url_for("admin_materie"))


@app.route("/admin/materie/<int:identificativo>/modifica", methods=["POST"])
def admin_modifica_materia(identificativo: int):
    nome = request.form.get("nome", "").strip().upper()
    sigla = request.form.get("sigla", "").strip().upper()
    percorsi = []
    for valore in request.form.getlist("percorso"):
        classe, separatore, indirizzo = valore.partition("|")
        if separatore and classe in CLASSI and indirizzo in INDIRIZZI:
            percorsi.append((classe, indirizzo))
    if not percorsi:
        flash("Selezionare almeno un percorso di studio.", "errore")
        return redirect(url_for("admin_materie", materia=identificativo))
    materia_selezionata = catalogo.materia(identificativo)
    if materia_selezionata is None:
        abort(404)
    if nome and len(nome) < 3:
        flash("Il nome della materia deve avere almeno 3 caratteri.", "errore")
        return redirect(url_for("admin_materie", materia=identificativo))
    if sigla and not catalogo.valida_sigla_tecnica(sigla):
        flash("Sigla tecnica non valida: usare 3 caratteri, lettere o numeri, senza spazi.", "errore")
        return redirect(url_for("admin_materie", materia=identificativo))
    if sigla and sigla != str(materia_selezionata["sigla"]).upper() and catalogo.sigla_tecnica_in_uso(sigla, identificativo):
        flash("Sigla già in uso da un'altra materia.", "errore")
        return redirect(url_for("admin_materie", materia=identificativo))
    if sigla and sigla != str(materia_selezionata["sigla"]).upper() and not catalogo.aggiorna_sigla_materia(identificativo, sigla):
        flash("Impossibile aggiornare la sigla tecnica.", "errore")
        return redirect(url_for("admin_materie", materia=identificativo))
    mancanti = catalogo.percorsi_pecup_mancanti_percorsi(
        str(materia_selezionata["nome"]), str(materia_selezionata["sigla"]), percorsi
    )
    if mancanti:
        session["bozza_materia"] = {"id": identificativo, "percorsi": percorsi}
        session["pecup_mancanti"] = mancanti
        return redirect(url_for("admin_materie", materia=identificativo, pecup="mancanti"))
    if not catalogo.aggiorna_percorsi_materia(identificativo, percorsi):
        abort(404)
    flash("Percorsi della materia aggiornati.", "info")
    return redirect(url_for("admin_materie"))


@app.route("/admin/materie/<int:identificativo>/conferma", methods=["POST"])
def admin_conferma_modifica_materia(identificativo: int):
    bozza = session.get("bozza_materia") or {}
    if bozza and bozza.get("id") != identificativo:
        abort(400)
    if bozza:
        if not catalogo.aggiorna_percorsi_materia(identificativo, bozza.get("percorsi", [])):
            abort(404)
    session.pop("bozza_materia", None)
    session.pop("pecup_mancanti", None)
    azione = request.form.get("azione")
    if azione == "pecup":
        return redirect(url_for("admin_pecup_materia", identificativo=identificativo))
    if azione == "salva":
        flash("Percorsi della materia aggiornati.", "info")
    return redirect(url_for("admin_materie"))


@app.route("/admin/materie/<int:identificativo>/annulla", methods=["POST"])
def admin_annulla_modifica_materia(identificativo: int):
    session.pop("bozza_materia", None)
    session.pop("pecup_mancanti", None)
    return redirect(url_for("admin_materie", materia=identificativo))


@app.route("/admin/materie/<int:identificativo>/pecup", methods=["GET", "POST"])
def admin_pecup_materia(identificativo: int):
    materia_selezionata = catalogo.materia(identificativo)
    if materia_selezionata is None:
        abort(404)
    classi_mancanti = catalogo.classi_pecup_mancanti(identificativo)
    classe = request.values.get("classe", "")
    if classe not in classi_mancanti:
        classe = classi_mancanti[0] if classi_mancanti else ""
    fonti = [int(valore) for valore in request.values.getlist("fonte") if valore.isdigit()]
    anni = [anno for anno in request.values.getlist("anno") if anno in CLASSI]
    if request.method == "POST":
        selezioni = {
            tipo: request.form.getlist(tipo)
            + [
                testo.strip()
                for indice in range(1, 6)
                for testo in [request.form.get(f"{tipo}_personalizzato_{indice}", "")]
                if testo.strip()
            ]
            + [
                testo.strip()
                for testo in request.form.get(f"{tipo}_personalizzato", "").splitlines()
                if testo.strip()
            ]
            for tipo in ("abilita", "conoscenza", "competencia")
        }
        try:
            catalogo.salva_pecup(identificativo, classe, selezioni)
            elenco_codici.aggiorna_elenco_codici()
        except ValueError as errore:
            flash(str(errore), "errore")
        else:
            successive = catalogo.classi_pecup_mancanti(identificativo)
            if successive:
                flash(f"Codici PECUP salvati per {classe}. Completare ora {successive[0]}.", "info")
                return redirect(url_for("admin_pecup_materia", identificativo=identificativo, classe=successive[0]))
            session.pop("pecup_mancanti", None)
            flash("Codici PECUP creati e associati alla materia.", "info")
            return redirect(url_for("admin_materie"))
    return render_template(
        "admin_pecup.html", sezione="materie", materia=materia_selezionata,
        mancanti=session.get("pecup_mancanti", catalogo.percorsi_pecup_mancanti(identificativo)),
        classe=classe, classi_mancanti=classi_mancanti, fonti=fonti, anni=anni,
        materie_fonti=[voce for voce in catalogo.materie() if voce["id"] != identificativo],
        abilita=catalogo.testi_pecup_da_fonti("abilita", fonti, anni),
        conoscenze=catalogo.testi_pecup_da_fonti("conoscenza", fonti, anni),
        competenze=catalogo.testi_pecup_da_fonti("competenza", fonti, anni),
    )


@app.route("/admin/database/importa", methods=["POST"])
def admin_importa():
    if request.form.get("tutti") == "1":
        return _importa_tutti(request.form.get("sostituisci") == "1")

    nome = request.form.get("nome", "")
    percorso = CARTELLA_RICEVUTI / nome
    if Path(nome).name != nome or not percorso.is_file():
        abort(404)
    archivio.importa(percorso)
    flash(f"File aggiunto al data base: {nome}", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/importa-tutti", methods=["POST"])
def admin_importa_tutti():
    return _importa_tutti(request.form.get("sostituisci") == "1")


def _importa_tutti(sostituisci: bool):
    quanti, saltati = archivio.importa_tutti(sostituisci=sostituisci)
    messaggio = f"Aggiunti al data base {quanti} file."
    if saltati and not sostituisci:
        messaggio += " File gia' presenti lasciati invariati: " + ", ".join(saltati)
    flash(messaggio, "info")
    return redirect(url_for("admin_database"))


def _file_ricevuto_selezionato() -> Path:
    nome = request.form.get("nome", "")
    percorso = CARTELLA_RICEVUTI / nome
    if Path(nome).name != nome or not percorso.is_file():
        abort(404)
    return percorso


@app.route("/admin/database/file/stampe", methods=["POST"])
def admin_file_stampe():
    prog = archivio.leggi_file(_file_ricevuto_selezionato())
    modello.salva(prog)
    session["modalita_admin"] = True
    session["contesto"] = {
        chiave: getattr(prog, chiave)
        for chiave in ("cognome", "nome", "classe", "indirizzo", "disciplina")
    }
    return redirect(url_for("step4"))


@app.route("/admin/database/file/impostazioni", methods=["POST"])
def admin_file_impostazioni():
    try:
        prog = archivio.leggi_file(_file_ricevuto_selezionato())
        modello.salva(prog)
    except (OSError, TypeError, ValueError, KeyError) as errore:
        app.logger.exception("Creazione cartella dati fallita")
        flash(f"Impossibile creare la cartella dati: {errore}", "errore")
        return redirect(url_for("admin_database"))
    flash("Create le impostazioni di lavoro del docente.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/file/impostazioni-tutti", methods=["POST"])
def admin_file_impostazioni_tutti():
    cartelle = []
    cartelle_non_create = []
    for percorso in archivio.file_ricevuti():
        prog = None
        try:
            prog = archivio.leggi_file(percorso)
            cartelle.append(modello.salva(prog))
        except (OSError, TypeError, ValueError, KeyError, IndexError, json.JSONDecodeError) as errore:
            app.logger.error("Creazione cartella fallita per %s: %s", percorso.name, errore)
            cartelle_non_create.append(
                f"{prog.cartella_docente}\\{prog.cartella_corso}" if prog is not None else percorso.name
            )
    for record in archivio.elenca():
        prog = None
        try:
            prog = archivio.programmazione(record["id"])
            if prog is not None:
                cartelle.append(modello.salva(prog))
        except (OSError, TypeError, ValueError, KeyError, IndexError, json.JSONDecodeError) as errore:
            nome = record.get("nome_file", str(record["id"]))
            app.logger.error("Creazione cartella fallita per %s: %s", nome, errore)
            cartelle_non_create.append(
                f"{prog.cartella_docente}\\{prog.cartella_corso}" if prog is not None else nome
            )
    uniche = sorted({str(percorso.parent) for percorso in cartelle})
    if cartelle_non_create:
        flash(
            f"Create le impostazioni di lavoro per {len(cartelle)} file in {CARTELLA_LAVORI}. "
            f"Cartelle docenti create: {len(uniche)}. Cartelle non create ({len(cartelle_non_create)}): "
            + " | ".join(cartelle_non_create),
            "errore",
        )
    else:
        flash(
            f"Create le impostazioni di lavoro per {len(cartelle)} file in {CARTELLA_LAVORI}. "
            f"Cartelle docenti create: {len(uniche)}.",
            "info",
        )
    return redirect(url_for("admin_database"))


@app.route("/admin/database/file/elimina", methods=["POST"])
def admin_file_elimina():
    percorso = _file_ricevuto_selezionato()
    nome = percorso.name
    percorso.unlink()
    flash(f"File eliminato: {nome}", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/<int:identificativo>/elimina", methods=["POST"])
def admin_elimina(identificativo: int):
    if not archivio.elimina(identificativo):
        abort(404)
    flash("Record eliminato dal data base.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/<int:identificativo>/esporta", methods=["POST"])
def admin_esporta(identificativo: int):
    percorso = archivio.esporta_su_file(identificativo, request.form.get("referente", ""))
    if percorso is None:
        abort(404)
    flash(f"File creato e salvato in: {percorso}", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/<int:identificativo>/stampe", methods=["POST"])
def admin_stampe(identificativo: int):
    prog = archivio.programmazione(identificativo)
    if prog is None:
        abort(404)
    prodotti = [
        esporta_word.genera_in(prog, tipo, CARTELLA_ADMIN_OUTPUT)
        for tipo in esporta_word.DOCUMENTI
    ]
    flash(
        f"Creati {len(prodotti)} documenti in {CARTELLA_ADMIN_OUTPUT}: "
        + ", ".join(p.name for p in prodotti),
        "info",
    )
    return redirect(url_for("admin_database"))


@app.route("/admin/database/record/<azione>", methods=["POST"])
def admin_azione_record(azione: str):
    identificativo = request.form.get("identificativo", "")
    if not identificativo.isdigit():
        abort(404)
    if azione == "esporta":
        return admin_esporta(int(identificativo))
    if azione == "elimina":
        return admin_elimina(int(identificativo))
    abort(404)


def _selezione_admin():
    classe = request.args.get("classe", "")
    scelti = [i for i in request.args.getlist("indirizzo") if i in catalogo.indirizzi()]
    triennio = classe in CLASSI[2:]
    if not triennio:
        scelti = [i for i in scelti if INDIRIZZI.index(i) < 4]
    return classe, scelti, triennio


@app.route("/admin/curricolo")
def admin_curricolo():
    classe, scelti, triennio = _selezione_admin()
    schede = {int(s["posizione"]): s for s in catalogo.competenze_ue()}
    disponibili = []
    if classe and scelti:
        trovate = archivio.unita_per_competenza(classe, scelti)
        disponibili = [
            {"posizione": posizione, "titolo": schede[posizione]["titolo"], "quante": len(voci)}
            for posizione, voci in sorted(trovate.items())
            if voci
        ]
    return render_template(
        "admin_curricolo.html",
        sezione="curricolo",
        classi=CLASSI,
        nomi_classi=NOMI_CLASSI,
        indirizzi=catalogo.indirizzi(),
        classe=classe,
        scelti=scelti,
        triennio=triennio,
        disponibili=disponibili,
        documento=session.pop("documento_istituto", None),
        documento_word=session.pop("documento_istituto_word", None),
    )


def _aggiorna_creazione(job_id: str, **valori: object) -> None:
    with _CREAZIONI_LOCK:
        stato = _CREAZIONI.get(job_id)
        if stato is not None:
            stato.update(valori)


def _avvia_creazione(lavoro, *, endpoint: str, classe: str, indirizzi: list[str]) -> Response:
    job_id = uuid.uuid4().hex
    with _CREAZIONI_LOCK:
        _CREAZIONI[job_id] = {
            "messaggio": "Preparazione documento...",
            "completato": False,
            "errore": None,
            "endpoint": endpoint,
            "classe": classe,
            "indirizzi": indirizzi,
        }

    def esegui() -> None:
        try:
            risultato = lavoro(lambda messaggio: _aggiorna_creazione(job_id, messaggio=messaggio))
            _aggiorna_creazione(job_id, completato=True, **risultato)
        except Exception as errore:
            _aggiorna_creazione(job_id, completato=True, errore=str(errore))

    threading.Thread(target=esegui, name=f"creazione-{job_id[:8]}", daemon=True).start()
    return redirect(url_for("admin_attesa_creazione", job_id=job_id))


@app.route("/admin/creazione/<job_id>")
def admin_attesa_creazione(job_id: str):
    with _CREAZIONI_LOCK:
        if job_id not in _CREAZIONI:
            abort(404)
    return render_template("admin_attesa.html", job_id=job_id)


@app.route("/admin/creazione/<job_id>/stato")
def admin_stato_creazione(job_id: str):
    with _CREAZIONI_LOCK:
        stato = _CREAZIONI.get(job_id)
        if stato is None:
            abort(404)
        return jsonify({"messaggio": stato["messaggio"], "completato": stato["completato"]})


@app.route("/admin/creazione/<job_id>/fine")
def admin_fine_creazione(job_id: str):
    with _CREAZIONI_LOCK:
        stato = _CREAZIONI.get(job_id)
        if stato is None:
            abort(404)
        if not stato["completato"]:
            return redirect(url_for("admin_attesa_creazione", job_id=job_id))
        stato = dict(stato)
        _CREAZIONI.pop(job_id, None)

    endpoint = str(stato["endpoint"])
    classe = str(stato["classe"])
    indirizzi = list(stato["indirizzi"])
    percorso_word = stato.get("percorso_word")
    errore = stato.get("errore")
    if errore:
        session.pop("documento_istituto", None)
        if percorso_word:
            session["documento_istituto_word"] = Path(str(percorso_word)).name
        flash(f"PDF non creato. {errore}", "errore")
    else:
        percorso = Path(str(stato["percorso"]))
        session["documento_istituto"] = percorso.name
        if percorso_word:
            session["documento_istituto_word"] = Path(str(percorso_word)).name
        else:
            session.pop("documento_istituto_word", None)
        if stato.get("percorso_pdf"):
            flash(
                f"Documento PDF creato e salvato in: {percorso}. Anche il file Word e' disponibile: "
                f"{Path(str(percorso_word)).name}",
                "info",
            )
        else:
            flash(f"Documento creato e salvato in: {percorso}", "info")
    if endpoint == "admin_educazione_civica":
        return redirect(url_for(endpoint, classe=classe, corso=indirizzi[0] if indirizzi else ""))
    return redirect(url_for(endpoint, classe=classe, indirizzo=indirizzi))


@app.route("/admin/curricolo/crea", methods=["POST"])
def admin_crea_curricolo():
    classe = request.form.get("classe", "")
    indirizzi = request.form.getlist("indirizzo")
    competenze = [int(v) for v in request.form.getlist("competenza") if v.isdigit()]
    if not (classe and indirizzi and competenze):
        flash("Selezionare classe, indirizzo e almeno una competenza.", "errore")
        return redirect(url_for("admin_curricolo", classe=classe, indirizzo=indirizzi))
    formato = request.args.get("formato") or request.form.get("formato")
    solo_codici = request.form.get("modo") == "codici"

    def lavoro(avanzamento):
        percorso_word = documenti_istituto.genera_curricolo(
            classe, indirizzi, competenze,
            solo_codici=solo_codici,
            avanzamento=avanzamento,
        )
        risultato = {"percorso_word": str(percorso_word), "percorso": str(percorso_word)}
        if formato == "pdf":
            avanzamento("Produzione PDF - puo' richiedere tempo")
            percorso_pdf = documenti_istituto.converti_pdf(percorso_word)
            risultato.update(percorso_pdf=str(percorso_pdf), percorso=str(percorso_pdf))
        return risultato

    return _avvia_creazione(lavoro, endpoint="admin_curricolo", classe=classe, indirizzi=indirizzi)


@app.route("/admin/multidisciplinare")
def admin_multidisciplinare():
    classe, scelti, triennio = _selezione_admin()
    disponibili = []
    if classe and scelti:
        trovate = archivio.aree_multidisciplinari(classe, scelti)
        disponibili = [{"nome": area, "quante": len(voci)} for area, voci in sorted(trovate.items()) if voci]
    return render_template(
        "admin_multidisciplinare.html",
        sezione="multidisciplinare", classi=CLASSI, nomi_classi=NOMI_CLASSI,
        indirizzi=catalogo.indirizzi(), classe=classe, scelti=scelti, triennio=triennio,
        disponibili=disponibili,
        documento=session.pop("documento_istituto", None),
        documento_word=session.pop("documento_istituto_word", None),
    )


def _corso_educazione(corso: str) -> tuple[str, str] | None:
    return {
        "CAT": ("CAT", "CAT"),
        "GRAFICO": ("GRAFICO", "GRAFICO"),
        "AGRARIO": ("AGRARIO", "AGRARIO (tutte le articolazioni)"),
    }.get(corso)


def _calcola_completamento() -> list[dict[str, object]]:
    risultato = []
    for corso in ("CAT", "GRAFICO", "AGRARIO"):
        ore_per_classe = []
        for classe in CLASSI:
            articolazioni = ("COMUNE", "PT", "GAT", "ENO") if corso == "AGRARIO" else ("COMUNE",)
            piani = {}
            for articolazione in articolazioni:
                for piano in educazione_civica.piani_contesto(corso, classe, articolazione):
                    piani[(piano["disciplina"], articolazione)] = piano
            ore = sum(
                int(piano.get("ore_disciplina", 0) or 0)
                or sum(int(voce.get("ore", 0) or 0) for voce in piano.get("voci", []))
                for piano in piani.values()
            )
            ore_per_classe.append(ore)
        risultato.append({"corso": corso, "ore": ore_per_classe})
    return risultato


@app.route("/admin/educazione-civica/salva", methods=["POST"])
def admin_salva_educazione_civica():
    dati = request.get_json(silent=True) or {}
    corso = str(dati.get("corso", ""))
    classe = str(dati.get("classe", ""))
    disciplina = str(dati.get("disciplina", ""))
    configurazione = dati.get("configurazione") or {}
    if corso not in ("CAT", "GRAFICO", "AGRARIO") or classe not in CLASSI or not disciplina:
        return jsonify(ok=False, errore="Dati del piano non validi."), 400
    articolazione = str(dati.get("articolazione", "COMUNE"))
    if corso != "AGRARIO" or classe in ("PRIMA", "SECONDA"):
        articolazione = "COMUNE"
    voci = configurazione.get("voci") or []
    ore = sum(int(voce.get("ore", 0) or 0) for voce in voci)
    if ore <= 0:
        educazione_civica.elimina_piano(corso, classe, articolazione, disciplina)
        return jsonify(ok=True, completamento=_calcola_completamento())
    vecchio = educazione_civica.piano(corso, classe, articolazione, disciplina) or {}
    educazione_civica.salva_piano(
        corso,
        classe,
        articolazione,
        disciplina,
        {
            "macroarea": str(configurazione.get("macroarea", "")),
            "voci": voci,
            "ore_disciplina": ore,
            "conferme": vecchio.get("conferme", {}),
        },
    )
    return jsonify(ok=True, completamento=_calcola_completamento())


@app.route("/admin/educazione-civica", methods=["GET", "POST"])
def admin_educazione_civica():
    corso = request.values.get("corso", "")
    classe = request.values.get("classe", "")
    destinazione = _corso_educazione(corso)
    indirizzo_catalogo = destinazione[1] if destinazione else ""
    if classe and indirizzo_catalogo:
        if corso == "AGRARIO" and classe in ("TERZA", "QUARTA", "QUINTA"):
            discipline = catalogo.discipline_normalizzate(
                classe,
                ("AGRARIO (tutte le articolazioni)", "AGRARIO (p.t.)", "AGRARIO (g.a.t.)", "AGRARIO (eno)"),
            )
        else:
            discipline = catalogo.discipline_normalizzate(classe, ("COMUNE", indirizzo_catalogo))
    else:
        discipline = []
    macroaree = educazione_civica.catalogo_voci()
    macroarea = request.values.get("macroarea", educazione_civica.MACROAREE[0])
    if macroarea not in macroaree:
        macroarea = educazione_civica.MACROAREE[0]

    completamento = _calcola_completamento()

    if request.method == "POST" and request.form.get("azione") == "salva":
        if not destinazione or classe not in CLASSI:
            flash("Selezionare un tipo di corso e una classe validi.", "errore")
        elif not request.form.getlist("disciplina"):
            flash("Selezionare almeno una disciplina.", "errore")
        else:
            articolazione = request.form.get("articolazione", "COMUNE")
            if corso != "AGRARIO" or classe in ("PRIMA", "SECONDA"):
                articolazione = "COMUNE"
            configurazioni = json.loads(request.form.get("configurazioni", "{}"))
            for disciplina in request.form.getlist("disciplina"):
                configurazione = configurazioni.get(disciplina, {})
                voci = configurazione.get("voci", [])
                ore = str(configurazione.get("ore_disciplina", "0"))
                if not ore.isdigit():
                    flash(f"Le ore della disciplina {disciplina} devono essere numeriche.", "errore")
                    break
                vecchio = educazione_civica.piano(corso, classe, articolazione, disciplina) or {}
                dati_disciplina = {
                    "macroarea": configurazione.get("macroarea", ""),
                    "voci": voci,
                    "ore_disciplina": int(ore),
                    "conferme": vecchio.get("conferme", {}),
                }
                educazione_civica.salva_piano(corso, classe, articolazione, disciplina, dati_disciplina)
            else:
                flash("Bozza del piano di Educazione civica memorizzata.", "info")

    articolazioni_visualizzate = (
        ("PT", "GAT", "ENO") if corso == "AGRARIO" and classe in ("TERZA", "QUARTA", "QUINTA")
        else ("COMUNE",)
    )
    piani_per_articolazione = {
        articolazione: {
            catalogo.nome_disciplina_visualizzato(voce["disciplina"]): voce
            for voce in educazione_civica.piani_contesto(corso, classe, articolazione)
        }
        for articolazione in ("COMUNE", *articolazioni_visualizzate)
    }
    indirizzi_articolazioni = {"PT": "AGRARIO (p.t.)", "GAT": "AGRARIO (g.a.t.)", "ENO": "AGRARIO (eno)"}
    indirizzo_comune = "AGRARIO (tutte le articolazioni)"

    def disciplina_presente_nell_articolazione(disciplina: str, articolazione: str) -> bool:
        if corso != "AGRARIO":
            return catalogo.disciplina_presente(classe, indirizzo_catalogo, disciplina)
        if articolazione == "COMUNE":
            return catalogo.disciplina_presente(classe, indirizzo_comune, disciplina)
        if catalogo.disciplina_presente(classe, indirizzi_articolazioni[articolazione], disciplina):
            return True
        esiste_specifica = any(
            catalogo.disciplina_presente(classe, indirizzo, disciplina)
            for indirizzo in indirizzi_articolazioni.values()
        )
        return not esiste_specifica and catalogo.disciplina_presente(classe, indirizzo_comune, disciplina)

    def piano_per_articolazione(disciplina: str, articolazione: str):
        piano_specifico = piani_per_articolazione[articolazione].get(disciplina)
        if piano_specifico:
            return piano_specifico
        if articolazione == "COMUNE":
            return piani_per_articolazione["COMUNE"].get(disciplina)
        esiste_specifica = any(
            catalogo.disciplina_presente(classe, indirizzo, disciplina)
            for indirizzo in indirizzi_articolazioni.values()
        )
        if not esiste_specifica and disciplina_presente_nell_articolazione(disciplina, articolazione):
            return piani_per_articolazione["COMUNE"].get(disciplina)
        return None

    righe = []
    for disciplina in discipline:
        stati = {}
        piano_comune = piani_per_articolazione["COMUNE"].get(disciplina)
        voci_piano = (piano_comune or {}).get("voci", [])
        stati_voci = {}
        for articolazione in articolazioni_visualizzate:
            presente = disciplina_presente_nell_articolazione(disciplina, articolazione)
            piano = piano_per_articolazione(disciplina, articolazione)
            conferme = (piano or {}).get("conferme", {})
            stati[articolazione] = {
                "admin": educazione_civica.stato_piano(piano) if piano and presente else "rosso" if presente else "inattivo",
                "docente": "verde" if conferme else "rosso" if presente else "inattivo",
            }
        for voce in voci_piano:
            nome_voce = voce.get("voce", "")
            stati_voce = {}
            for articolazione in articolazioni_visualizzate:
                presente = disciplina_presente_nell_articolazione(disciplina, articolazione)
                piano_voce = piano_per_articolazione(disciplina, articolazione)
                conferme_voce = (piano_voce or {}).get("conferme", {})
                conferme_della_voce = [
                    dati for dati in conferme_voce.values()
                    if nome_voce in dati.get("voci", [])
                ]
                conferma = next(
                    iter(conferme_della_voce),
                    next(iter(conferme_voce.values()), None) if conferme_voce and not any("voci" in dati for dati in conferme_voce.values()) else None,
                )
                quadrimestri = {
                    dati.get("quadrimestre")
                    for dati in conferme_della_voce
                    if dati.get("quadrimestre") in ("I", "II")
                }
                stati_voce[articolazione] = {
                    "stato": "verde" if conferma else "rosso" if presente else "inattivo",
                    "testo": (
                        "entrambi"
                        if len(quadrimestri) > 1
                        else f"{conferma.get('quadrimestre')} quadrimestre"
                        if conferma and conferma.get("quadrimestre")
                        else "DA CONFERMARE" if presente else "INATTIVO"
                    ),
                }
            stati_voci[nome_voce] = stati_voce
        righe.append({
            "disciplina": disciplina,
            "piano": piano_comune,
            "attiva": bool(piano_comune and any(int(voce.get("ore", 0) or 0) > 0 for voce in piano_comune.get("voci", []))),
            "stati": stati,
            "stati_voci": stati_voci,
        })
    return render_template(
        "admin_educazione_civica.html",
        sezione="educazione-civica", corsi=("CAT", "GRAFICO", "AGRARIO"),
        classi=CLASSI, corso=corso, classe=classe, articolazioni=("PT", "GAT", "ENO"),
        discipline=discipline, righe=righe, piani=piani_per_articolazione["COMUNE"], macroaree=macroaree,
        articolazioni_visualizzate=articolazioni_visualizzate,
        macroarea=macroarea, voci=macroaree[macroarea], completamento=completamento,
        stati_voci={riga["disciplina"]: riga["stati_voci"] for riga in righe},
        documento=session.pop("documento_istituto", None),
        documento_word=session.pop("documento_istituto_word", None),
    )


@app.route("/admin/multidisciplinare/crea", methods=["POST"])
def admin_crea_multidisciplinare():
    classe = request.form.get("classe", "")
    indirizzi = request.form.getlist("indirizzo")
    aree = request.form.getlist("area")
    if not (classe and indirizzi and aree):
        flash("Selezionare classe, indirizzo e almeno un'area.", "errore")
        return redirect(url_for("admin_multidisciplinare", classe=classe, indirizzo=indirizzi))
    formato = request.args.get("formato") or request.form.get("formato")

    def lavoro(avanzamento):
        percorso_word = documenti_istituto.genera_multidisciplinare(
            classe, indirizzi, aree, avanzamento=avanzamento
        )
        risultato = {"percorso_word": str(percorso_word), "percorso": str(percorso_word)}
        if formato == "pdf":
            avanzamento("Produzione PDF - puo' richiedere tempo")
            percorso_pdf = documenti_istituto.converti_pdf(percorso_word)
            risultato.update(percorso_pdf=str(percorso_pdf), percorso=str(percorso_pdf))
        return risultato

    return _avvia_creazione(
        lavoro, endpoint="admin_multidisciplinare", classe=classe, indirizzi=indirizzi
    )


@app.route("/admin/completamento")
def admin_completamento():
    return render_template(
        "admin_completamento.html", sezione="completamento", griglia=completamento.griglia()
    )


def _documento_admin(nome: str) -> Path | None:
    percorso = CARTELLA_ADMIN_OUTPUT / nome
    if Path(nome).name != nome or not percorso.is_file():
        return None
    return percorso


@app.route("/admin/documento/<nome>")
def admin_scarica(nome: str):
    percorso = _documento_admin(nome)
    if percorso is None:
        abort(404)
    return send_file(percorso, as_attachment=True)


@app.route("/admin/documento/apri", methods=["POST"])
def admin_apri():
    percorso = _documento_admin(request.form.get("nome", ""))
    if percorso is None:
        abort(404)
    if not hasattr(os, "startfile"):
        flash("Apertura automatica non disponibile su questo sistema.", "errore")
    else:
        os.startfile(percorso)
        flash(f"Documento aperto: {percorso.name}", "info")
    return redirect(request.referrer or url_for("admin_database"))


if __name__ == "__main__":
    prepara_cartelle_admin()
    eseguibile = getattr(sys, "frozen", False)
    porta = 5001 if eseguibile else 5000
    if eseguibile:
        threading.Thread(target=controlla_heartbeat, daemon=True).start()
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{porta}")).start()
    app.run(debug=not eseguibile, port=porta)