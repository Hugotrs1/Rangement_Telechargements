"""Surveillance en continu du dossier source.

Les navigateurs écrivent d'abord dans un fichier temporaire (.crdownload, .part…)
puis le renomment : on attend donc que le fichier final soit stable pendant
`settle_seconds` avant de le ranger.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from organizer.config import Config
from organizer.journal import Journal
from organizer.mover import cleanup, process_file, sweep

log = logging.getLogger(__name__)

FULL_SWEEP_EVERY = 15 * 60  # filet de sécurité si un événement a été manqué
CLEANUP_EVERY = 6 * 3600


class PendingFiles(FileSystemEventHandler):
    """Mémorise les fichiers touchés récemment et l'heure de leur dernier changement."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.pending: dict[Path, float] = {}
        self.lock = threading.Lock()

    def _touch(self, raw_path: str | bytes) -> None:
        path = Path(raw_path if isinstance(raw_path, str) else raw_path.decode())
        if path.parent == self.source:  # uniquement la racine, pas les sous-dossiers déjà rangés
            with self.lock:
                self.pending[path] = time.monotonic()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._touch(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._touch(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._touch(event.dest_path)

    def pop_settled(self, settle_seconds: float) -> list[Path]:
        now = time.monotonic()
        with self.lock:
            ready = [p for p, t in self.pending.items() if now - t >= settle_seconds]
            for path in ready:
                del self.pending[path]
        return ready

    def retry_later(self, path: Path) -> None:
        with self.lock:
            self.pending[path] = time.monotonic()


def watch(config: Config, journal: Journal) -> None:
    log.info("Rangement initial de %s", config.source)
    sweep(config, journal)

    handler = PendingFiles(config.source)
    observer = Observer()
    observer.schedule(handler, str(config.source), recursive=False)
    observer.start()
    log.info("Surveillance de %s (Ctrl+C pour arrêter)", config.source)

    last_sweep = last_cleanup = time.monotonic()
    try:
        while True:
            time.sleep(1)
            for path in handler.pop_settled(config.settle_seconds):
                try:
                    process_file(path, config, journal, journal.new_batch())
                except PermissionError:
                    handler.retry_later(path)  # encore ouvert par le navigateur ou un autre programme
                except OSError as exc:
                    log.error("Impossible de traiter %s : %s", path.name, exc)

            now = time.monotonic()
            if now - last_sweep > FULL_SWEEP_EVERY:
                sweep(config, journal)
                last_sweep = now
            if config.cleanup and now - last_cleanup > CLEANUP_EVERY:
                cleanup(config, journal)
                last_cleanup = now
    except KeyboardInterrupt:
        log.info("Arrêt demandé.")
    finally:
        observer.stop()
        observer.join()
