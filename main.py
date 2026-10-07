"""Rangement automatique du dossier Téléchargements.

Utilisation :
    python main.py sort             range le dossier une fois
    python main.py sort --dry-run   simulation : affiche ce qui serait fait, sans rien déplacer
    python main.py watch            range puis surveille en continu
    python main.py undo             annule le dernier rangement
    python main.py clean            envoie les vieux fichiers à la corbeille (section « cleanup »)
    python main.py stats            combien de fichiers ont été rangés, et où

Options : -c autre-config.yaml (autre fichier de règles), -v (affiche plus de détails)
"""

import argparse
import logging
import sys
from collections import Counter
from logging.handlers import RotatingFileHandler
from pathlib import Path

import organizer
from journal import Journal
from settings import ConfigError, load_config

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"


def setup_logging(log_file: Path | None, verbose: bool):
    """Affiche les messages dans la console, et les garde aussi dans un fichier si demandé."""
    handlers = []
    # Lancé sans console (pythonw, au démarrage de Windows), sys.stdout vaut None
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    if log_file is not None:
        # Fichier limité à 1 Mo ; les 3 anciennes versions sont gardées
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def read_arguments(argv):
    parser = argparse.ArgumentParser(prog="main.py", description="Range automatiquement ton dossier Téléchargements.")
    parser.add_argument("command", choices=["watch", "sort", "undo", "clean", "stats"])
    parser.add_argument("-c", "--config", type=Path, default=DEFAULT_CONFIG, help="fichier de règles YAML")
    parser.add_argument("-n", "--dry-run", action="store_true", help="simulation : ne déplace rien")
    parser.add_argument("-v", "--verbose", action="store_true", help="affiche plus de détails")
    return parser.parse_args(argv)


def show_stats(config, journal: Journal):
    moves = [entry for entry in journal.entries() if entry["action"] == "move"]
    if not moves:
        print("Aucun fichier rangé pour l'instant.")
        return

    folders = Counter()
    for entry in moves:
        folder = Path(entry["dst"]).parent
        if folder.is_relative_to(config.destination):
            folder = folder.relative_to(config.destination)
        folders[str(folder)] += 1

    print(f"{len(moves)} fichier(s) rangé(s) depuis le {moves[0]['time'][:10]} :")
    for folder, count in folders.most_common(15):
        print(f"  {count:>5}  {folder}")


def main(argv=None) -> int:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")  # accents et flèches dans la console Windows

    arguments = read_arguments(argv)
    try:
        config = load_config(arguments.config)
    except ConfigError as error:
        print(f"Erreur de configuration : {error}", file=sys.stderr)
        return 2

    # En mode surveillance, on garde aussi les messages dans organizer.log (à côté de config.yaml)
    log_file = config.journal.parent / "organizer.log" if arguments.command == "watch" else None
    setup_logging(log_file, arguments.verbose)
    journal = Journal(config.journal)
    simulation_prefix = "[simulation] " if arguments.dry_run else ""

    if arguments.command == "watch":
        organizer.watch(config, journal)

    elif arguments.command == "sort":
        outcomes = organizer.sort_folder(config, journal, dry_run=arguments.dry_run)
        moved = [outcome for outcome in outcomes if outcome.action == "moved"]
        duplicates = [outcome for outcome in outcomes if outcome.action == "duplicate"]
        print(f"{simulation_prefix}{len(moved)} fichier(s) rangé(s), {len(duplicates)} doublon(s) à la corbeille.")

    elif arguments.command == "undo":
        for line in journal.undo_last():
            print(line)

    elif arguments.command == "clean":
        trashed = organizer.clean_old_files(config, journal, dry_run=arguments.dry_run)
        print(f"{simulation_prefix}{len(trashed)} fichier(s) ancien(s) à la corbeille.")

    elif arguments.command == "stats":
        show_stats(config, journal)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
