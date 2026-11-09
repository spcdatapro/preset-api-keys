import asyncio
import json
from pathlib import Path

import pytest

from helpers.api import ApiHandler
from helpers.modules import load_classes_from_file
from usr.plugins.preset_api_keys.api.delete_key import DeleteKey
from usr.plugins.preset_api_keys.api.keys_overview import KeysOverview
from usr.plugins.preset_api_keys.api.move_key import MoveKey
from usr.plugins.preset_api_keys.api.set_key import SetKey
from usr.plugins.preset_api_keys.helpers import store

from pak_samples import KEY_A, KEY_B, standard

API_DIR = Path(__file__).resolve().parent.parent / "api"
HANDLERS = {
    "keys_overview": KeysOverview,
    "set_key": SetKey,
    "delete_key": DeleteKey,
    "move_key": MoveKey,
}


def call(handler_cls, payload):
    return asyncio.run(handler_cls(None, None).process(payload, None))


def status_and_text(response):
    return response.status_code, response.get_data(as_text=True)


def as_text(result) -> str:
    return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result.get_data(as_text=True)


@pytest.mark.parametrize("file_name, handler_cls", HANDLERS.items())
def test_each_file_exposes_exactly_its_handler_with_secure_defaults(file_name, handler_cls):
    classes = load_classes_from_file(str(API_DIR / f"{file_name}.py"), ApiHandler)
    assert [cls.__name__ for cls in classes] == [handler_cls.__name__]
    assert handler_cls.requires_auth() is True
    assert handler_cls.requires_csrf() is True
    assert handler_cls.requires_api_key() is False
    assert handler_cls.requires_loopback() is False
    assert handler_cls.get_methods() == ["POST"]


def test_there_is_no_handler_that_could_reveal_a_key():
    assert {p.stem for p in API_DIR.glob("*.py")} == set(HANDLERS)


def test_set_then_overview_then_delete(tree):
    assert call(SetKey, {"preset": "Alpha", "key": KEY_A}) == {"ok": True, "preset": "Alpha", "provider": "anthropic"}
    view = call(KeysOverview, {})
    alpha = next(p for p in view["presets"] if p["name"] == "Alpha")
    assert view["ok"] is True and alpha["key"]["state"] == "active" and alpha["key"]["masked"] == "••••1111"
    assert call(DeleteKey, {"preset": "Alpha"}) == {"ok": True, "deleted": True}
    assert store.has_keys() is False


def test_move_key_after_a_rename(tree):
    call(SetKey, {"preset": "Alpha", "provider": "anthropic", "key": KEY_A})
    renamed = standard()
    renamed[1]["name"] = "Beta"
    tree.write(renamed)
    assert [o["name"] for o in call(KeysOverview, {})["orphans"]] == ["Alpha"]
    assert call(MoveKey, {"from": "Alpha", "to": "Beta"}) == {"ok": True, "preset": "Beta"}
    assert call(KeysOverview, {})["orphans"] == []


@pytest.mark.parametrize(
    "handler_cls, payload",
    [
        (SetKey, {}),
        (SetKey, {"preset": "Nope", "key": KEY_A}),
        (SetKey, {"preset": "Alpha", "provider": "openai", "key": KEY_A}),
        (SetKey, {"preset": "Alpha", "key": ""}),
        (SetKey, {"preset": "Alpha", "key": ["a"]}),
        (SetKey, {"preset": "Alpha", "key": KEY_A + " " + KEY_B}),
        (DeleteKey, {}),
        (MoveKey, {}),
        (MoveKey, {"from": "Nope", "to": "Alpha"}),
        (MoveKey, {"from": "Alpha", "to": "Mixed"}),
    ],
)
def test_user_errors_are_http_400_and_never_echo_the_key(tree, handler_cls, payload):
    status, text = status_and_text(call(handler_cls, payload))
    assert status == 400 and text
    assert KEY_A not in text and KEY_B not in text


def test_a_damaged_store_is_a_400_for_every_handler(tree):
    tree.keys_file.parent.mkdir(parents=True)
    tree.keys_file.write_text("{broken", encoding="utf-8")
    for handler_cls, payload in (
        (KeysOverview, {}),
        (SetKey, {"preset": "Alpha", "key": KEY_A}),
        (DeleteKey, {"preset": "Alpha"}),
        (MoveKey, {"from": "Gone", "to": "Alpha"}),
    ):
        status, text = status_and_text(call(handler_cls, payload))
        assert status == 400 and KEY_A not in text
    assert tree.keys_file.read_text(encoding="utf-8") == "{broken"


def test_no_response_ever_contains_a_key(tree):
    responses = [
        call(SetKey, {"preset": "Alpha", "key": KEY_A}),
        call(SetKey, {"preset": "Mixed", "provider": "openai", "key": KEY_B}),
        call(KeysOverview, {}),
        call(SetKey, {"preset": "Alpha", "provider": "openai", "key": KEY_B}),
        call(MoveKey, {"from": "Alpha", "to": "Mixed"}),
    ]
    renamed = standard()
    renamed[1]["name"] = "Beta"
    tree.write(renamed)
    responses += [call(KeysOverview, {}), call(MoveKey, {"from": "Alpha", "to": "Beta"}), call(KeysOverview, {}),
                  call(DeleteKey, {"preset": "Beta"})]
    for response in responses:
        text = as_text(response)
        for key in (KEY_A, KEY_B):
            assert key not in text and key[:12] not in text
