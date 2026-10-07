# Downloads Organizer

Range automatiquement le dossier Téléchargements selon des règles définies dans `config.yaml`.

## Fonctionnalités

- Rangement par extension, par nom ou par taille (ex : factures → `Admin/2026`)
- Surveillance en continu du dossier
- Doublons envoyés à la corbeille
- Annulation du dernier rangement
- Suppression automatique des vieux fichiers

## Commandes

```bash
python main.py sort --dry-run   # simulation
python main.py sort             # range une fois
python main.py watch            # range en continu
python main.py undo             # annule le dernier rangement
python main.py clean            # supprime les vieux fichiers
python main.py stats            # statistiques
```

## Lancer

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
python main.py sort --dry-run
```
