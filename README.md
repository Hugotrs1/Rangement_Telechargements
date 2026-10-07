# 🗂️ Downloads Organizer

Range automatiquement mon dossier **Téléchargements** : factures dans `Admin/2026`,
captures d'écran classées par mois, images, vidéos, archives… selon des règles simples écrites
dans un fichier YAML. Il tourne en fond sous Windows, et chaque rangement peut être annulé.

![Python](https://img.shields.io/badge/python-3.12-blue)

## Ce qu'il fait

- 📏 Range les fichiers selon leurs **extensions** et leur **nom** (`*facture*`), la première règle qui correspond gagne.
- 👀 **Surveille** le dossier en continu et attend la fin d'un téléchargement avant de déplacer le fichier.
- 🧬 Repère les **doublons** (même contenu) et les envoie à la corbeille.
- 🚫 N'écrase **jamais** un fichier : en cas de nom déjà pris, il devient `photo (1).jpg`.
- ↩️ **Annule** le dernier rangement en une commande.
- 🧹 Envoie à la corbeille les vieux installateurs (après 30 jours, réglable).

## Utilisation

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy config.example.yaml config.yaml          # puis adapte les règles

.venv\Scripts\python main.py sort --test      # simulation : montre ce qui serait fait
.venv\Scripts\python main.py sort             # range une fois
.venv\Scripts\python main.py watch            # range en continu
.venv\Scripts\python main.py undo             # annule le dernier rangement
.venv\Scripts\python main.py clean            # supprime les vieux fichiers (corbeille)
.venv\Scripts\python main.py stats            # ce qui a été rangé, et où
```

Pour qu'il démarre tout seul avec Windows :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-startup.ps1
```

## Écrire une règle

```yaml
rules:
  - name: Factures
    match:
      name: ["*facture*", "*invoice*"]   # le nom doit ressembler à un de ces motifs…
      extensions: [pdf]                   # …et l'extension doit être dans cette liste
    to: Admin/{year}                      # {year} et {month} = date du fichier
```

## Organisation du code

```
main.py          les commandes (sort, watch, undo…)
organizer.py     toute la logique : règles, déplacement, doublons, journal, surveillance
config.example.yaml
tests/
```
