from pathlib import Path

import main
from main import app
from curricolo.config import CARTELLA_RICEVUTI


def test_crea_impostazioni_da_file_ricevuto():
    files = sorted(CARTELLA_RICEVUTI.glob("*.ini"))
    if not files:
        return

    client = app.test_client()
    response = client.post(
        "/admin/database/file/impostazioni",
        data={"nome": Path(files[0]).name},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/database")


def test_crea_impostazioni_gestisci_errore_scrittura(monkeypatch):
    files = sorted(CARTELLA_RICEVUTI.glob("*.ini"))
    if not files:
        return

    def salva_fallisce(_prog):
        raise OSError("permesso negato")

    monkeypatch.setattr(main.modello, "salva", salva_fallisce)
    response = app.test_client().post(
        "/admin/database/file/impostazioni",
        data={"nome": Path(files[0]).name},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Impossibile creare la cartella dati" in response.get_data(as_text=True)


def test_crea_impostazioni_tutti_non_si_interrompe_per_un_file(monkeypatch):
    def salva_fallisce(_prog):
        raise OSError("permesso negato")

    monkeypatch.setattr(main.modello, "salva", salva_fallisce)
    response = app.test_client().post(
        "/admin/database/file/impostazioni-tutti",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Elementi non elaborati" in response.get_data(as_text=True)