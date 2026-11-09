from helpers.api import ApiHandler, Input, Output, Request, Response
from usr.plugins.preset_api_keys.helpers import resolve
from usr.plugins.preset_api_keys.helpers.errors import KeyStoreError


class DeleteKey(ApiHandler):
    """Remove the key stored for a preset name (existing or orphaned). Input: preset. Output: deleted."""

    async def process(self, input: Input, request: Request) -> Output:
        try:
            result = resolve.delete_key(input.get("preset"))
        except KeyStoreError as error:
            return Response(str(error), 400)
        return {"ok": True, **result}
