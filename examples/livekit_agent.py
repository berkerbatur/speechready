"""A LiveKit Agents voice assistant with speechready between the LLM and the TTS.

Install (livekit-agents 1.8 or newer):

    pip install "livekit-agents[openai,deepgram,elevenlabs,silero]~=1.8" speechready python-dotenv

Environment, in a .env file next to this script or exported:

    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET   # a LiveKit Cloud project or your own server
    OPENAI_API_KEY, DEEPGRAM_API_KEY, ELEVEN_API_KEY

Run:

    python livekit_agent.py console    # talk to it from this terminal; no room needed
    python livekit_agent.py dev        # register with your LiveKit project and join rooms

What speechready adds: LiveKit's default transforms strip markdown and emoji. This
one replaces them with the full pipeline, so numbers, dates, prices and phone numbers
are written out, [pause 1s] becomes an ElevenLabs break tag, and a fenced code block
is dropped (or mentioned) as one piece instead of being read line by line.
"""

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import deepgram, elevenlabs, openai, silero

from speechready.integrations import livekit as speechready_livekit

load_dotenv()

PROVIDER = "elevenlabs"
MODEL = "eleven_turbo_v2_5"

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        # enable_ssml_parsing lets ElevenLabs honour the <break> tags speechready writes for [pause ...].
        tts=elevenlabs.TTS(model=MODEL, enable_ssml_parsing=True),
        vad=silero.VAD.load(),
        # Sentences are released as the token stream confirms them, each prepared for this provider.
        tts_text_transforms=[speechready_livekit.text_transform(provider=PROVIDER, model=MODEL, locale="en-US")],
    )
    await session.start(
        agent=Agent(instructions="You are a concise voice assistant. Answer in a few short sentences."),
        room=ctx.room,
    )
    await session.generate_reply(instructions="Greet the user and ask how you can help.")


if __name__ == "__main__":
    cli.run_app(server)
