"""Range le dossier Téléchargements selon les règles de config.yaml."""

import fnmatch
import hashlib
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import yaml
from send2trash import send2trash

HERE = Path(__file__).parent
CONFIG_FILE = HERE / "config.yaml"
JOURNAL = HERE / "journal.jsonl"  # historique des déplacements, pour pouvoir annuler
LOG_FILE = HERE / "organizer.log"

# Téléchargements en cours et fichiers système : on n'y touche jamais
ALWAYS_IGNORED = ["*.crdownload", "*.part", "*.tmp", "*.download", "desktop.ini", ".*"]


def load_config(path=CONFIG_FILE):
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config["source"] = Path(config["source"]).expanduser()
    config["destination"] = Path(config.get("destination") or config["source"]).expanduser()
    for key in ("rules", "ignore", "cleanup"):
        config[key] = config.get(key) or []
    return config


# --- Où ranger un fichier ? -------------------------------------------------------

def find_folder(file, config):
    """Dossier où ranger le fichier, ou None s'il doit rester où il est.
    Les règles sont testées dans l'ordre : la première qui correspond gagne."""
    name = file.name.lower()
    if any(fnmatch.fnmatch(name, pattern) for pattern in ALWAYS_IGNORED + config["ignore"]):
        return None

    extension = file.suffix.lower().lstrip(".")
    for rule in config["rules"]:
        match = rule["match"]
        if "extensions" in match and extension not in match["extensions"]:
            continue
        if "name" in match and not any(fnmatch.fnmatch(name, pattern.lower()) for pattern in match["name"]):
            continue
        date = datetime.fromtimestamp(file.stat().st_mtime)
        return config["destination"] / rule["to"].format(year=date.year, month=f"{date.month:02d}")

    if config.get("fallback"):  # dossier pour les fichiers qu'aucune règle ne concerne
        return config["destination"] / config["fallback"]
    return None


# --- Déplacer un fichier sans rien abîmer -------------------------------------------

def file_hash(file):
    """Empreinte du contenu : deux fichiers identiques ont la même."""
    with open(file, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def find_duplicate(file, folder):
    """Un fichier au contenu identique existe-t-il déjà dans ce dossier ?"""
    if not folder.is_dir():
        return None
    for other in folder.iterdir():
        # On compare d'abord la taille (rapide), puis le contenu seulement si besoin
        if other != file and other.is_file() and other.stat().st_size == file.stat().st_size and file_hash(other) == file_hash(file):
            return other
    return None


def free_name(target):
    """« photo.jpg » est déjà pris ? → « photo (1).jpg », puis « photo (2).jpg »…"""
    candidate, number = target, 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem} ({number}){target.suffix}")
        number += 1
    return candidate


def tidy_file(file, config, run_id, test=False):
    """Range un fichier. Renvoie une phrase qui décrit ce qui a été fait (None si rien)."""
    folder = find_folder(file, config)
    if folder is None:
        return None

    duplicate = find_duplicate(file, folder)
    if duplicate:
        if not test:
            send2trash(str(file))
            write_journal(run_id, file, None)
        return f"🗑️  {file.name} : déjà présent ({duplicate.name}), envoyé à la corbeille"

    target = free_name(folder / file.name)
    if not test:
        folder.mkdir(parents=True, exist_ok=True)
        shutil.move(file, target)
        write_journal(run_id, file, target)
    return f"📁 {file.name} → {target.parent.relative_to(config['destination'])}"


def tidy_folder(config, test=False):
    """Range tous les fichiers du dossier source (sans toucher aux sous-dossiers)."""
    run_id = datetime.now().isoformat()
    messages = []
    for file in sorted(config["source"].iterdir()):
        if not file.is_file():
            continue
        try:
            message = tidy_file(file, config, run_id, test)
        except PermissionError:
            message = f"⏳ {file.name} est encore ouvert par un programme, ignoré pour l'instant"
        if message:
            messages.append(message)
    return messages


def clean_old_files(config, test=False):
    """Envoie à la corbeille les fichiers trop vieux des dossiers listés dans « cleanup »."""
    run_id = datetime.now().isoformat()
    messages = []
    for rule in config["cleanup"]:
        too_old = time.time() - rule["older_than_days"] * 24 * 3600
        folder = config["destination"] / rule["folder"]
        for file in folder.glob("*"):
            if file.is_file() and file.stat().st_mtime < too_old:
                if not test:
                    send2trash(str(file))
                    write_journal(run_id, file, None)
                messages.append(f"🧹 {file.name} (plus de {rule['older_than_days']} jours) → corbeille")
    return messages


# --- Journal et annulation -------------------------------------------------------------

def write_journal(run_id, source, target):
    """Note chaque déplacement. target = None : le fichier est parti à la corbeille."""
    entry = {"run": run_id, "from": str(source), "to": str(target) if target else None}
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_journal():
    if not JOURNAL.exists():
        return []
    return [json.loads(line) for line in JOURNAL.read_text(encoding="utf-8").splitlines() if line]


def undo_last_run():
    """Remet à leur place les fichiers du dernier rangement."""
    entries = read_journal()
    if not entries:
        return ["Rien à annuler."]

    last_run = entries[-1]["run"]
    messages = []
    for entry in reversed([e for e in entries if e["run"] == last_run]):
        source, target = Path(entry["from"]), entry["to"] and Path(entry["to"])
        if target is None:
            messages.append(f"⚠️  {source.name} est dans la corbeille : restaure-le depuis la corbeille.")
        elif not target.exists() or source.exists():
            messages.append(f"⚠️  {source.name} : impossible de le remettre en place, ignoré.")
        else:
            shutil.move(target, source)
            messages.append(f"↩️  {source.name} remis à sa place")

    remaining = [e for e in entries if e["run"] != last_run]
    JOURNAL.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in remaining), encoding="utf-8")
    return messages


# --- Mode surveillance --------------------------------------------------------------------

def report(message):
    """Affiche un message et le garde dans organizer.log."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def watch(config, check_every=5):
    """Range les nouveaux fichiers au fur et à mesure.

    Un fichier n'est rangé que si sa taille n'a pas changé entre deux passages :
    sinon, c'est qu'il est encore en train d'être téléchargé.
    """
    report(f"👀 Surveillance de {config['source']}")
    previous = {}  # {fichier: (taille, date de modification)} au passage précédent
    last_cleanup = 0

    while True:
        current = {}
        for file in config["source"].iterdir():
            try:
                stats = file.stat()
            except FileNotFoundError:  # supprimé entre-temps
                continue
            if not file.is_file():
                continue
            state = (stats.st_size, stats.st_mtime)
            if previous.get(file) == state:
                try:
                    if message := tidy_file(file, config, datetime.now().isoformat()):
                        report(message)
                except PermissionError:
                    pass  # encore ouvert : on réessaiera au prochain passage
            current[file] = state
        previous = current

        if time.time() - last_cleanup > 6 * 3600:  # nettoyage toutes les 6 heures
            for message in clean_old_files(config):
                report(message)
            last_cleanup = time.time()

        time.sleep(check_every)
