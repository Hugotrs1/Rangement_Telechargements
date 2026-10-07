"""Choix de la destination d'un fichier selon les règles (la première qui correspond gagne)."""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime
from pathlib import Path

from organizer.config import Config, Rule


def is_ignored(path: Path, config: Config) -> bool:
    name = path.name.lower()
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in config.ignore)


def matches(path: Path, rule: Rule, size: int | None = None) -> bool:
    """Tous les critères renseignés doivent correspondre (ET) ; dans une liste, un seul suffit (OU)."""
    name = path.name.lower()
    if rule.extensions and path.suffix.lower().lstrip(".") not in rule.extensions:
        return False
    if rule.names and not any(fnmatch.fnmatch(name, pattern.lower()) for pattern in rule.names):
        return False
    if rule.regex and not re.search(rule.regex, path.name, re.IGNORECASE):
        return False
    if rule.min_size_mb is not None:
        size = path.stat().st_size if size is None else size
        if size < rule.min_size_mb * 1024 * 1024:
            return False
    return True


def render_destination(template: str, path: Path, when: datetime) -> str:
    """Remplace {year}, {month}, {day} et {ext} dans le chemin de destination."""
    return template.format(
        year=f"{when.year:04d}",
        month=f"{when.month:02d}",
        day=f"{when.day:02d}",
        ext=path.suffix.lower().lstrip(".") or "sans-extension",
    )


def find_destination(path: Path, config: Config) -> tuple[Rule | None, Path | None]:
    """Renvoie (règle appliquée, dossier de destination), ou (None, None) si le fichier reste en place."""
    if is_ignored(path, config):
        return None, None
    when = datetime.fromtimestamp(path.stat().st_mtime)
    for rule in config.rules:
        if matches(path, rule):
            return rule, config.destination / render_destination(rule.to, path, when)
    if config.fallback:
        fallback = Rule(name="Par défaut", to=config.fallback, names=("*",))
        return fallback, config.destination / render_destination(config.fallback, path, when)
    return None, None
