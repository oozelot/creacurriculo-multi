"""Create a distribution ZIP with stable timestamps and entry ordering."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import zipfile


def crea_archivio(sorgente: Path, destinazione: Path, epoca: int) -> None:
    sorgente = sorgente.resolve()
    destinazione = destinazione.resolve()
    if not sorgente.is_dir():
        raise FileNotFoundError(f"Cartella di distribuzione mancante: {sorgente}")
    if sorgente == destinazione or sorgente in destinazione.parents:
        raise ValueError("L'archivio ZIP non puo' essere creato dentro la distribuzione.")

    data = datetime.fromtimestamp(epoca, timezone.utc)
    if not 1980 <= data.year <= 2107:
        raise ValueError("SOURCE_DATE_EPOCH deve corrispondere a una data supportata dal formato ZIP.")
    timestamp = (
        data.year,
        data.month,
        data.day,
        data.hour,
        data.minute,
        data.second - data.second % 2,
    )

    destinazione.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        destinazione, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archivio:
        percorsi = [
            sorgente,
            *sorted(
                sorgente.rglob("*"),
                key=lambda voce: voce.relative_to(sorgente).as_posix(),
            ),
        ]
        for percorso in percorsi:
            if percorso.is_symlink():
                raise ValueError(f"Collegamento simbolico non supportato nella distribuzione: {percorso}")
            nome = sorgente.name
            relativo = percorso.relative_to(sorgente)
            if relativo.parts:
                nome = f"{nome}/{relativo.as_posix()}"
            if percorso.is_dir():
                nome += "/"
                modalita = stat.S_IFDIR | 0o755
                contenuto = b""
            elif percorso.is_file():
                modalita = stat.S_IFREG | stat.S_IMODE(percorso.stat().st_mode)
                contenuto = percorso.read_bytes()
            else:
                raise ValueError(f"Elemento di distribuzione non supportato: {percorso}")
            voce_zip = zipfile.ZipInfo(nome, timestamp)
            voce_zip.create_system = 3
            voce_zip.external_attr = modalita << 16
            if percorso.is_dir():
                voce_zip.external_attr |= 0x10
            voce_zip.compress_type = zipfile.ZIP_DEFLATED
            archivio.writestr(voce_zip, contenuto, compresslevel=9)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un archivio ZIP riproducibile della distribuzione.")
    parser.add_argument("sorgente", type=Path)
    parser.add_argument("destinazione", type=Path)
    args = parser.parse_args()
    valore_epoca = os.environ.get("SOURCE_DATE_EPOCH")
    if valore_epoca is None:
        parser.error("Impostare SOURCE_DATE_EPOCH prima di creare l'archivio.")
    try:
        epoca = int(valore_epoca)
    except ValueError:
        parser.error("SOURCE_DATE_EPOCH deve essere un timestamp Unix intero.")
    crea_archivio(args.sorgente, args.destinazione, epoca)


if __name__ == "__main__":
    main()
