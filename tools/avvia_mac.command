#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

mostra_istruzioni_python() {
    scelta="$(osascript -e 'display dialog "CreaCurricoloMulti non riesce a usare Python 3.10 o successivo." & return & "Scarica il programma di installazione macOS universal2 dalla pagina ufficiale, apri il file .pkg scaricato e completa l’installazione. Poi riapri questo launcher." buttons {"Chiudi", "Apri download ufficiali"} default button "Apri download ufficiali" with title "Installare Python" with icon caution')"
    if [[ "$scelta" == *"button returned:Apri download ufficiali"* ]]; then
        open "https://www.python.org/downloads/macos/"
    fi
}

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
    mostra_istruzioni_python
    exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
    if ! "$PYTHON" -m venv .venv; then
        mostra_istruzioni_python
        exit 1
    fi
fi

if ! ".venv/bin/python" -c 'import flask, docx, openpyxl, pypdf' >/dev/null 2>&1; then
    echo "Installazione delle dipendenze da PyPI (https://pypi.org/)..."
    ".venv/bin/python" -m pip install --disable-pip-version-check \
        --index-url "https://pypi.org/simple" -r requirements.txt
fi

exec ".venv/bin/python" -m tools.avvia_mac
