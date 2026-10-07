"""Le cœur du rangement : choisir la destination d'un fichier et l'y déplacer sans rien abîmer."""

import fnmatch
import hashlib
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from send2trash import send2trash

from journal import Journal
from settings import Config, Rule

log = logging.getLogger("organizer")

CLEANUP_EVERY_SECONDS = 6 * 3600  # en mode surveillance, nettoyage toutes les 6 heures


@dataclass
class Outcome:
    """Ce qui est arrivé à un fichier."""
    action: str                     # « moved » (rangé), « duplicate » (doublon à la corbeille) ou « skipped »
    file: Path
    destination: Path | None = None
    rule_name: str | None = None


# --- 1. Choisir la destination ------------------------------------------------------------------

def is_ignored(file: Path, config: Config) -> bool:
    name = file.name.lower()
    for pattern in config.ignore:
        if fnmatch.fnmatch(name, pattern.lower()):
            return True
    return False


def rule_matches(rule: Rule, file: Path) -> bool:
    """Vrai si le fichier correspond à TOUS les critères renseignés dans la règle."""
    name = file.name.lower()
    extension = file.suffix.lower().lstrip(".")  # « Photo.JPG » → « jpg »

    if rule.extensions and extension not in rule.extensions:
        return False

    if rule.name_patterns:
        # fnmatch compare avec des jokers : « *facture* » = « contient facture »
        matches_a_pattern = any(fnmatch.fnmatch(name, pattern.lower()) for pattern in rule.name_patterns)
        if not matches_a_pattern:
            return False

    if rule.regex and not re.search(rule.regex, file.name, re.IGNORECASE):
        return False

    if rule.min_size_mb is not None:
        size_in_mb = file.stat().st_size / (1024 * 1024)
        if size_in_mb < rule.min_size_mb:
            return False

    return True


def fill_placeholders(destination: str, file: Path) -> str:
    """Remplace {year}, {month}, {day} et {ext} dans le dossier de destination.

    La date utilisée est celle de la dernière modification du fichier (≈ date du téléchargement).
    Exemple : « Images/{year}-{month} » → « Images/2026-10 »
    """
    modified = datetime.fromtimestamp(file.stat().st_mtime)
    extension = file.suffix.lower().lstrip(".") or "sans-extension"
    return destination.format(
        year=f"{modified.year:04d}",
        month=f"{modified.month:02d}",
        day=f"{modified.day:02d}",
        ext=extension,
    )


def find_destination(file: Path, config: Config) -> tuple[str | None, Path | None]:
    """Renvoie (nom de la règle appliquée, dossier de destination), ou (None, None) si le fichier reste en place.

    Les règles sont testées dans l'ordre : la première qui correspond gagne.
    """
    if is_ignored(file, config):
        return None, None

    for rule in config.rules:
        if rule_matches(rule, file):
            return rule.name, config.destination / fill_placeholders(rule.destination, file)

    if config.fallback:
        return "Par défaut", config.destination / fill_placeholders(config.fallback, file)
    return None, None


# --- 2. Doublons et conflits de noms ------------------------------------------------------------

def file_fingerprint(file: Path) -> str:
    """Empreinte SHA-256 du contenu : deux fichiers identiques ont la même empreinte.

    Le fichier est lu par morceaux de 1 Mo pour ne pas charger une grosse vidéo d'un coup en mémoire.
    """
    digest = hashlib.sha256()
    with file.open("rb") as opened_file:
        while True:
            chunk = opened_file.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate(file: Path, folder: Path) -> Path | None:
    """Cherche dans `folder` un fichier au contenu identique à `file`."""
    if not folder.is_dir():
        return None
    file_size = file.stat().st_size
    for other in folder.iterdir():
        if other == file or not other.is_file():
            continue
        # Comparer la taille est très rapide : on ne calcule l'empreinte que si elle est identique
        if other.stat().st_size != file_size:
            continue
        if file_fingerprint(other) == file_fingerprint(file):
            return other
    return None


def free_name(target: Path) -> Path:
    """Si « photo.jpg » est déjà pris, renvoie « photo (1).jpg », puis « photo (2).jpg »…"""
    candidate = target
    number = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem} ({number}){target.suffix}")
        number += 1
    return candidate


