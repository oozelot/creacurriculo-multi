"""Avvia l'applicazione macOS con il Python installato dall'utente."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
import webbrowser

import main


def _apri_browser_quando_pronto(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(url, timeout=1):
                webbrowser.open(url)
                return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    print(f"Apri manualmente l'applicazione: {url}")


def main_mac() -> None:
    main.prepara_cartelle_admin()
    porta = main._porta_locale_disponibile(5001)
    url = f"http://127.0.0.1:{porta}"
    threading.Thread(target=_apri_browser_quando_pronto, args=(url,), daemon=True).start()
    main.app.run(debug=False, port=porta)


if __name__ == "__main__":
    main_mac()
