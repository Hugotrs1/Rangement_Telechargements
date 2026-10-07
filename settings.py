"""Lecture et vérification du fichier de configuration (config.yaml)."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Téléchargements en cours et fichiers système : on n'y touche jamais
ALWAYS_IGNORED = ["*.crdownload", "*.part", "*.partial", "*.tmp", "*.download", "*.opdownload", "desktop.ini", ".*"]


class ConfigError(ValueError):
    """Le fichier de configuration contient une erreur."""


@dataclass
class Rule:
    """Une règle de rangement.

    Tous les critères renseignés doivent correspondre (ET).
    Dans une liste (extensions, motifs de nom), un seul élément suffit (OU).
    """
    name: str
    destination: str                                         # ex : « Admin/{year} »
    extensions: list[str] = field(default_factory=list)      # ex : ["pdf", "docx"]
    name_patterns: list[str] = field(default_factory=list)   # ex : ["*facture*"]
    regex: str | None = None                                 # expression régulière sur le nom
    min_size_mb: float | None = None                         # taille minimale en Mo


@dataclass
class CleanupRule:
    """Envoie à la corbeille les fichiers de `folder` plus vieux que `older_than_days` jours."""
    folder: str
    older_than_days: int


@dataclass
class Config:
    source: Path                  # dossier à ranger
    destination: Path             # racine des dossiers de rangement
    rules: list[Rule]
    ignore: list[str]             # motifs de fichiers à ne jamais déplacer
    settle_seconds: float         # temps sans changement avant de ranger un nouveau fichier
    duplicates: str               # « trash » (doublons à la corbeille) ou « keep » (renommés)
    fallback: str | None          # dossier pour les fichiers sans règle (None = on n'y touche pas)
    cleanup: list[CleanupRule]
    journal: Path                 # fichier qui garde la trace des déplacements


def to_path(text: str) -> Path:
    """« ~/Downloads » ou « %USERPROFILE%/Downloads » → chemin complet."""
    return Path(os.path.expandvars(os.path.expanduser(text))).resolve()


def as_list(value) -> list:
    """Accepte une valeur seule ou une liste dans le YAML : « pdf » ou « [pdf, docx] »."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_rule(raw_rule: dict, number: int) -> Rule:
    """Transforme une règle du YAML en objet Rule, en vérifiant qu'elle est complète."""
    name = raw_rule.get("name", f"Règle {number}")
    if "to" not in raw_rule:
        raise ConfigError(f"Règle « {name} » : la clé « to » (dossier de destination) est obligatoire.")

    match = raw_rule.get("match") or {}
    rule = Rule(
        name=name,
        destination=raw_rule["to"],
        extensions=[extension.lower().lstrip(".") for extension in as_list(match.get("extensions"))],
        name_patterns=as_list(match.get("name")),
        regex=match.get("regex"),
        min_size_mb=match.get("min_size_mb"),
    )

    if not rule.extensions and not rule.name_patterns and not rule.regex:
        raise ConfigError(f"Règle « {name} » : il faut au moins un critère (extensions, name ou regex).")
    if rule.regex:
        try:
            re.compile(rule.regex)
        except re.error as error:
            raise ConfigError(f"Règle « {name} » : expression régulière invalide ({error}).") from None
    return rule


def load_config(path: Path) -> Config:
    """Lit config.yaml. Lève ConfigError avec un message clair si quelque chose ne va pas."""
    if not path.exists():
        raise ConfigError(f"Fichier introuvable : {path}. Copie config.example.yaml en config.yaml.")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "source" not in data:
        raise ConfigError("La clé « source » (dossier à ranger) est obligatoire.")
    source = to_path(data["source"])
    destination = to_path(data.get("destination") or data["source"])

    rules = []
    for number, raw_rule in enumerate(as_list(data.get("rules")), start=1):
        rules.append(read_rule(raw_rule, number))

    duplicates = data.get("duplicates", "trash")
    if duplicates not in ("trash", "keep"):
        raise ConfigError("« duplicates » doit valoir « trash » ou « keep ».")

    cleanup = []
    for raw_cleanup in as_list(data.get("cleanup")):
        cleanup.append(CleanupRule(folder=raw_cleanup["folder"], older_than_days=int(raw_cleanup["older_than_days"])))

    # Par défaut, le journal est rangé à côté de config.yaml
    if data.get("journal"):
        journal = to_path(data["journal"])
    else:
        journal = path.resolve().parent / "journal.jsonl"

    return Config(
        source=source,
        destination=destination,
        rules=rules,
        ignore=ALWAYS_IGNORED + as_list(data.get("ignore")),
        settle_seconds=float(data.get("settle_seconds", 5)),
        duplicates=duplicates,
        fallback=data.get("fallback"),
        cleanup=cleanup,
        journal=journal,
    )
