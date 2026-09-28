#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON=""
for candidate in "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "$(command -v python3 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] \
        && "$candidate" -c 'import ensurepip, sys, venv; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
        >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Per avviare CreaCurricoloMulti serve Python 3.10 o successivo."
    echo "Scarica e installa il pacchetto macOS universale (universal2) dalla pagina ufficiale, poi riavvia questo launcher."
    open "https://www.python.org/downloads/macos/" || true
    exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
    if ! "$PYTHON" -m venv .venv; then
        echo "Non riesco a creare l'ambiente Python. Installa Python dal sito ufficiale e riprova:"
        echo "https://www.python.org/downloads/macos/"
        read -r -p "Premi Invio per chiudere. "
        exit 1
    fi
fi

if ! ".venv/bin/python" -c 'import flask, docx, openpyxl, pypdf' >/dev/null 2>&1; then
    echo "Installazione delle dipendenze da PyPI (https://pypi.org/)..."
    ".venv/bin/python" -m pip install --disable-pip-version-check \
        --index-url "https://pypi.org/simple" -r requirements.txt
fi

exec ".venv/bin/python" -m tools.avvia_mac
