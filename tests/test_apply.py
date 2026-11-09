"""The runtime path: which key a model build gets."""

import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import models
from usr.plugins.preset_api_keys.helpers import apply, resolve, store

from pak_samples import KEY_A, KEY_B

PLUGIN_DIR = Path(__file__).resolve().parent.parent
FUNCTIONS = PLUGIN_DIR / "extensions" / "python" / "_functions"
GETTERS = ("get_chat_model", "get_utility_model", "get_embedding_model")
PROVIDER_KEY = "provider-key-from-env"


class FakeContext:
    def __init__(self, data=None, streaming_agent=None):
        self.id = "ctx"
        self.data = dict(data or {})
        self.streaming_agent = streaming_agent
        self.agent0 = None

    def get_data(self, key, default=None):
        return self.data.get(key, default)


def make_agent(preset: str | None = None, select: str | None = None, tree=None):
    """An agent whose chat picked `preset` in the switcher, or whose scope selected `select`."""
    if select:
        config = tree.root / "usr" / "plugins" / "_model_config" / "config.json"
        config.write_text(json.dumps({"model_preset": select}), encoding="utf-8")
    context = FakeContext({"chat_model_override": {"preset_name": preset}} if preset else {})
    agent = SimpleNamespace(context=context, config=SimpleNamespace(profile=""))
    context.agent0 = agent
    return agent


def set_ambient(monkeypatch, context) -> None:
    import agent as agent_module

    monkeypatch.setattr(agent_module.AgentContext, "current", staticmethod(lambda: context))


