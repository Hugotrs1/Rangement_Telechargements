"""Journal des déplacements, pour pouvoir annuler le dernier rangement.

Chaque ligne du fichier est un petit objet JSON (format « JSON Lines ») :
    {"time": "...", "batch": "20261007-154200-a1b2c3", "action": "move", "src": "...", "dst": "..."}

- batch  : identifiant du rangement (tous les fichiers rangés en une fois ont le même) ;
- action : « move » (déplacé), « trash » (envoyé à la corbeille) ou « undo » (rangement annulé).
"""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


class Journal:
    def __init__(self, path: Path):
        self.path = path

    @staticmethod
    def new_batch() -> str:
        """Nouvel identifiant de rangement : date + quelques caractères au hasard."""
        return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"

    def record(self, batch: str, action: str, source: Path, destination: Path | None):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "batch": batch,
            "action": action,
            "src": str(source),
            "dst": str(destination) if destination else None,
        }
        self.append(entry)

    def append(self, entry: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self) -> list[dict]:
        """Toutes les lignes du journal, de la plus ancienne à la plus récente."""
        if not self.path.exists():
            return []
        entries = []
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def last_batch(self) -> tuple[str | None, list[dict]]:
        """Le dernier rangement qui n'a pas encore été annulé : (identifiant, ses lignes)."""
        entries = self.entries()
        cancelled_batches = {entry["batch"] for entry in entries if entry["action"] == "undo"}

        last_batch = None
        for entry in entries:
            if entry["action"] != "undo" and entry["batch"] not in cancelled_batches:
                last_batch = entry["batch"]
        if last_batch is None:
            return None, []

        batch_entries = [entry for entry in entries if entry["batch"] == last_batch]
        return last_batch, batch_entries

    def undo_last(self) -> list[str]:
        """Remet les fichiers du dernier rangement à leur place. Renvoie un compte rendu ligne par ligne."""
        batch, entries = self.last_batch()
        if batch is None:
            return ["Rien à annuler."]

        report = []
        # On annule dans l'ordre inverse, du dernier fichier déplacé au premier
        for entry in reversed(entries):
            source = Path(entry["src"])
            destination = Path(entry["dst"]) if entry["dst"] else None

            if entry["action"] == "trash":
                report.append(f"⚠ {source.name} : envoyé à la corbeille, à restaurer depuis la corbeille.")
            elif destination is None or not destination.exists():
                report.append(f"⚠ {source.name} : introuvable à {destination}, ignoré.")
            elif source.exists():
                report.append(f"⚠ {source.name} : un fichier existe déjà à l'emplacement d'origine, ignoré.")
            else:
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
                report.append(f"↩ {destination.name} → {source.parent}")

        # On note l'annulation, pour que le prochain « undo » passe au rangement précédent
        self.append({"time": datetime.now().isoformat(timespec="seconds"), "batch": batch, "action": "undo"})
        return report
