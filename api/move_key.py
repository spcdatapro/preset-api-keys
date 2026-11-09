from helpers.api import ApiHandler, Input, Output, Request, Response
from usr.plugins.preset_api_keys.helpers import resolve
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError


class MoveKey(ApiHandler):
    """Give an orphaned key to an existing preset. Input: from, to. Output: preset."""

    async def process(self, input: Input, request: Request) -> Output:
        try:
            result = resolve.move_key(input.get("from"), input.get("to"))
        except KeyStoreError as error:
            return Response(str(error), 400)
        return {"ok": True, **result}
