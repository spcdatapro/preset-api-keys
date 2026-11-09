# Preset API Keys

An [Agent Zero](https://github.com/agent0ai/agent-zero) plugin that lets each **model preset** have its
own API key.

Agent Zero keeps one API key per provider, shared by every preset. If you keep one preset per project or
per person, all of them spend from the same key. With this plugin a preset can use a key of its own, so
usage and rate limits stay apart. A preset without its own key keeps using the provider key, as before.

No external services, no extra dependencies, and no change to Agent Zero's own code.

## Install

In Agent Zero open **Plugins → Install**, choose **Git** and use:

```text
https://github.com/spcdatapro/preset-api-keys
```

Restart Agent Zero, then open it from the sidebar quick-actions menu (**Preset API Keys**).

Tested with Agent Zero v2.15.

## Usage

The dialog lists every preset with the providers its models use and whether it has its own key.

- **Set key**: paste the key and save. If the preset uses more than one provider, choose which one the
  key belongs to. The key is used for every model of that preset that runs on that provider (usually Main
  and Utility).
- **Replace** or **Remove** it at any time. A saved key is never shown again: only its last four
  characters, so you can tell keys apart.
- Only you change a key, from this dialog. Duplicating a preset or copying settings between presets does
  not copy or touch it.

### What happens when a preset changes

- **The preset changes provider.** Its key stays saved but is not used, and the dialog says so. If the
  preset goes back to that provider, the key is used again.
- **The preset is renamed or deleted.** Agent Zero does not tell plugins, so the key is left under the old
  name and is not used. It shows up under **Keys without a preset**, where you can move it to the renamed
  preset or remove it.

## Good to know

- **Keep the provider key.** It is the fallback for presets without their own key, and Agent Zero still
  checks for it before letting you chat.
- **The key follows the chat.** A call uses the key of the preset selected for the chat (or its project or
  agent profile) that makes it. This covers the main and utility models, subordinate agents, background
  memory tasks, chat compaction and memory embeddings. If you compact a chat with a different preset, the
  chat's own key is still the one used.
- **Calls outside a chat use the provider key**: the model list in Settings, the missing-key check and
  startup tasks.
- **Embeddings keep their key until reloaded.** Agent Zero builds the memory embedding model once and
  reuses it, so a new key for an embedding provider applies after the memory is reloaded or Agent Zero
  restarts. Main and utility models pick up a new key on the next call.

## Security

- Keys are stored in `usr/preset_api_keys/keys.json`, outside the plugin folder, readable only by the
  owner (mode 0600). They are never written to the presets file or to `.env`.
- The file is **plain text**. Anyone who can enter the container can read it, and so can the agent itself
  through its terminal. It is also included in Agent Zero backups, like the rest of `usr/`.
- A key never goes back to the browser, and the plugin never logs one.

## Uninstall

Delete the plugin from the Plugins dialog. Uninstalling also deletes the stored keys, so nothing sensitive
is left behind. Your presets and provider keys are never touched. If you delete the folder by hand instead,
remove `usr/preset_api_keys/` yourself.

## Development

The plugin lives in `usr/plugins/preset_api_keys/`. Tests use `pytest` and run with the framework's Python
from the Agent Zero root, on a throwaway copy of the model configuration:

```bash
python -m pytest usr/plugins/preset_api_keys/tests -q
```

## License

MIT, see [LICENSE](LICENSE).
