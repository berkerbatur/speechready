# Examples

Runnable agents that put speechready between the LLM and the TTS, one per framework, plus a sample lexicon. Each file starts with its install line, the environment variables it reads, and how to run it. They are written against the framework versions named in the file and were checked against those packages' source; they are not run in CI, so if a framework changes its entry points, the file header says which version they match.

| File | Framework | What it shows |
| --- | --- | --- |
| `livekit_agent.py` | LiveKit Agents 1.8+ (Python) | `tts_text_transforms=[speechready.integrations.livekit.text_transform(...)]` on an `AgentSession`; `console` mode talks from the terminal. |
| `livekit_agent.mjs` | LiveKit Agents 1.9+ (Node) | The same with `speechready/livekit`, which returns the `ReadableStream` transform the SDK chains. |
| `pipecat_bot.py` | Pipecat 1.15+ | `text_transforms=[("sentence", speechready.integrations.pipecat.text_transform(...))]` on the ElevenLabs TTS service, served to a browser at `localhost:7860`. |
| `lexicon.en.yaml` | any | A pronunciation lexicon with `ipa`, `say` and `spell` entries, for `Lexicon.load()` or `prepare(..., lexicon="examples/lexicon.en.yaml")`. |

Two details the examples get right that are easy to miss:

- **ElevenLabs needs SSML parsing turned on** (`enable_ssml_parsing=True` / `enableSsmlParsing: true`) or the `<break>` tags speechready writes for `[pause 1s]` are read aloud as text. Azure, Google and Polly take SSML as a matter of course; OpenAI, Cartesia and Deepgram get punctuation instead, so nothing to enable.
- **Register the Pipecat transform on the TTS service**, not on `LLMTextProcessor`: transforms there also change what goes into the conversation context and to the client.

For Turkish, pass `locale="tr-TR"` and, for developer vocabulary, `lexicon="tr-tech"`, the bundled lexicon that reads `API` as "ey pi ay" and `JSON` as "ceyson".
