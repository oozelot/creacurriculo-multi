"""Riparazione dei testi corrotti nei file INI legacy.

Alcuni contenuti incollati da Word sono stati salvati come byte UTF-8 dentro file
scritti in cp1252: rileggendoli compaiono sequenze come "lâ€™ipotesi" al posto di
"l'ipotesi". La correzione si applica solo in visualizzazione e nei documenti Word:
i file INI vanno riscritti come sono, per restare identici a quelli del VB6.
"""

from __future__ import annotations

# Un carattere UTF-8 corrotto occupa 2-4 byte, riletti in cp1252 come altrettanti caratteri:
# si ricompongono i byte e li si ridecodifica, ma solo quando formano UTF-8 valido.
LUNGHEZZE = (4, 3, 2)
PRIMO_BYTE_MINIMO = {2: 0xC2, 3: 0xE0, 4: 0xF0}


def _ricompone(pezzo: str, lunghezza: int) -> str | None:
    try:
        byte = pezzo.encode("cp1252")
    except UnicodeEncodeError:
        return None
    if len(byte) != lunghezza or byte[0] < PRIMO_BYTE_MINIMO[lunghezza]:
        return None
    try:
        return byte.decode("utf-8")
    except UnicodeDecodeError:
        return None


def ripara_mojibake(testo: str) -> str:
    if not testo:
        return testo

    risultato: list[str] = []
    posizione = 0
    while posizione < len(testo):
        riparato = None
        for lunghezza in LUNGHEZZE:
            if posizione + lunghezza <= len(testo):
                riparato = _ricompone(testo[posizione : posizione + lunghezza], lunghezza)
                if riparato is not None:
                    risultato.append(riparato)
                    posizione += lunghezza
                    break
        if riparato is None:
            risultato.append(testo[posizione])
            posizione += 1
    return "".join(risultato)
