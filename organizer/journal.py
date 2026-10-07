"""Journal des déplacements (JSON Lines) : permet d'annuler le dernier rangement."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def new_batch() -> str:
        return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"

    def record(self, batch: str, action: str, src: Path, dst: Path | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "batch": batch,
            "action": action,
            "src": str(src),
            "dst": str(dst) if dst else None,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def last_batch(self) -> tuple[str | None, list[dict]]:
        """Dernier lot de déplacements qui n'a pas encore été annulé."""
        entries = self.entries()
        undone = {e["batch"] for e in entries if e["action"] == "undo"}
        batches = [e["batch"] for e in entries if e["action"] != "undo" and e["batch"] not in undone]
        if not batches:
            return None, []
        batch = batches[-1]
        return batch, [e for e in entries if e["batch"] == batch]

    def undo_last(self) -> list[str]:
        """Remet les fichiers du dernier lot à leur place d'origine. Renvoie un compte rendu ligne par ligne."""
        batch, entries = self.last_batch()
        if batch is None:
            return ["Rien à annuler."]

        report = []
        for entry in reversed(entries):
            src, dst = Path(entry["src"]), Path(entry["dst"]) if entry["dst"] else None
            if entry["action"] == "trash":
                report.append(f"⚠ {src.name} : envoyé à la corbeille, à restaurer depuis la corbeille.")
            elif dst is None or not dst.exists():
                report.append(f"⚠ {src.name} : introuvable à {dst}, ignoré.")
            elif src.exists():
                report.append(f"⚠ {src.name} : un fichier existe déjà à l'emplacement d'origine, ignoré.")
            else:
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                report.append(f"↩ {dst.name} → {src.parent}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "batch": batch, "action": "undo"}) + "\n")
        return report
