"""Interface en ligne de commande.

    python -m organizer watch      # range puis surveille en continu
    python -m organizer sort       # range une fois et quitte
    python -m organizer sort -n    # simulation : affiche sans rien déplacer
    python -m organizer undo       # annule le dernier rangement
    python -m organizer clean      # applique les règles de nettoyage
    python -m organizer stats      # résumé du journal
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from logging.handlers import RotatingFileHandler
from pathlib import Path

from organizer.config import ConfigError, load_config
from organizer.journal import Journal
from organizer.mover import cleanup, sweep
from organizer.watcher import watch

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def setup_logging(log_file: Path | None, verbose: bool) -> None:
    # Sous pythonw (lancement au démarrage, sans console), sys.stdout vaut None.
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)] if sys.stdout else []
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # accents et flèches dans la console Windows

    parser = argparse.ArgumentParser(prog="organizer", description="Range automatiquement ton dossier Téléchargements.")
    parser.add_argument("command", choices=["watch", "sort", "undo", "clean", "stats"])
    parser.add_argument("-c", "--config", type=Path, default=DEFAULT_CONFIG, help="fichier de règles YAML")
    parser.add_argument("-n", "--dry-run", action="store_true", help="simulation : n'affiche que ce qui serait fait")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        return 2

    setup_logging(config.journal.parent / "organizer.log" if args.command == "watch" else None, args.verbose)
    journal = Journal(config.journal)

    if args.command == "watch":
        watch(config, journal)
    elif args.command == "sort":
        outcomes = sweep(config, journal, dry_run=args.dry_run)
        moved = [o for o in outcomes if o.action == "moved"]
        duplicates = [o for o in outcomes if o.action == "duplicate"]
        prefix = "[simulation] " if args.dry_run else ""
        print(f"{prefix}{len(moved)} fichier(s) rangé(s), {len(duplicates)} doublon(s) à la corbeille.")
    elif args.command == "undo":
        for line in journal.undo_last():
            print(line)
    elif args.command == "clean":
        trashed = cleanup(config, journal, dry_run=args.dry_run)
        print(f"{'[simulation] ' if args.dry_run else ''}{len(trashed)} fichier(s) ancien(s) à la corbeille.")
    elif args.command == "stats":
        entries = [e for e in journal.entries() if e["action"] == "move"]
        if not entries:
            print("Aucun fichier rangé pour l'instant.")
            return 0
        def folder_of(entry: dict) -> str:
            parent = Path(entry["dst"]).parent
            return str(parent.relative_to(config.destination)) if parent.is_relative_to(config.destination) else str(parent)

        folders = Counter(folder_of(e) for e in entries)
        print(f"{len(entries)} fichier(s) rangé(s) depuis le {entries[0]['time'][:10]} :")
        for folder, count in folders.most_common(15):
            print(f"  {count:>5}  {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
