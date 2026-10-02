import pytest

import main
from curricolo import catalogo
from main import app


def test_salvataggio_pecup_include_competenze_e_ritorna_alla_selezione(monkeypatch):
    stato = {"salvato": False}
    selezioni_ricevute = {}
    materia = {
        "id": 99,
        "nome": "MATERIA NUOVA",
        "sigla": "MNU",
        "percorsi": [("PRIMA", "COMUNE")],
    }
    monkeypatch.setattr(main, "_sessione_inizializzata", True)
    monkeypatch.setattr(catalogo, "materia", lambda identificativo: materia)
    monkeypatch.setattr(
        catalogo,
        "classi_pecup_mancanti",
        lambda identificativo: [] if stato["salvato"] else ["PRIMA"],
    )
    monkeypatch.setattr(catalogo, "materie", lambda: [])
    monkeypatch.setattr(catalogo, "percorsi_pecup_mancanti", lambda identificativo: [])
    monkeypatch.setattr(
        catalogo,
        "testi_pecup_da_fonti",
        lambda tipo, fonti, anni: [f"TESTO {tipo.upper()}"],
    )

    def salva_pecup(identificativo, classe, selezioni):
        selezioni_ricevute.update(selezioni)
        stato["salvato"] = True

    monkeypatch.setattr(catalogo, "salva_pecup", salva_pecup)
    monkeypatch.setattr(main.elenco_codici, "aggiorna_elenco_codici", lambda: None)

    response = app.test_client().post(
        "/admin/materie/99/pecup",
        data={
            "classe": "PRIMA",
            "fonte": "2",
            "anno": "PRIMA",
            "abilita": "TESTO ABILITA",
            "conoscenza": "TESTO CONOSCENZA",
            "competenza": "TESTO COMPETENZA",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert selezioni_ricevute == {
        "abilita": ["TESTO ABILITA"],
        "conoscenza": ["TESTO CONOSCENZA"],
        "competenza": ["TESTO COMPETENZA"],
    }
    assert b"Codici salvati" in response.data
    assert b'<option value="PRIMA" selected>' in response.data
    assert b"name=\"fonte\" value=\"2\"" in response.data


def test_conferma_materia_senza_bozza_non_400():
    client = app.test_client()
    response = client.post("/admin/materie/1/conferma", data={"azione": "pecup"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/materie/1/pecup")


@pytest.mark.parametrize(
    ("percorsi_mancanti", "mostra_conferma_pecup"),
    [([("PRIMA", "COMUNE")], True), ([], False)],
)
def test_aggiunta_materia_apre_la_schermata_di_completamento(
    monkeypatch, percorsi_mancanti, mostra_conferma_pecup
):
    materia = {
        "id": 99,
        "nome": "MATERIA NUOVA",
        "sigla": "MNU",
        "percorsi": [("PRIMA", "COMUNE")],
        "avviso": "",
        "completa": False,
    }
    monkeypatch.setattr(main, "_sessione_inizializzata", True)
    monkeypatch.setattr(catalogo, "valida_sigla_tecnica", lambda sigla: True)
    monkeypatch.setattr(catalogo, "sigla_tecnica_in_uso", lambda sigla: False)
    monkeypatch.setattr(catalogo, "aggiungi_materia", lambda nome, sigla, percorsi: 99)
    monkeypatch.setattr(
        catalogo,
        "percorsi_pecup_mancanti",
        lambda identificativo: percorsi_mancanti,
    )
    monkeypatch.setattr(catalogo, "materia", lambda identificativo: materia)
    monkeypatch.setattr(catalogo, "materie", lambda: [materia])

    response = app.test_client().post(
        "/admin/materie/aggiungi",
        data={"nome": "MATERIA NUOVA", "sigla": "MNU", "percorso": "PRIMA|COMUNE"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'action="/admin/materie/99/modifica"' in response.data
    assert b"Premi quando completato le modifiche" in response.data
    assert (b"S\xc3\xac, gestisci codici PECUP" in response.data) == mostra_conferma_pecup


def test_elimina_materia_usa_id_selezionato_nel_form(monkeypatch):
    eliminati = []
    materia = {
        "id": 42,
        "nome": "MATERIA",
        "sigla": "MAT",
        "percorsi": [("PRIMA", "COMUNE")],
    }
    monkeypatch.setattr(main, "_sessione_inizializzata", True)
    monkeypatch.setattr(catalogo, "materia", lambda identificativo: materia)
    monkeypatch.setattr(catalogo, "piani_educazione_per_rimozione", lambda identificativo, percorsi=None: [])
    monkeypatch.setattr(
        catalogo,
        "applica_rimozione_materia",
        lambda identificativo, destinatari=None, percorsi_nuovi=None, sigla_nuova="": eliminati.append(identificativo) or True,
    )

    client = app.test_client()
    response = client.post(
        "/admin/materie/elimina",
        data={"identificativo": "42"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    response = client.post(
        "/admin/materie/elimina/decidi",
        data={"azione": "senza_trasferire"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/materie")
    assert eliminati == [42]


def test_elimina_materia_rifiuta_id_mancante():
    response = app.test_client().post("/admin/materie/elimina", data={})

    assert response.status_code == 400


def test_form_elimina_materia_invia_id_selezionato(monkeypatch):
    monkeypatch.setattr(main, "_sessione_inizializzata", True)
    monkeypatch.setattr(catalogo, "materie", lambda: [])

    response = app.test_client().get("/admin/materie")

    assert response.status_code == 200
    assert b'action="/admin/materie/elimina"' in response.data
    assert b'name="identificativo" id="materia-da-eliminare"' in response.data


def test_aggiungi_materia_rifiuta_sigla_duplicata_in_materia_diversa():
    catalogo.aggiungi_materia("MATEMATICA", "MAT", [("PRIMA", "COMUNE")])

    with pytest.raises(ValueError, match="sigla"):
        catalogo.aggiungi_materia("SCIENZE", "MAT", [("PRIMA", "COMUNE")])


def test_admin_reset_richiede_password_admin():
    client = app.test_client()
    response = client.post("/admin/reset", data={"password": "sbagliata"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/database")


def test_admin_memorizza_pecup_richiede_password_admin():
    client = app.test_client()
    response = client.post("/admin/memorizza-pecup", data={"password": "sbagliata"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/database")
