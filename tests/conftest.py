import sys
from pathlib import Path

import pytest
import yaml

from helpers import cache, files, plugins
from usr.plugins.preset_api_keys.helpers import apply, store

# Agent Zero runs pytest with --import-mode=importlib, which does not put this folder on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pak_samples  # noqa: E402


class Tree:
    """A throwaway Agent Zero tree with the real _model_config code reading from it."""

    def __init__(self, root: Path):
        self.root = root

    @property
    def presets_file(self) -> Path:
        return self.root / "usr" / "plugins" / "_model_config" / "presets.yaml"

    @property
    def keys_file(self) -> Path:
        return self.root / "usr" / "preset_api_keys" / "keys.json"

    def write(self, preset_list: list[dict]) -> None:
        self.presets_file.parent.mkdir(parents=True, exist_ok=True)
        self.presets_file.write_text(yaml.safe_dump(preset_list, sort_keys=False), encoding="utf-8")
        cache.clear("*(plugins)*")


@pytest.fixture
def tree(monkeypatch, tmp_path: Path) -> Tree:
    monkeypatch.setattr(files, "_base_dir", str(tmp_path))
    monkeypatch.setattr(plugins, "call_plugin_hook", lambda plugin_name, hook_name, default=None, **kwargs: default)
    plugin_dir = tmp_path / "plugins" / "_model_config"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: _model_config\nper_project_config: true\nper_agent_config: true\n", encoding="utf-8"
    )
    (plugin_dir / "mode_presets_fallback.yaml").write_text(
        "- name: Default\n"
        "  chat: {provider: fallback, name: chat}\n"
        "  utility: {provider: fallback, name: utility}\n"
        "  embedding: {provider: fallback, name: embedding}\n",
        encoding="utf-8",
    )
    (tmp_path / "usr" / "plugins" / "_model_config").mkdir(parents=True)
    (tmp_path / "usr" / "projects").mkdir(parents=True)
    cache.clear("*(plugins)*")
    monkeypatch.setattr(store, "_cache", None)
    monkeypatch.setattr(apply, "_warned", False)
    apply.leave()
    made = Tree(tmp_path)
    made.write(pak_samples.standard())
    yield made
    apply.leave()
    cache.clear("*(plugins)*")
