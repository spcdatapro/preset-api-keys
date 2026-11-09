"""Which key applies to which preset, and the UI-safe view of the store.

One key per preset, bound to the provider chosen when it was saved. It applies to every model slot
of the preset whose provider matches; if the preset later moves to another provider the key stays
stored but inactive. A key whose preset no longer exists (renamed or deleted in the native editor,
which sends no event) is an orphan: it applies to nothing until the user moves or deletes it.
"""

from __future__ import annotations

from plugins._model_config.helpers import model_config

from usr.plugins.preset_api_keys.helpers import store
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError

SLOTS = {"chat": "Main", "utility": "Utility", "embedding": "Embedding", "vision": "Vision"}
MASK = "••••"


def norm_provider(provider: object) -> str:
    return str(provider or "").strip().lower()


def mask(key: str) -> str:
    """Enough to tell two keys apart, never enough to use one."""
    return MASK + key[-4:] if len(key) >= 12 else MASK


def effective_providers(preset: dict, default: dict) -> dict[str, str]:
    """Provider of each slot after the framework's own inheritance from Default ('' if unset)."""
    config = model_config.preset_to_config(default)
    if str(preset.get("name") or "") != model_config.DEFAULT_PRESET_NAME:
        config = model_config.build_config_from_preset(preset, config, strip_api_key=False)
    return {
        slot: norm_provider((config.get(section) or {}).get("provider"))
        for slot, section in model_config.PRESET_SLOT_CONFIG_SECTIONS.items()
    }


def key_for(preset_name: object, provider: object) -> str | None:
    """The preset's own key if it has one for this provider, else None (use the provider key)."""
    wanted = norm_provider(provider)
    if not wanted:
        return None
    entry = store.get(preset_name)
    if not entry or norm_provider(entry["provider"]) != wanted:
        return None
    return entry["key"]


def _presets() -> tuple[list[dict], dict]:
    presets = model_config.get_presets()
    default = next((p for p in presets if p.get("name") == model_config.DEFAULT_PRESET_NAME), {})
    return presets, default


def _find(presets: list[dict], name: object) -> dict | None:
    wanted = store.norm(name)
    return next((p for p in presets if wanted and store.norm(p.get("name")) == wanted), None)


def overview() -> dict:
    """Everything the UI needs. Never includes a key value."""
    presets, default = _presets()
    entries = store.entries()
    rows = []
    for preset in presets:
        name = str(preset.get("name") or "")
        providers = effective_providers(preset, default)
        entry = entries.pop(store.norm(name), None)
        key = None
        if entry:
            provider = norm_provider(entry["provider"])
            slots = [slot for slot, value in providers.items() if value == provider]
            key = {
                "provider": provider,
                "masked": mask(entry["key"]),
                "updated_at": entry.get("updated_at", ""),
                "state": "active" if slots else "inactive",
                "slots": slots,
            }
        rows.append(
            {
                "name": name,
                "is_default": name == model_config.DEFAULT_PRESET_NAME,
                "providers": providers,
                "key": key,
            }
        )
    orphans = [
        {
            "name": entry["preset"],
            "provider": norm_provider(entry["provider"]),
            "masked": mask(entry["key"]),
            "updated_at": entry.get("updated_at", ""),
        }
        for entry in entries.values()
    ]
    return {"presets": rows, "orphans": orphans, "slots": SLOTS}


def clean_key(key: object) -> str:
    if not isinstance(key, str) or not key.strip():
        raise KeyStoreError("Enter an API key")
    key = key.strip()
    if len(key) > store.MAX_KEY_LENGTH or any(ch.isspace() or not ch.isprintable() for ch in key):
        raise KeyStoreError("That does not look like an API key")
    return key


def set_key(preset_name: object, provider: object, key: object) -> dict:
    presets, default = _presets()
    preset = _find(presets, preset_name)
    if not preset:
        raise KeyStoreError("Preset not found")
    providers = effective_providers(preset, default)
    provider = norm_provider(provider) or providers.get("chat", "")
    if not provider or provider not in providers.values():
        raise KeyStoreError("The preset does not use that provider")
    name = str(preset["name"])
    store.put(name, provider, clean_key(key))
    return {"preset": name, "provider": provider}


def delete_key(preset_name: object) -> dict:
    if not store.norm(preset_name):
        raise KeyStoreError("Preset name is required")
    return {"deleted": store.remove(preset_name)}


def move_key(source: object, target: object) -> dict:
    """Give an orphaned key to an existing preset, e.g. after renaming it in the native editor."""
    presets, _default = _presets()
    if _find(presets, source):
        raise KeyStoreError("Only keys of presets that no longer exist can be moved")
    preset = _find(presets, target)
    if not preset:
        raise KeyStoreError("Target preset not found")
    name = str(preset["name"])
    store.move(source, name)
    return {"preset": name}
