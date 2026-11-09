import json

import pytest

from usr.plugins.preset_api_keys.helpers import resolve, store
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError

from pak_samples import KEY_A, KEY_B, standard


def row(name: str) -> dict:
    return next(p for p in resolve.overview()["presets"] if p["name"] == name)


def test_mask_never_reveals_more_than_the_last_four_characters():
    assert resolve.mask(KEY_A) == "••••1111"
    assert resolve.mask("short") == "••••"
    assert KEY_A[:-4] not in resolve.mask(KEY_A)


def test_overview_lists_every_preset_with_its_effective_providers(tree):
    view = resolve.overview()
    assert [p["name"] for p in view["presets"]] == ["Default", "Alpha", "Mixed", "Inherits"]
    assert row("Default")["is_default"] is True
    assert row("Inherits")["providers"] == {
        "chat": "anthropic", "utility": "anthropic", "embedding": "huggingface", "vision": "",
    }
    assert row("Mixed")["providers"]["chat"] == "openai" and row("Mixed")["providers"]["utility"] == "anthropic"
    assert all(p["key"] is None for p in view["presets"]) and view["orphans"] == []


def test_set_key_defaults_to_the_main_provider_and_applies_to_matching_slots(tree):
    assert resolve.set_key("alpha", "", f"  {KEY_A}\n") == {"preset": "Alpha", "provider": "anthropic"}
    key = row("Alpha")["key"]
    assert key["state"] == "active" and key["slots"] == ["chat", "utility"] and key["masked"] == "••••1111"
    assert resolve.key_for("ALPHA", "Anthropic") == KEY_A
    assert resolve.key_for("Alpha", "openai") is None
    assert resolve.key_for("Alpha", "") is None
    assert resolve.key_for("Default", "anthropic") is None


def test_a_preset_with_two_providers_keeps_one_key_for_the_chosen_one(tree):
    resolve.set_key("Mixed", "anthropic", KEY_A)
    assert row("Mixed")["key"]["slots"] == ["utility"]
    assert resolve.key_for("Mixed", "anthropic") == KEY_A and resolve.key_for("Mixed", "openai") is None
    resolve.set_key("Mixed", "openai", KEY_B)
    assert row("Mixed")["key"]["slots"] == ["chat"]
    assert resolve.key_for("Mixed", "anthropic") is None and resolve.key_for("Mixed", "openai") == KEY_B


@pytest.mark.parametrize(
    "preset, provider, key",
    [
        ("Nope", "anthropic", KEY_A),
        ("", "anthropic", KEY_A),
        ("Alpha", "openai", KEY_A),
        ("Alpha", "anthropic", ""),
        ("Alpha", "anthropic", "   "),
        ("Alpha", "anthropic", None),
        ("Alpha", "anthropic", "two words"),
        ("Alpha", "anthropic", "x" * 501),
    ],
)
def test_set_key_rejects_bad_input_without_storing_or_echoing_it(tree, preset, provider, key):
    with pytest.raises(KeyStoreError) as caught:
        resolve.set_key(preset, provider, key)
    assert store.has_keys() is False
    if isinstance(key, str) and key.strip():
        assert key not in str(caught.value)


def test_a_provider_change_leaves_the_key_stored_but_inactive_until_it_matches_again(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    changed = standard()
    changed[1]["chat"] = {"provider": "openai", "name": "gpt"}
    changed[1]["utility"] = {"provider": "openai", "name": "gpt-mini"}
    tree.write(changed)
    key = row("Alpha")["key"]
    assert key["state"] == "inactive" and key["slots"] == [] and key["provider"] == "anthropic"
    assert store.get("Alpha")["key"] == KEY_A
    tree.write(standard())
    assert row("Alpha")["key"]["state"] == "active"


def test_a_renamed_or_deleted_preset_leaves_an_orphan_that_applies_to_nothing(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    renamed = standard()
    renamed[1]["name"] = "Beta"
    tree.write(renamed)
    view = resolve.overview()
    assert [o["name"] for o in view["orphans"]] == ["Alpha"]
    assert view["orphans"][0]["masked"] == "••••1111"
    assert row("Beta")["key"] is None and resolve.key_for("Beta", "anthropic") is None


def test_move_key_hands_an_orphan_to_an_existing_preset(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    renamed = standard()
    renamed[1]["name"] = "Beta"
    tree.write(renamed)
    assert resolve.move_key("alpha", "beta") == {"preset": "Beta"}
    assert resolve.overview()["orphans"] == [] and resolve.key_for("Beta", "anthropic") == KEY_A


def test_move_key_only_moves_orphans_to_existing_presets_without_a_key(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    with pytest.raises(KeyStoreError):
        resolve.move_key("Alpha", "Inherits")  # Alpha still exists: nothing to repair
    renamed = standard()
    renamed[1]["name"] = "Beta"
    tree.write(renamed)
    resolve.set_key("Inherits", "anthropic", KEY_B)
    for target in ("Nope", "Inherits", ""):
        with pytest.raises(KeyStoreError):
            resolve.move_key("Alpha", target)
    assert store.get("Alpha")["key"] == KEY_A and store.get("Inherits")["key"] == KEY_B


def test_delete_key_works_for_presets_and_orphans(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    assert resolve.delete_key("alpha") == {"deleted": True}
    assert resolve.delete_key("alpha") == {"deleted": False}
    with pytest.raises(KeyStoreError):
        resolve.delete_key("  ")


def test_the_overview_never_contains_a_key(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    resolve.set_key("Mixed", "openai", KEY_B)
    renamed = standard()
    renamed[2]["name"] = "Gone"
    tree.write(renamed)
    text = json.dumps(resolve.overview(), ensure_ascii=False)
    for key in (KEY_A, KEY_B):
        assert key not in text and key[:12] not in text


def test_nothing_is_written_to_the_presets_file(tree):
    before = tree.presets_file.read_bytes()
    resolve.set_key("Alpha", "anthropic", KEY_A)
    resolve.delete_key("Alpha")
    assert tree.presets_file.read_bytes() == before
