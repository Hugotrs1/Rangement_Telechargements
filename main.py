"""Rangement automatique du dossier Téléchargements.

    python main.py sort          range le dossier une fois
    python main.py sort --test   simulation : affiche ce qui serait fait, sans rien déplacer
    python main.py watch         range en continu (à laisser tourner)
    python main.py undo          annule le dernier rangement
    python main.py clean         envoie les vieux fichiers à la corbeille (voir « cleanup »)
    python main.py stats         combien de fichiers ont été rangés, et où
"""

import sys
from collections import Counter
from pathlib import Path

import organizer


def main():
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8")  # pour les accents et emojis dans la console Windows

    command = sys.argv[1] if len(sys.argv) > 1 else ""
    test = "--test" in sys.argv

    if not organizer.CONFIG_FILE.exists():
        sys.exit("config.yaml introuvable : copie config.example.yaml en config.yaml et adapte-le.")
    config = organizer.load_config()

    if command == "sort":
        messages = organizer.tidy_folder(config, test)
        print("\n".join(messages) or "Rien à ranger.")
        if test:
            print("\n(simulation : rien n'a été déplacé)")
    elif command == "watch":
        organizer.watch(config)
    elif command == "undo":
        print("\n".join(organizer.undo_last_run()))
    elif command == "clean":
        print("\n".join(organizer.clean_old_files(config, test)) or "Rien à nettoyer.")
    elif command == "stats":
        moves = [entry for entry in organizer.read_journal() if entry["to"]]
        folders = Counter(str(Path(entry["to"]).parent) for entry in moves)
        print(f"{len(moves)} fichier(s) rangé(s) :")
        for folder, count in folders.most_common():
            print(f"  {count:>4}  {folder}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
