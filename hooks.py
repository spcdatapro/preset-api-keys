"""Lifecycle hooks (run in the Agent Zero framework runtime).

The plugin needs no setup or dependencies, so there is no install(). It does own data outside its
folder: the per-preset API keys (usr/preset_api_keys/keys.json). They are removed on uninstall so
no secret is left behind. Presets and provider keys are never touched.
"""

import os


def uninstall():
    from usr.plugins.preset_api_keys.helpers import store

    store.delete_store()
    try:
        os.rmdir(store.store_dir())  # only if empty: never removes anything we do not own
    except OSError:
        pass
