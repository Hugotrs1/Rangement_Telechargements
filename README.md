# 🗂️ Downloads Organizer

Range automatiquement le dossier **Téléchargements** selon des règles écrites en YAML :
factures dans `Admin/2026`, captures d'écran par mois, installateurs supprimés au bout de 30 jours…
Tourne en tâche de fond sous Windows, et chaque rangement peut être **annulé**.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Windows](https://img.shields.io/badge/Windows-%7C%20Linux%20%7C%20macOS-lightgrey)

## Fonctionnalités

- 👀 **Surveillance en temps réel** (watchdog) : un fichier téléchargé est rangé quelques secondes après la fin du téléchargement.
- ⏳ **Téléchargements en cours ignorés** (`.crdownload`, `.part`…) : on attend que le fichier soit stable avant d'y toucher.
- 📏 **Règles flexibles** : extensions, motifs de nom (`*facture*`), expressions régulières, taille minimale, et variables de date dans la destination (`Images/Captures/{year}-{month}`).
- 🧬 **Doublons détectés par empreinte SHA-256** : un fichier identique à un fichier déjà rangé part à la corbeille au lieu de créer `photo (1).jpg`.
- 🚫 **Jamais d'écrasement** : en cas de conflit de nom, le fichier est renommé `nom (1).ext`.
- ↩️ **Annulation** : chaque déplacement est journalisé (JSON Lines), `undo` remet le dernier lot en place.
- 🧹 **Nettoyage** : envoie à la corbeille (récupérable) les vieux fichiers de certains dossiers.
- 🧪 **Mode simulation** (`--dry-run`) pour vérifier ses règles sans rien déplacer.

## Installation

```powershell
git clone https://github.com/<toi>/downloads-organizer
cd downloads-organizer
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy config.example.yaml config.yaml     # puis adapte les règles
```

## Utilisation

```powershell
.venv\Scripts\python -m organizer sort --dry-run   # simulation : affiche ce qui serait fait
.venv\Scripts\python -m organizer sort             # range une fois
.venv\Scripts\python -m organizer watch            # range puis surveille en continu
.venv\Scripts\python -m organizer undo             # annule le dernier rangement
.venv\Scripts\python -m organizer clean            # nettoyage des vieux fichiers
.venv\Scripts\python -m organizer stats            # combien de fichiers rangés et où
```

### Lancement automatique au démarrage de Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1              # installe
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall   # désinstalle
```

Le script crée un raccourci dans le dossier *Démarrage* qui lance `pythonw -m organizer watch` (sans fenêtre).
Les logs sont écrits dans `organizer.log`, à côté de `config.yaml`.

## Écrire ses règles

```yaml
rules:
  - name: Factures
    match:
      name: ["*facture*", "*invoice*"]   # un des motifs suffit
      extensions: [pdf]                   # ET l'extension doit correspondre
    to: Admin/{year}

  - name: Gros fichiers vidéo
    match:
      extensions: [mp4, mkv]
      min_size_mb: 500
    to: Vidéos/Gros
```

- Les règles sont testées **dans l'ordre**, la première qui correspond gagne : mets les plus précises en haut.
- Variables disponibles dans `to` : `{year}`, `{month}`, `{day}` (date du fichier), `{ext}`.
- `fallback: Divers` range aussi les fichiers qui ne correspondent à aucune règle.

## Tests

```powershell
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\ruff check .
.venv\Scripts\pytest
```

La CI GitHub Actions exécute les tests sous Ubuntu **et** Windows.

## Structure

```
organizer/
├── __main__.py   # interface en ligne de commande
├── config.py     # lecture et validation du YAML
├── rules.py      # choix de la destination
├── mover.py      # déplacement sûr, doublons, nettoyage
├── journal.py    # journal des déplacements et annulation
└── watcher.py    # surveillance en temps réel
```
