import pytest

from curricolo import catalogo
from main import app


def test_conferma_materia_senza_bozza_non_400():
    client = app.test_client()
    response = client.post("/admin/materie/1/conferma", data={"azione": "pecup"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/materie/1/pecup")


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
