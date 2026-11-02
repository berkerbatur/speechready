"""A Pipecat voice bot with speechready on the TTS service's text transforms.

Install (pipecat-ai 1.15 or newer):

    pip install "pipecat-ai[webrtc,runner,openai,deepgram,elevenlabs,silero]~=1.15" speechready python-dotenv

Environment, in a .env file next to this script or exported:

    OPENAI_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY

Run, then open http://localhost:7860 and press Connect:

    python pipecat_bot.py

Pipecat applies `text_transforms` to each sentence it aggregates, just before the TTS.
speechready's transform writes out numbers, dates, prices and phone numbers, compiles
[pause 1s] to an ElevenLabs break tag, and holds a code block that arrives split across
sentences until its closing fence so it can be dropped as one piece. Pipecat 1.14+ has
its own English transforms (strip_markdown, expand_numbers...); this one adds provider
dialects, Turkish and a pronunciation lexicon, and can sit alongside them.
"""

import os

from dotenv import load_dotenv
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from speechready.integrations import pipecat as speechready_pipecat

load_dotenv(override=True)

PROVIDER = "elevenlabs"
MODEL = "eleven_turbo_v2_5"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs premade voice "George"

transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4.1-mini")
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=VOICE_ID,
        model=MODEL,
        # enable_ssml_parsing lets ElevenLabs honour the <break> tags speechready writes for [pause ...].
        enable_ssml_parsing=True,
        # "sentence" is what the TTS aggregates by default; "*" would also cover token/word/expression pieces.
        text_transforms=[("sentence", speechready_pipecat.text_transform(provider=PROVIDER, model=MODEL, locale="en-US"))],
    )

    context = LLMContext(
        [{"role": "system", "content": "You are a concise voice assistant. Answer in a few short sentences."}]
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True, enable_usage_metrics=True))
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        context.add_message({"role": "developer", "content": "Greet the user and ask how you can help."})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments) -> None:
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
