from usr.plugins.preset_api_keys import hooks
from usr.plugins.preset_api_keys.helpers import store

from pak_samples import KEY_A


def test_uninstall_removes_the_keys_and_the_empty_data_folder(tree):
    store.put("Alpha", "anthropic", KEY_A)
    hooks.uninstall()
    assert not tree.keys_file.parent.exists()
    assert store.has_keys() is False


def test_uninstall_never_removes_files_it_does_not_own(tree):
    store.put("Alpha", "anthropic", KEY_A)
    stray = tree.keys_file.with_name("notes.txt")
    stray.write_text("keep", encoding="utf-8")
    hooks.uninstall()
    assert not tree.keys_file.exists() and stray.read_text(encoding="utf-8") == "keep"


def test_uninstall_never_touches_the_presets(tree):
    store.put("Alpha", "anthropic", KEY_A)
    before = tree.presets_file.read_bytes()
    hooks.uninstall()
    assert tree.presets_file.read_bytes() == before


def test_uninstall_with_nothing_to_clean_is_harmless(tree):
    hooks.uninstall()
    hooks.uninstall()