# --- 3. Ranger ----------------------------------------------------------------------------------

def process_file(file: Path, config: Config, journal: Journal, batch: str, dry_run: bool = False) -> Outcome:
    """Range un fichier. En mode dry_run (simulation), rien n'est déplacé."""
    if not file.is_file():
        return Outcome("skipped", file)

    rule_name, folder = find_destination(file, config)
    if folder is None:
        return Outcome("skipped", file)

    # Doublon exact d'un fichier déjà rangé : à la corbeille (récupérable) plutôt qu'en double
    if config.duplicates == "trash":
        duplicate = find_duplicate(file, folder)
        if duplicate is not None:
            if not dry_run:
                send2trash(str(file))
                journal.record(batch, "trash", file, duplicate)
            log.info("Doublon de %s → corbeille", duplicate.name)
            return Outcome("duplicate", file, duplicate, rule_name)

    target = free_name(folder / file.name)
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file), str(target))
        journal.record(batch, "move", file, target)
    log.info("[%s] %s → %s", rule_name, file.name, target.parent)
    return Outcome("moved", file, target, rule_name)


def sort_folder(config: Config, journal: Journal, dry_run: bool = False) -> list[Outcome]:
    """Range tous les fichiers à la racine du dossier source (les sous-dossiers ne sont pas touchés)."""
    batch = journal.new_batch()
    outcomes = []
    for file in sorted(config.source.iterdir()):
        try:
            outcomes.append(process_file(file, config, journal, batch, dry_run))
        except PermissionError:
            log.warning("%s est utilisé par un autre programme, on réessaiera plus tard.", file.name)
        except OSError as error:
            log.error("Impossible de traiter %s : %s", file.name, error)
    return outcomes


def clean_old_files(config: Config, journal: Journal, dry_run: bool = False) -> list[Path]:
    """Envoie à la corbeille les fichiers trop anciens des dossiers listés dans « cleanup »."""
    batch = journal.new_batch()
    trashed = []
    for cleanup_rule in config.cleanup:
        folder = config.destination / cleanup_rule.folder
        if not folder.is_dir():
            continue
        oldest_allowed = time.time() - cleanup_rule.older_than_days * 24 * 3600
        for file in folder.rglob("*"):  # rglob : aussi dans les sous-dossiers
            if file.is_file() and file.stat().st_mtime < oldest_allowed:
                if not dry_run:
                    send2trash(str(file))
                    journal.record(batch, "trash", file, None)
                log.info("Nettoyage : %s (plus de %d jours) → corbeille", file.name, cleanup_rule.older_than_days)
                trashed.append(file)
    return trashed


# --- 4. Surveillance en continu ------------------------------------------------------------------

def watch(config: Config, journal: Journal):
    """Range les nouveaux fichiers au fur et à mesure qu'ils arrivent.

    Les navigateurs écrivent d'abord dans un fichier temporaire (.crdownload…) puis le renomment.
    Pour ne pas déplacer un fichier en cours d'écriture, on ne range un fichier que si sa taille
    et sa date n'ont pas changé depuis le passage précédent (settle_seconds plus tôt).
    """
    log.info("Surveillance de %s (Ctrl+C pour arrêter)", config.source)
    previous_states = {}  # {fichier: (taille, date de modification)} vus au passage précédent
    last_cleanup = 0.0

    try:
        while True:
            current_states = {}
            for file in config.source.iterdir():
                try:
                    stats = file.stat()
                except FileNotFoundError:
                    continue  # supprimé entre-temps
                if not file.is_file():
                    continue

                state = (stats.st_size, stats.st_mtime)
                current_states[file] = state
                if previous_states.get(file) != state:
                    continue  # nouveau ou encore en train de changer : on attend le prochain passage

                try:
                    process_file(file, config, journal, journal.new_batch())
                except PermissionError:
                    pass  # encore ouvert par un programme : on réessaiera au prochain passage
                except OSError as error:
                    log.error("Impossible de traiter %s : %s", file.name, error)

            previous_states = current_states

            if config.cleanup and time.time() - last_cleanup > CLEANUP_EVERY_SECONDS:
                clean_old_files(config, journal)
                last_cleanup = time.time()

            time.sleep(config.settle_seconds)
    except KeyboardInterrupt:
        log.info("Arrêt demandé.")
