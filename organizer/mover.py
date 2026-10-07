"""Déplacement sûr d'un fichier : jamais d'écrasement, doublons détectés par empreinte SHA-256."""

from __future__ import annotations

import glob
import hashlib
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from send2trash import send2trash

from organizer.config import Config
from organizer.journal import Journal
from organizer.rules import find_destination

log = logging.getLogger(__name__)


@dataclass
class Outcome:
    action: str  # moved | duplicate | skipped
    src: Path
    dst: Path | None = None
    rule: str | None = None


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def same_content(a: Path, b: Path) -> bool:
    return a.stat().st_size == b.stat().st_size and file_hash(a) == file_hash(b)


def free_path(target: Path) -> Path:
    """« rapport.pdf » → « rapport (1).pdf », « rapport (2).pdf »… si le nom est pris."""
    if not target.exists():
        return target
    counter = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({counter}){target.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def find_duplicate(path: Path, folder: Path) -> Path | None:
    """Cherche dans `folder` un fichier identique (même nom ou variante « (n) »)."""
    if not folder.is_dir():
        return None
    size = path.stat().st_size
    for candidate in folder.glob(f"{glob.escape(path.stem)}*{glob.escape(path.suffix)}"):
        if candidate.is_file() and candidate.stat().st_size == size and same_content(path, candidate):
            return candidate
    return None


def process_file(path: Path, config: Config, journal: Journal, batch: str, dry_run: bool = False) -> Outcome:
    if not path.is_file():
        return Outcome("skipped", path)
    rule, folder = find_destination(path, config)
    if rule is None or folder is None:
        return Outcome("skipped", path)

    duplicate = find_duplicate(path, folder) if config.duplicates == "trash" else None
    if duplicate:
        if not dry_run:
            send2trash(str(path))
            journal.record(batch, "trash", path, duplicate)
        log.info("Doublon de %s → corbeille", duplicate)
        return Outcome("duplicate", path, duplicate, rule.name)

    target = free_path(folder / path.name)
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        journal.record(batch, "move", path, target)
    log.info("[%s] %s → %s", rule.name, path.name, target.parent)
    return Outcome("moved", path, target, rule.name)


def sweep(config: Config, journal: Journal, dry_run: bool = False) -> list[Outcome]:
    """Range tous les fichiers présents à la racine du dossier source (pas les sous-dossiers)."""
    batch = journal.new_batch()
    outcomes = []
    for path in sorted(config.source.iterdir()):
        try:
            outcomes.append(process_file(path, config, journal, batch, dry_run))
        except PermissionError:
            log.warning("%s est utilisé par un autre programme, on réessaiera plus tard.", path.name)
        except OSError as exc:
            log.error("Impossible de traiter %s : %s", path.name, exc)
    return outcomes


def cleanup(config: Config, journal: Journal, dry_run: bool = False) -> list[Path]:
    """Envoie à la corbeille les fichiers trop anciens des dossiers listés dans « cleanup »."""
    batch = journal.new_batch()
    trashed = []
    for rule in config.cleanup:
        folder = config.destination / rule.folder
        if not folder.is_dir():
            continue
        limit = time.time() - rule.older_than_days * 86400
        for path in folder.rglob("*"):
            if path.is_file() and path.stat().st_mtime < limit:
                if not dry_run:
                    send2trash(str(path))
                    journal.record(batch, "trash", path, None)
                log.info("Nettoyage : %s (plus de %d jours) → corbeille", path.name, rule.older_than_days)
                trashed.append(path)
    return trashed
