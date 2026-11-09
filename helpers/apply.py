"""Runtime side: decide which preset a model build belongs to and hand over its key.

Every model build without an explicit key ends in models.get_api_key(provider), which only knows
the provider. The preset comes from the agent:

1. Agent.get_chat_model / get_utility_model / get_embedding_model set the exact agent for the
   duration of the build (enter/leave, called from this plugin's start/end extensions);
2. otherwise the chat running in this task (AgentContext.current()), which covers builds that skip
   the agent getters: compaction, vision_load, the browser's own model, memory embeddings.

With neither (startup, settings pages, the missing-key banner) the provider key is used.
"""

from __future__ import annotations

from contextvars import ContextVar

from helpers.print_style import PrintStyle

_building_for: ContextVar[object | None] = ContextVar("preset_api_keys_agent", default=None)
_warned = False


def enter(agent) -> None:
    _building_for.set(agent)


def leave() -> None:
    _building_for.set(None)


def _current_agent():
    agent = _building_for.get()
    if agent is not None:
        return agent
    from agent import AgentContext

    context = AgentContext.current()
    if not context:
        return None
    return getattr(context, "streaming_agent", None) or getattr(context, "agent0", None)


def preset_key(provider: object) -> str | None:
    """Key of the active preset for this provider, or None. Never raises."""
    global _warned
    try:
        from usr.plugins.preset_api_keys.helpers import resolve, store

        if not provider or not store.has_keys():
            return None
        agent = _current_agent()
        if agent is None:
            return None
        from plugins._model_config.helpers import model_config

        return resolve.key_for(model_config.get_effective_preset_name(agent), provider)
    except Exception as error:
        if not _warned:  # once: this runs on every model build
            _warned = True
            PrintStyle.warning(
                f"Preset API Keys: could not resolve a preset key ({type(error).__name__}); "
                "using the provider key instead."
            )
        return None
