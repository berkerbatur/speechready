"""Drop-in hooks for voice agent frameworks.

Each module returns a plain callable in the shape the framework expects, so
nothing here imports the framework itself and no extra dependency is needed:

- `speechready.integrations.livekit.text_transform(...)` for `AgentSession(tts_text_transforms=[...])`
- `speechready.integrations.pipecat.text_transform(...)` for a TTS service's `text_transforms=[("*", ...)]`
"""
