from helpers.extension import Extension
from usr.plugins.preset_api_keys.helpers import apply


class PresetApiKey(Extension):
    """Swap the provider key for the active preset's own key, when it has one for this provider."""

    def execute(self, data: dict = {}, **kwargs):
        args = data.get("args") or ()
        provider = args[0] if args else (data.get("kwargs") or {}).get("service")
        key = apply.preset_key(provider)
        if key:
            data["result"] = key