def load_extension(*parts: str):
    path = FUNCTIONS.joinpath(*parts)
    spec = importlib.util.spec_from_file_location("pak_ext_" + "_".join(parts).replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classes = [
        cls for cls in vars(module).values()
        if inspect.isclass(cls) and cls.__module__ == module.__name__
    ]
    assert len(classes) == 1
    return classes[0]


def run_key_hook(provider: str, agent=None) -> str:
    """What models.get_api_key would return after this plugin's end extension."""
    data = {"args": (provider,), "kwargs": {}, "result": PROVIDER_KEY, "exception": None}
    load_extension("models", "get_api_key", "end", "_50_preset_api_key.py")(agent=agent).execute(data=data)
    return data["result"]


@pytest.fixture
def keys(tree):
    resolve.set_key("Alpha", "anthropic", KEY_A)
    resolve.set_key("Mixed", "openai", KEY_B)
    return tree


def test_without_any_stored_key_nothing_is_resolved(tree, monkeypatch):
    set_ambient(monkeypatch, make_agent("Alpha").context)
    assert apply.preset_key("anthropic") is None
    assert run_key_hook("anthropic") == PROVIDER_KEY


def test_without_an_agent_or_a_running_chat_the_provider_key_is_used(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    assert run_key_hook("anthropic") == PROVIDER_KEY


def test_the_chat_preset_key_is_used_for_its_provider_only(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    apply.enter(make_agent("Alpha"))
    assert run_key_hook("anthropic") == KEY_A
    assert run_key_hook("openai") == PROVIDER_KEY  # e.g. the browser's own model on another provider
    assert run_key_hook("perplexity") == PROVIDER_KEY
    assert run_key_hook("") == PROVIDER_KEY


def test_a_preset_without_its_own_key_uses_the_provider_key(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    apply.enter(make_agent("Inherits"))
    assert run_key_hook("anthropic") == PROVIDER_KEY


def test_the_scope_selection_counts_when_the_chat_has_no_override(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    apply.enter(make_agent(select="Alpha", tree=keys))
    assert run_key_hook("anthropic") == KEY_A


def test_a_key_for_another_provider_than_the_slot_is_not_used(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    apply.enter(make_agent("Mixed"))
    assert run_key_hook("openai") == KEY_B
    assert run_key_hook("anthropic") == PROVIDER_KEY


def test_builds_outside_the_agent_getters_follow_the_running_chat(keys, monkeypatch):
    set_ambient(monkeypatch, make_agent("Alpha").context)
    assert run_key_hook("anthropic") == KEY_A


def test_the_streaming_agent_of_the_running_chat_wins_over_agent0(keys, monkeypatch):
    context = make_agent("Inherits").context
    context.streaming_agent = make_agent("Alpha")
    set_ambient(monkeypatch, context)
    assert run_key_hook("anthropic") == KEY_A


def test_the_exact_agent_wins_over_the_running_chat_and_is_forgotten_after_the_build(keys, monkeypatch):
    set_ambient(monkeypatch, make_agent("Inherits").context)
    asking = make_agent("Alpha")
    for getter in GETTERS:
        load_extension("agent", "Agent", getter, "start", "_05_preset_api_key.py")(agent=asking).execute(data={})
        assert run_key_hook("anthropic") == KEY_A
        load_extension("agent", "Agent", getter, "end", "_50_preset_api_key.py")(agent=asking).execute(data={})
        assert run_key_hook("anthropic") == PROVIDER_KEY


def test_an_orphaned_or_inactive_key_is_never_used(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    store.put("Gone", "anthropic", KEY_B)
    apply.enter(make_agent("Gone"))  # unknown preset: the framework falls back to Default
    assert run_key_hook("anthropic") == PROVIDER_KEY


def test_a_failure_falls_back_to_the_provider_key_and_warns_once_without_the_key(keys, monkeypatch, capsys):
    set_ambient(monkeypatch, None)
    apply.enter(make_agent("Alpha"))

    def boom(*args, **kwargs):
        raise RuntimeError(f"secret {KEY_A}")

    monkeypatch.setattr(resolve, "key_for", boom)
    assert run_key_hook("anthropic") == PROVIDER_KEY
    assert run_key_hook("anthropic") == PROVIDER_KEY
    printed = capsys.readouterr()
    assert (printed.out + printed.err).count("Preset API Keys") == 1
    assert KEY_A not in printed.out + printed.err


def test_a_damaged_store_falls_back_to_the_provider_key(keys, monkeypatch):
    set_ambient(monkeypatch, None)
    keys.keys_file.write_text("{broken", encoding="utf-8")
    apply.enter(make_agent("Alpha"))
    assert run_key_hook("anthropic") == PROVIDER_KEY


# ---------- Canaries: the framework behaviour this plugin relies on ----------


def test_the_framework_still_exposes_the_extension_points_this_plugin_uses():
    from agent import Agent

    assert hasattr(models.get_api_key, "__wrapped__"), "models.get_api_key is no longer @extensible"
    assert models.get_api_key.__module__ == "models" and models.get_api_key.__qualname__ == "get_api_key"
    for getter in GETTERS:
        assert hasattr(getattr(Agent, getter), "__wrapped__"), f"Agent.{getter} is no longer @extensible"


def test_every_model_build_without_an_explicit_key_still_asks_get_api_key():
    merge = inspect.getsource(models._merge_provider_defaults)
    assert '"api_key" not in kwargs' in merge and "get_api_key(original_provider)" in merge
    for builder in (models._get_litellm_chat, models._get_litellm_embedding):
        assert 'kwargs.pop("api_key", None) or get_api_key(provider_name)' in inspect.getsource(builder)


def test_the_framework_still_resolves_the_preset_of_an_agent(tree):
    from plugins._model_config.helpers import model_config

    assert model_config.get_effective_preset_name(make_agent("alpha")) == "Alpha"
    assert model_config.get_effective_preset_name(make_agent("Nope")) == "Default"


def test_each_extension_file_sits_at_a_point_the_framework_emits():
    found = sorted(str(p.relative_to(FUNCTIONS)).replace("\\", "/") for p in FUNCTIONS.rglob("*.py"))
    expected = [f"agent/Agent/{getter}/{side}" for getter in GETTERS
                for side in ("end/_50_preset_api_key.py", "start/_05_preset_api_key.py")]
    assert found == sorted(expected + ["models/get_api_key/end/_50_preset_api_key.py"])
