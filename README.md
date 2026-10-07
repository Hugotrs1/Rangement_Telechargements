# 🗂️ Downloads Organizer

Range automatiquement mon dossier **Téléchargements** selon des règles écrites en YAML :
factures dans `Admin/2026`, captures d'écran par mois, installateurs supprimés au bout de 30 jours…
Il tourne en fond sous Windows, et chaque rangement peut être **annulé**.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Windows](https://img.shields.io/badge/Windows-%7C%20Linux%20%7C%20macOS-lightgrey)

## Fonctionnalités

- 👀 **Surveillance en continu** : un fichier téléchargé est rangé quelques secondes après la fin du téléchargement.
- ⏳ **Téléchargements en cours ignorés** (`.crdownload`, `.part`…) : on attend que le fichier ne bouge plus.
- 📏 **Règles flexibles** : extensions, motifs de nom (`*facture*`), expressions régulières, taille minimale,
  et variables de date dans la destination (`Images/Captures/{year}-{month}`).
- 🧬 **Doublons détectés par empreinte SHA-256** : un fichier identique à un fichier déjà rangé part à la corbeille
  (ou est gardé et renommé, au choix).
- 🚫 **Jamais d'écrasement** : en cas de conflit de nom, le fichier devient `nom (1).ext`.
- ↩️ **Annulation** : chaque déplacement est noté dans un journal, `undo` remet le dernier rangement en place.
- 🧹 **Nettoyage** : envoie à la corbeille (récupérable) les vieux fichiers de certains dossiers.
- 🧪 **Mode simulation** (`--dry-run`) pour vérifier ses règles sans rien déplacer.
- ✅ **Configuration vérifiée** au démarrage, avec des messages d'erreur clairs.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy config.example.yaml config.yaml     # puis adapte les règles
```

## Utilisation

```powershell
.venv\Scripts\python main.py sort --dry-run   # simulation : affiche ce qui serait fait
.venv\Scripts\python main.py sort             # range une fois
.venv\Scripts\python main.py watch            # range puis surveille en continu
.venv\Scripts\python main.py undo             # annule le dernier rangement
.venv\Scripts\python main.py clean            # nettoyage des vieux fichiers
.venv\Scripts\python main.py stats            # combien de fichiers rangés, et où
```

Options : `-c autre-config.yaml` pour utiliser un autre fichier de règles, `-v` pour plus de détails.

Lancement automatique au démarrage de Windows (sans fenêtre, messages dans `organizer.log`) :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1              # installe
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1 -Uninstall   # désinstalle
```

## Écrire ses règles

```yaml
rules:
  - name: Factures
    match:
      name: ["*facture*", "*invoice*"]   # un des motifs suffit…
      extensions: [pdf]                   # …ET l'extension doit correspondre
    to: Admin/{year}

  - name: Gros enregistrements vidéo
    match:
      regex: "^\\d{4}-\\d{2}-\\d{2}"      # nom qui commence par une date
      extensions: [mkv, mp4]
      min_size_mb: 500
    to: Vidéos/{year}-{month}-{day}
```

- Les règles sont testées **dans l'ordre**, la première qui correspond gagne : mets les plus précises en haut.
- Variables disponibles dans `to` : `{year}`, `{month}`, `{day}` (date du fichier), `{ext}`.
- `fallback: Divers` range aussi les fichiers qui ne correspondent à aucune règle.

## Organisation du code

```
main.py          les commandes (sort, watch, undo, clean, stats)
settings.py      lecture et vérification de config.yaml
organizer.py     choisir la destination, gérer les doublons, déplacer, surveiller
journal.py       garder la trace des déplacements et les annuler
tests/
```

## Tests

```powershell
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\ruff check .
.venv\Scripts\pytest
```

La CI GitHub Actions exécute les tests sous Ubuntu **et** Windows.
