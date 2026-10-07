import os
import time
from pathlib import Path

import pytest

from organizer.config import ConfigError, load_config
from organizer.journal import Journal
from organizer.mover import cleanup, free_path, sweep
from organizer.rules import find_destination

CONFIG = """
source: {src}
destination: {src}
duplicates: trash
rules:
  - name: Factures
    match:
      name: ["*facture*"]
      extensions: [pdf]
    to: Admin/{{year}}
  - name: Images
    match: {{ extensions: [jpg, png] }}
    to: Images
  - name: PDF
    match: {{ extensions: [pdf] }}
    to: Documents/PDF
  - name: Gros fichiers
    match: {{ regex: "^video", min_size_mb: 0.001 }}
    to: Gros
cleanup:
  - folder: Installateurs
    older_than_days: 30
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    src = tmp_path / "Downloads"
    src.mkdir()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG.format(src=src.as_posix()), encoding="utf-8")
    trashed = []
    monkeypatch.setattr("organizer.mover.send2trash", lambda p: (trashed.append(Path(p)), os.remove(p)))
    config = load_config(config_file)
    return config, Journal(config.journal), src, trashed


def write(path: Path, content: bytes = b"data") -> Path:
    path.write_bytes(content)
    return path


def test_rules_first_match_wins(env):
    config, _, src, _ = env
    facture = write(src / "Facture-EDF.PDF")
    year = time.localtime(facture.stat().st_mtime).tm_year
    assert find_destination(facture, config)[1] == src / "Admin" / str(year)
    assert find_destination(write(src / "cours.pdf"), config)[1] == src / "Documents" / "PDF"
    assert find_destination(write(src / "photo.JPG"), config)[1] == src / "Images"
    assert find_destination(write(src / "notes.txt"), config) == (None, None)


def test_ignores_partial_downloads(env):
    config, _, src, _ = env
    assert find_destination(write(src / "film.mp4.crdownload"), config) == (None, None)


def test_size_criterion(env):
    config, _, src, _ = env
    assert find_destination(write(src / "video-petite.bin", b"x"), config) == (None, None)
    assert find_destination(write(src / "video-grosse.bin", b"x" * 2048), config)[1] == src / "Gros"


def test_sweep_moves_renames_and_dedupes(env):
    config, journal, src, trashed = env
    (src / "Images").mkdir()
    write(src / "Images" / "a.png", b"original")
    write(src / "a.png", b"original")  # doublon exact → corbeille
    write(src / "b.png", b"one")
    write(src / "Images" / "b.png", b"other")  # même nom, contenu différent → renommé

    outcomes = sweep(config, journal)
    actions = sorted((o.src.name, o.action) for o in outcomes if o.action != "skipped")
    assert actions == [("a.png", "duplicate"), ("b.png", "moved")]
    assert trashed == [src / "a.png"]
    assert (src / "Images" / "b (1).png").read_bytes() == b"one"
    assert not (src / "b.png").exists()


def test_dry_run_changes_nothing(env):
    config, journal, src, _ = env
    write(src / "photo.png")
    outcomes = sweep(config, journal, dry_run=True)
    assert outcomes[0].action == "moved"
    assert (src / "photo.png").exists()
    assert journal.entries() == []


def test_undo_restores_last_batch(env):
    config, journal, src, _ = env
    write(src / "photo.png")
    write(src / "cours.pdf")
    sweep(config, journal)
    assert not (src / "photo.png").exists()

    report = journal.undo_last()
    assert len(report) == 2
    assert (src / "photo.png").exists() and (src / "cours.pdf").exists()
    assert journal.undo_last() == ["Rien à annuler."]


def test_cleanup_old_files(env):
    config, journal, src, trashed = env
    folder = src / "Installateurs"
    folder.mkdir()
    old = write(folder / "vieux.exe")
    recent = write(folder / "recent.exe")
    forty_days_ago = time.time() - 40 * 86400
    os.utime(old, (forty_days_ago, forty_days_ago))

    assert cleanup(config, journal) == [old]
    assert trashed == [old]
    assert recent.exists()


def test_free_path(tmp_path):
    write(tmp_path / "x.txt")
    write(tmp_path / "x (1).txt")
    assert free_path(tmp_path / "x.txt") == tmp_path / "x (2).txt"
    assert free_path(tmp_path / "y.txt") == tmp_path / "y.txt"


def test_invalid_config(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("source: .\nrules:\n  - name: Vide\n    to: X\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="critère"):
        load_config(bad)
