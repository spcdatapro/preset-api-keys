from helpers.extension import Extension
from usr.plugins.preset_api_keys.helpers import apply


class PresetApiKeyScope(Extension):
    """Runs before _model_config builds the model: tells the key lookup which agent asks."""

    def execute(self, data: dict = {}, **kwargs):
        apply.enter(self.agent)
