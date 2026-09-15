"""Rimuove gli artefatti generati prima di una nuova compilazione."""

from pathlib import Path
import shutil


for nome in ("build", "dist"):
    percorso = Path(nome)
    if percorso.exists():
        shutil.rmtree(percorso)
        print(f"Rimossa: {percorso}")
