from helpers.api import ApiHandler, Input, Output, Request, Response
from usr.plugins.preset_api_keys.helpers import resolve
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError


class KeysOverview(ApiHandler):
    """Presets with the state of their own key, and orphaned keys. Keys are masked, never returned."""

    async def process(self, input: Input, request: Request) -> Output:
        try:
            return {"ok": True, **resolve.overview()}
        except KeyStoreError as error:
            return Response(str(error), 400)
