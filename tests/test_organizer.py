import os
import time
from pathlib import Path

import pytest

import organizer
from journal import Journal
from organizer import clean_old_files, find_destination, free_name, sort_folder
from settings import ConfigError, load_config

CONFIG = """
source: {folder}
destination: {folder}
duplicates: {duplicates}
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
    to: Gros/{{ext}}
cleanup:
  - folder: Installateurs
    older_than_days: 30
"""


def make_environment(tmp_path, monkeypatch, duplicates="trash"):
    """Un faux dossier Téléchargements, avec une corbeille factice (on note ce qui y est envoyé)."""
    folder = tmp_path / "Downloads"
    folder.mkdir()
    config_file = tmp_path / "config.yaml"
    config_file.write_text(CONFIG.format(folder=folder.as_posix(), duplicates=duplicates), encoding="utf-8")

    trash = []

    def fake_send2trash(path):
        trash.append(Path(path))
        os.remove(path)

    monkeypatch.setattr(organizer, "send2trash", fake_send2trash)
    config = load_config(config_file)
    return config, Journal(config.journal), folder, trash


@pytest.fixture
def env(tmp_path, monkeypatch):
    return make_environment(tmp_path, monkeypatch)


def create(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_la_premiere_regle_qui_correspond_gagne(env):
    config, _, folder, _ = env
    invoice = create(folder / "Facture-EDF.PDF")
    year = time.localtime(invoice.stat().st_mtime).tm_year
    assert find_destination(invoice, config)[1] == folder / "Admin" / str(year)
    assert find_destination(create(folder / "cours.pdf"), config)[1] == folder / "Documents" / "PDF"
    assert find_destination(create(folder / "photo.JPG"), config)[1] == folder / "Images"
    assert find_destination(create(folder / "notes.txt"), config) == (None, None)


def test_telechargements_en_cours_ignores(env):
    config, _, folder, _ = env
    assert find_destination(create(folder / "film.mp4.crdownload"), config) == (None, None)


def test_regex_et_taille_minimale(env):
    config, _, folder, _ = env
    assert find_destination(create(folder / "video-petite.bin", b"x"), config) == (None, None)
    assert find_destination(create(folder / "video-grosse.bin", b"x" * 2048), config)[1] == folder / "Gros" / "bin"


def test_doublons_a_la_corbeille_et_conflits_de_noms(env):
    config, journal, folder, trash = env
    create(folder / "Images" / "a.png", b"original")
    create(folder / "a.png", b"original")  # doublon exact → corbeille
    create(folder / "b.png", b"un")
    create(folder / "Images" / "b.png", b"autre")  # même nom, contenu différent → renommé

    outcomes = sort_folder(config, journal)
    actions = sorted((outcome.file.name, outcome.action) for outcome in outcomes if outcome.action != "skipped")
    assert actions == [("a.png", "duplicate"), ("b.png", "moved")]
    assert trash == [folder / "a.png"]
    assert (folder / "Images" / "b (1).png").read_bytes() == b"un"
    assert not (folder / "b.png").exists()


def test_option_duplicates_keep(tmp_path, monkeypatch):
    config, journal, folder, trash = make_environment(tmp_path, monkeypatch, duplicates="keep")
    create(folder / "Images" / "a.png", b"original")
    create(folder / "a.png", b"original")
    sort_folder(config, journal)
    assert trash == []
    assert (folder / "Images" / "a (1).png").exists()


def test_simulation_ne_change_rien(env):
    config, journal, folder, _ = env
    create(folder / "photo.png")
    outcomes = sort_folder(config, journal, dry_run=True)
    assert outcomes[0].action == "moved"
    assert (folder / "photo.png").exists()
    assert journal.entries() == []


def test_annulation_du_dernier_rangement(env):
    config, journal, folder, _ = env
    create(folder / "photo.png")
    create(folder / "cours.pdf")
    sort_folder(config, journal)
    assert not (folder / "photo.png").exists()

    report = journal.undo_last()
    assert len(report) == 2
    assert (folder / "photo.png").exists() and (folder / "cours.pdf").exists()
    assert journal.undo_last() == ["Rien à annuler."]


def test_nettoyage_des_vieux_fichiers(env):
    config, journal, folder, trash = env
    old = create(folder / "Installateurs" / "vieux.exe")
    recent = create(folder / "Installateurs" / "recent.exe")
    forty_days_ago = time.time() - 40 * 24 * 3600
    os.utime(old, (forty_days_ago, forty_days_ago))

    assert clean_old_files(config, journal) == [old]
    assert trash == [old]
    assert recent.exists()


def test_nom_libre(tmp_path):
    create(tmp_path / "x.txt")
    create(tmp_path / "x (1).txt")
    assert free_name(tmp_path / "x.txt") == tmp_path / "x (2).txt"
    assert free_name(tmp_path / "y.txt") == tmp_path / "y.txt"


@pytest.mark.parametrize("content, message", [
    ("source: .\nrules:\n  - name: Vide\n    to: X\n", "critère"),
    ("rules: []\n", "source"),
    ("source: .\nduplicates: peut-etre\n", "duplicates"),
    ("source: .\nrules:\n  - name: Sans destination\n    match: {extensions: [pdf]}\n", "to"),
    ("source: .\nrules:\n  - name: Regex cassée\n    match: {regex: '('}\n    to: X\n", "régulière"),
])
def test_configuration_invalide(tmp_path, content, message):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(config_file)
