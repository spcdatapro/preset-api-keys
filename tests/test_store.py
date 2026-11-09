import json
import os
import stat

import pytest

from usr.plugins.preset_api_keys.helpers import store
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError

from pak_samples import KEY_A, KEY_B


def test_an_empty_store_has_no_keys_and_creates_nothing(tree):
    assert store.has_keys() is False
    assert store.entries() == {} and store.get("Alpha") is None
    assert not tree.keys_file.parent.exists()


def test_put_writes_an_owner_only_file_outside_the_plugin_folder(tree):
    store.put("Alpha", "anthropic", KEY_A)
    assert tree.keys_file.is_file()
    assert stat.S_IMODE(os.stat(tree.keys_file).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(tree.keys_file.parent).st_mode) == 0o700
    assert "plugins" not in tree.keys_file.relative_to(tree.root).parts
    assert not tree.keys_file.with_name("keys.json.tmp").exists()


def test_names_are_matched_case_insensitively_and_keep_their_spelling(tree):
    store.put("Alpha", "anthropic", KEY_A)
    assert store.get(" alpha ")["key"] == KEY_A
    assert store.get("ALPHA")["preset"] == "Alpha"
    store.put("ALPHA", "anthropic", KEY_B)
    assert len(store.entries()) == 1 and store.get("alpha")["key"] == KEY_B


def test_remove_reports_whether_something_was_deleted(tree):
    store.put("Alpha", "anthropic", KEY_A)
    assert store.remove("alpha") is True
    assert store.remove("alpha") is False
    assert store.has_keys() is False


def test_move_keeps_key_provider_and_date(tree):
    store.put("Old name", "anthropic", KEY_A)
    before = store.get("Old name")
    store.move("old NAME", "Alpha")
    moved = store.get("Alpha")
    assert store.get("Old name") is None
    assert (moved["key"], moved["provider"], moved["updated_at"]) == (KEY_A, "anthropic", before["updated_at"])
    assert moved["preset"] == "Alpha"


def test_move_refuses_a_missing_source_or_a_taken_target(tree):
    store.put("Alpha", "anthropic", KEY_A)
    store.put("Mixed", "openai", KEY_B)
    with pytest.raises(KeyStoreError):
        store.move("Nope", "Inherits")
    with pytest.raises(KeyStoreError):
        store.move("Alpha", "Mixed")
    assert store.get("Alpha")["key"] == KEY_A and store.get("Mixed")["key"] == KEY_B


def test_changes_made_by_another_process_are_seen(tree):
    store.put("Alpha", "anthropic", KEY_A)
    assert store.get("Alpha")["key"] == KEY_A
    data = json.loads(tree.keys_file.read_text(encoding="utf-8"))
    data["keys"]["alpha"]["key"] = KEY_B + "-longer"
    tree.keys_file.write_text(json.dumps(data), encoding="utf-8")
    assert store.get("Alpha")["key"] == KEY_B + "-longer"


@pytest.mark.parametrize(
    "content",
    ["{not json", "[]", '{"keys": []}', '{"keys": {"alpha": {"preset": "Alpha", "provider": "anthropic"}}}'],
)
def test_a_damaged_file_is_reported_and_never_overwritten(tree, content):
    tree.keys_file.parent.mkdir(parents=True)
    tree.keys_file.write_text(content, encoding="utf-8")
    with pytest.raises(KeyStoreError) as caught:
        store.entries()
    assert KEY_A not in str(caught.value)
    with pytest.raises(KeyStoreError):
        store.put("Alpha", "anthropic", KEY_A)
    assert tree.keys_file.read_text(encoding="utf-8") == content


def test_delete_store_removes_only_its_own_files(tree):
    store.put("Alpha", "anthropic", KEY_A)
    stray = tree.keys_file.with_name("notes.txt")
    stray.write_text("keep", encoding="utf-8")
    store.delete_store()
    store.delete_store()
    assert not tree.keys_file.exists() and stray.read_text(encoding="utf-8") == "keep"
    assert store.has_keys() is False
