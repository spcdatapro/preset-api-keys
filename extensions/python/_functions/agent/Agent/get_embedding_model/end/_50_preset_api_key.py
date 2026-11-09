from helpers.extension import Extension
from usr.plugins.preset_api_keys.helpers import apply


class PresetApiKeyScopeEnd(Extension):
    """The model is built: later key lookups in this task fall back to the running chat."""

    def execute(self, data: dict = {}, **kwargs):
        apply.leave()
