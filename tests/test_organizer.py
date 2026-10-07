import os
import time

import pytest

import organizer

CONFIG = """
source: {folder}
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
    to: Documents
cleanup:
  - folder: Installateurs
    older_than_days: 30
"""


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    """Un faux dossier Téléchargements, avec un journal et une corbeille factices."""
    folder = tmp_path / "Downloads"
    folder.mkdir()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG.format(folder=folder.as_posix()), encoding="utf-8")

    monkeypatch.setattr(organizer, "JOURNAL", tmp_path / "journal.jsonl")
    trash = []
    monkeypatch.setattr(organizer, "send2trash", lambda path: (trash.append(os.path.basename(path)), os.remove(path)))
    return folder, organizer.load_config(config_file), trash


def create(path, content="contenu"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_regles(downloads):
    folder, config, _ = downloads
    year = time.localtime().tm_year
    assert organizer.find_folder(create(folder / "Facture-EDF.PDF"), config) == folder / "Admin" / str(year)
    assert organizer.find_folder(create(folder / "cours.pdf"), config) == folder / "Documents"
    assert organizer.find_folder(create(folder / "photo.JPG"), config) == folder / "Images"
    assert organizer.find_folder(create(folder / "notes.txt"), config) is None
    assert organizer.find_folder(create(folder / "film.mp4.crdownload"), config) is None


def test_rangement_doublons_et_conflits(downloads):
    folder, config, trash = downloads
    create(folder / "Images" / "a.png", "pareil")
    create(folder / "a-copie.png", "pareil")  # même contenu → corbeille
    create(folder / "Images" / "b.png", "ancien")
    create(folder / "b.png", "nouveau")  # même nom, contenu différent → renommé

    organizer.tidy_folder(config)

    assert trash == ["a-copie.png"]
    assert (folder / "Images" / "b (1).png").read_text() == "nouveau"
    assert not (folder / "b.png").exists()


def test_simulation(downloads):
    folder, config, _ = downloads
    create(folder / "photo.png")
    assert organizer.tidy_folder(config, test=True) == ["📁 photo.png → Images"]
    assert (folder / "photo.png").exists()


def test_annulation(downloads):
    folder, config, _ = downloads
    create(folder / "photo.png")
    create(folder / "cours.pdf")
    organizer.tidy_folder(config)
    assert not (folder / "photo.png").exists()

    organizer.undo_last_run()
    assert (folder / "photo.png").exists() and (folder / "cours.pdf").exists()
    assert organizer.undo_last_run() == ["Rien à annuler."]


def test_nettoyage(downloads):
    folder, config, trash = downloads
    old = create(folder / "Installateurs" / "vieux.exe")
    create(folder / "Installateurs" / "recent.exe")
    forty_days_ago = time.time() - 40 * 24 * 3600
    os.utime(old, (forty_days_ago, forty_days_ago))

    organizer.clean_old_files(config)
    assert trash == ["vieux.exe"]


def test_nom_libre(tmp_path):
    create(tmp_path / "x.txt")
    create(tmp_path / "x (1).txt")
    assert organizer.free_name(tmp_path / "x.txt") == tmp_path / "x (2).txt"
