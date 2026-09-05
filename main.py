"""Applicazione web che riproduce il flusso del programma VB6 (Step 1-4)."""

from __future__ import annotations

import os
import shutil
import sys
import threading
import webbrowser
from pathlib import Path

from flask import (
    Flask,
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
    CARTELLA_RICEVUTI,
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


def prepara_cartelle_admin() -> None:
    for cartella in (CARTELLA_ADMIN, CARTELLA_ADMIN_INPUT, CARTELLA_RICEVUTI, CARTELLA_ADMIN_OUTPUT):
        cartella.mkdir(parents=True, exist_ok=True)


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
        cognome = request.form.get("cognome", "").strip().upper()
        nome = request.form.get("nome", "").strip().upper()
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
                modello.salva(prog)
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
        flash(f"Massimo {MAX_UD} unita' didattiche per modulo.", "errore")
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

    if request.method == "POST":
        ud.titolo = request.form.get("titolo", "").strip()
        ud.argomenti = request.form.get("argomenti", "")
        ud.prerequisiti = request.form.get("prerequisiti", "")
        ud.multidisciplinare = [int(request.form.get("multidisciplinare", 1) or 1)]
        ud.multidisciplinare_altro = request.form.get("multidisciplinare_altro", "").strip()
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
        quadro_altro_valido = ud.multidisciplinare[0] != 4 or len(ud.multidisciplinare_altro.strip()) >= 3
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
        ):
            flash("Completare tutti i campi obbligatori dell'unita' didattica.", "errore")
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
                limiti=LIMITI,
                intervallo_abilita=range(1, MAX_ABILITA + 1),
                intervallo_conoscenze=range(1, MAX_CONOSCENZE + 1),
                intervallo_competenze=range(1, MAX_COMPETENZE_PECUP + 1),
            )
        modello.salva(prog)
        flash("Unita' didattica salvata.", "info")
        return redirect(url_for("unita", numero=numero, indice=indice))

    chiave = (prog.disciplina, prog.classe, prog.indirizzo)
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
        limiti=LIMITI,
        intervallo_abilita=range(1, MAX_ABILITA + 1),
        intervallo_conoscenze=range(1, MAX_CONOSCENZE + 1),
        intervallo_competenze=range(1, MAX_COMPETENZE_PECUP + 1),
    )


@app.route("/step4")
def step4():
    if not session.get("contesto") or not stato_navigazione()["accesso_step4"]:
        return redirect(url_for("step1"))
    prog = _programmazione()
    cartella_invio = legacy.cartella_docente(prog.cognome, prog.nome) / "da_inviare"
    nome = esporta_ini.nome_file_invio(prog)
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
    percorso = cartella / esporta_ini.nome_file_invio(prog)
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
    os.startfile(percorso)  # apre con il programma predefinito del computer del docente
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


@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    """Elimina i dati locali e prepara un archivio nuovo al successivo accesso."""
    global _sessione_inizializzata
    session.clear()
    if CARTELLA_ADMIN.exists():
        shutil.rmtree(CARTELLA_ADMIN)
    db.resetta_database()
    prepara_cartelle_admin()
    _sessione_inizializzata = True
    flash("Lavoro e dati locali azzerati. Il catalogo di base e' stato ricostruito.", "info")
    return redirect(url_for("step1"))


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
    if len(nome) < 3 or len(sigla) < 3 or not percorsi:
        flash("Inserire nome, sigla e almeno un percorso di studio.", "errore")
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
    if bozza.get("id") != identificativo:
        abort(400)
    if not catalogo.aggiorna_percorsi_materia(identificativo, bozza.get("percorsi", [])):
        abort(404)
    session.pop("bozza_materia", None)
    session.pop("pecup_mancanti", None)
    if request.form.get("azione") == "pecup":
        return redirect(url_for("admin_pecup_materia", identificativo=identificativo))
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
            tipo: request.form.getlist(tipo) + [testo.strip() for testo in request.form.get(f"{tipo}_personalizzato", "").splitlines() if testo.strip()]
            for tipo in ("abilita", "conoscenza", "competenza")
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
    prog = archivio.leggi_file(_file_ricevuto_selezionato())
    modello.salva(prog)
    flash("Create le impostazioni di lavoro del docente.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/<int:identificativo>/elimina", methods=["POST"])
def admin_elimina(identificativo: int):
    if not archivio.elimina(identificativo):
        abort(404)
    flash("Record eliminato dal data base.", "info")
    return redirect(url_for("admin_database"))


@app.route("/admin/database/<int:identificativo>/esporta", methods=["POST"])
def admin_esporta(identificativo: int):
    percorso = archivio.esporta_su_file(identificativo)
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
    )


@app.route("/admin/curricolo/crea", methods=["POST"])
def admin_crea_curricolo():
    classe = request.form.get("classe", "")
    indirizzi = request.form.getlist("indirizzo")
    competenze = [int(v) for v in request.form.getlist("competenza") if v.isdigit()]
    if not (classe and indirizzi and competenze):
        flash("Selezionare classe, indirizzo e almeno una competenza.", "errore")
        return redirect(url_for("admin_curricolo", classe=classe, indirizzo=indirizzi))

    percorso = documenti_istituto.genera_curricolo(
        classe, indirizzi, competenze, solo_codici=request.form.get("modo") == "codici"
    )
    session["documento_istituto"] = percorso.name
    flash(f"Documento creato e salvato in: {percorso}", "info")
    return redirect(url_for("admin_curricolo", classe=classe, indirizzo=indirizzi))


@app.route("/admin/multidisciplinare")
def admin_multidisciplinare():
    classe, scelti, triennio = _selezione_admin()
    disponibili = []
    if classe and scelti:
        trovate = archivio.aree_multidisciplinari(classe, scelti)
        disponibili = [
            {"nome": area, "quante": len(voci)} for area, voci in sorted(trovate.items()) if voci
        ]
    return render_template(
        "admin_multidisciplinare.html",
        sezione="multidisciplinare",
        classi=CLASSI,
        nomi_classi=NOMI_CLASSI,
        indirizzi=catalogo.indirizzi(),
        classe=classe,
        scelti=scelti,
        triennio=triennio,
        disponibili=disponibili,
        documento=session.pop("documento_istituto", None),
    )


@app.route("/admin/multidisciplinare/crea", methods=["POST"])
def admin_crea_multidisciplinare():
    classe = request.form.get("classe", "")
    indirizzi = request.form.getlist("indirizzo")
    aree = request.form.getlist("area")
    if not (classe and indirizzi and aree):
        flash("Selezionare classe, indirizzo e almeno un'area.", "errore")
        return redirect(url_for("admin_multidisciplinare", classe=classe, indirizzo=indirizzi))

    percorso = documenti_istituto.genera_multidisciplinare(classe, indirizzi, aree)
    session["documento_istituto"] = percorso.name
    flash(f"Documento creato e salvato in: {percorso}", "info")
    return redirect(url_for("admin_multidisciplinare", classe=classe, indirizzo=indirizzi))


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
    eseguibile = getattr(sys, "frozen", False)
    if eseguibile:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=not eseguibile)