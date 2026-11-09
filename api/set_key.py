from helpers.api import ApiHandler, Input, Output, Request, Response
from usr.plugins.preset_api_keys.helpers import resolve
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError


class SetKey(ApiHandler):
    """Store or replace a preset's own key. Input: preset, provider (optional), key. Output: preset, provider."""

    async def process(self, input: Input, request: Request) -> Output:
        try:
            result = resolve.set_key(input.get("preset"), input.get("provider"), input.get("key"))
        except KeyStoreError as error:
            return Response(str(error), 400)
        return {"ok": True, **result}
