import hashlib
import zipfile

import pytest

from tools.archivia_dist import crea_archivio


def test_archivio_usa_timestamp_e_ordinamento_stabili(tmp_path):
    distribuzione = tmp_path / "CreaCurricoloMulti"
    templates = distribuzione / "templates"
    templates.mkdir(parents=True)
    launcher = distribuzione / "Avvia CreaCurricolo.command"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    (templates / "index.html").write_text("<h1>Curricolo</h1>\n", encoding="utf-8")
    archive_a = tmp_path / "a.zip"
    archive_b = tmp_path / "b.zip"

    crea_archivio(distribuzione, archive_a, 1_759_276_800)
    launcher.touch()
    crea_archivio(distribuzione, archive_b, 1_759_276_800)

    assert hashlib.sha256(archive_a.read_bytes()).digest() == hashlib.sha256(archive_b.read_bytes()).digest()
    with zipfile.ZipFile(archive_a) as archivio:
        assert archivio.namelist() == [
            "CreaCurricoloMulti/",
            "CreaCurricoloMulti/Avvia CreaCurricolo.command",
            "CreaCurricoloMulti/templates/",
            "CreaCurricoloMulti/templates/index.html",
        ]
        assert all(voce.date_time == (2025, 10, 1, 0, 0, 0) for voce in archivio.infolist())


def test_archivio_rifiuta_timestamp_fuori_dal_formato_zip(tmp_path):
    distribuzione = tmp_path / "CreaCurricoloMulti"
    distribuzione.mkdir()

    with pytest.raises(ValueError, match="SOURCE_DATE_EPOCH"):
        crea_archivio(distribuzione, tmp_path / "release.zip", 0)
