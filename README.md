# CreaCurricoloMulti

Versione multipiattaforma di CreaCurricolo per Windows, macOS e Linux.

## Requisiti

- Python 3.10 o successivo per l'avvio da sorgente.
- LibreOffice installato e disponibile nel percorso di sistema per creare i PDF.
- Microsoft Word non e' necessario.

L'applicazione genera i documenti Word `.docx` con `python-docx`. Quando viene richiesto un PDF, usa LibreOffice in modalita' headless. Se LibreOffice non e' installato, il documento Word viene comunque creato e l'applicazione mostra un messaggio che indica come completare la conversione.

## Installazione di LibreOffice

- Windows: installare LibreOffice dal sito ufficiale e riavviare l'applicazione.
- macOS: installare LibreOffice nella cartella Applicazioni.
- Linux: installare il pacchetto LibreOffice tramite il gestore della distribuzione.

L'app cerca `soffice`, `libreoffice` e, su macOS, il percorso standard dell'applicazione.

## Avvio da sorgente

```text
python -m pip install -r requirements.txt
python main.py
```

Aprire quindi `http://127.0.0.1:5000`.

## Build

La build PyInstaller deve essere eseguita sul sistema operativo di destinazione. Il workflow GitHub Actions in `.github/workflows/build.yml` crea pacchetti separati per Windows, macOS e Linux con il nome `CreaCurricoloMulti`. Su macOS il pacchetto usa il Python installato sul computer anziche' includere un runtime Python non firmato.
I pacchetti includono lo snapshot Admin memorizzato e il database Master; il database
Corrente e i file INI ricevuti non vengono distribuiti. Per pubblicare i tre ZIP,
creare un tag `v*`: il workflow verifica e prepara gli archivi prima di allegarli
alla Release GitHub.

### Avvio su macOS

Estrai lo ZIP e apri `Avvia CreaCurricolo.command`. Serve Python 3.10 o successivo.
Se non e' disponibile, il launcher apre la pagina ufficiale dei download Python:
installa il pacchetto macOS universal2 di python.org, firmato e notarizzato, quindi
riapri il launcher (l'installer potrebbe chiedere la password di amministratore).
Al primo avvio crea un ambiente virtuale e installa le
dipendenze da PyPI. Se macOS blocca il file `.command`, usa Finder per consentirne
l'apertura; il runtime Python viene invece eseguito dall'installazione ufficiale
di Python.

La generazione dei documenti Word non richiede Microsoft Office o LibreOffice.
Per esportare in PDF l'applicazione usa, in ordine, LibreOffice e Microsoft Word
(tramite `pywin32` su Windows). Se nessuno dei due e' disponibile, il documento
Word viene comunque creato e l'applicazione comunica che occorre installare
LibreOffice o Microsoft Word per completare l'esportazione PDF.

I dati creati dall'applicazione sono salvati accanto all'eseguibile nella cartella
della distribuzione: il database, le cartelle `ADMIN` e le cartelle dei docenti
vengono creati direttamente nell'AppPath. Le risorse incluse nel pacchetto non
vengono usate come archivio dei dati generati.

## Database e ripristini

L'applicazione mantiene tre archivi distinti:

- `curricolobak.db`: stato Master iniziale, usato come riferimento per il ripristino Master.
- `curricolobak-modificato.db`: stato Admin approvato, aggiornato dai comandi di memorizzazione.
- `dati/curricolo.db`: stato Corrente, usato durante il lavoro e per acquisire i file INI.

Il ripristino Master riallinea solo il database Corrente al Master e non modifica
l'archivio Admin. Il ripristino Admin riallinea solo il Corrente all'ultimo stato
Admin memorizzato. Entrambi i ripristini svuotano nel database Corrente i record
INI e le conferme dei periodi, che possono essere riacquisiti importando nuovamente
i file. Per aggiornare l'archivio Admin dopo il ripristino Master, usare in Admin
il comando di memorizzazione delle materie, dei percorsi e dei codici PECUP.

La memorizzazione PECUP aggiorna nel checkpoint Admin l'elenco dei codici e delle
descrizioni, oltre a materie e percorsi attivi; non copia le associazioni PECUP
derivate dai file INI. La memorizzazione di Educazione civica sostituisce nel
checkpoint Admin tutti i piani di corsi, classi e articolazioni, senza le conferme
di periodo provenienti dagli INI.

Nelle interfacce e nei documenti, le materie Chimica, Fisica e Scienza della Terra
e Biologia sono mostrate rispettivamente come Sc.Sp. Chimica, Sc.Sp. Fisica e
Sc.Sp. Scienza della Terra e Biologia. I nomi interni, le sigle e i dati storici
restano invariati.
