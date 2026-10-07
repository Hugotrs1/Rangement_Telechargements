"""Chargement et validation du fichier de règles YAML."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_IGNORE = ["*.crdownload", "*.part", "*.partial", "*.tmp", "*.download", "*.opdownload", "desktop.ini", ".*"]


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    name: str
    to: str
    extensions: frozenset[str] = frozenset()
    names: tuple[str, ...] = ()
    regex: str | None = None
    min_size_mb: float | None = None


@dataclass(frozen=True)
class CleanupRule:
    folder: str
    older_than_days: int


@dataclass(frozen=True)
class Config:
    source: Path
    destination: Path
    rules: tuple[Rule, ...]
    ignore: tuple[str, ...] = tuple(DEFAULT_IGNORE)
    settle_seconds: float = 5
    duplicates: str = "trash"  # trash | keep
    fallback: str | None = None  # dossier pour les fichiers sans règle (None = on n'y touche pas)
    cleanup: tuple[CleanupRule, ...] = field(default_factory=tuple)
    journal: Path = Path()


def _path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"Fichier de configuration introuvable : {path} (copie config.example.yaml)")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "source" not in data:
        raise ConfigError("La clé « source » (dossier à ranger) est obligatoire.")
    source = _path(data["source"])
    destination = _path(data.get("destination", data["source"]))

    rules = []
    for index, raw in enumerate(_as_list(data.get("rules")), start=1):
        if "to" not in raw:
            raise ConfigError(f"Règle n°{index} : la clé « to » (destination) est obligatoire.")
        match = raw.get("match") or {}
        rule = Rule(
            name=raw.get("name", f"Règle {index}"),
            to=raw["to"],
            extensions=frozenset(e.lower().lstrip(".") for e in _as_list(match.get("extensions"))),
            names=tuple(_as_list(match.get("name"))),
            regex=match.get("regex"),
            min_size_mb=match.get("min_size_mb"),
        )
        if not (rule.extensions or rule.names or rule.regex):
            raise ConfigError(f"Règle « {rule.name} » : il faut au moins un critère (extensions, name ou regex).")
        rules.append(rule)

    duplicates = data.get("duplicates", "trash")
    if duplicates not in ("trash", "keep"):
        raise ConfigError("« duplicates » doit valoir « trash » ou « keep ».")

    cleanup = tuple(
        CleanupRule(folder=c["folder"], older_than_days=int(c["older_than_days"]))
        for c in _as_list(data.get("cleanup"))
    )

    journal = data.get("journal")
    return Config(
        source=source,
        destination=destination,
        rules=tuple(rules),
        ignore=tuple(DEFAULT_IGNORE + _as_list(data.get("ignore"))),
        settle_seconds=float(data.get("settle_seconds", 5)),
        duplicates=duplicates,
        fallback=data.get("fallback"),
        cleanup=cleanup,
        journal=_path(journal) if journal else path.resolve().parent / "journal.jsonl",
    )
