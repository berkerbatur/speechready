// A LiveKit Agents (Node) voice assistant with speechready between the LLM and the TTS.
//
// Install (@livekit/agents 1.9 or newer, Node 20+):
//
//     npm install @livekit/agents @livekit/agents-plugin-openai @livekit/agents-plugin-deepgram \
//                 @livekit/agents-plugin-elevenlabs @livekit/agents-plugin-silero speechready dotenv
//
// Environment, in a .env file next to this script or exported:
//
//     LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
//     OPENAI_API_KEY, DEEPGRAM_API_KEY, ELEVEN_API_KEY
//
// Run:
//
//     node livekit_agent.mjs console    // talk to it from this terminal; no room needed
//     node livekit_agent.mjs dev        // register with your LiveKit project and join rooms
//
// `textTransform` returns the `(ReadableStream<string>) => ReadableStream<string>` the SDK
// chains in `ttsTextTransforms`; it replaces the default markdown and emoji filters.

import "dotenv/config";
import { fileURLToPath } from "node:url";
import { ServerOptions, cli, defineAgent, voice } from "@livekit/agents";
import * as deepgram from "@livekit/agents-plugin-deepgram";
import * as elevenlabs from "@livekit/agents-plugin-elevenlabs";
import * as openai from "@livekit/agents-plugin-openai";
import * as silero from "@livekit/agents-plugin-silero";
import { textTransform } from "speechready/livekit";

const PROVIDER = "elevenlabs";
const MODEL = "eleven_turbo_v2_5";

export default defineAgent({
  entry: async (ctx) => {
    const session = new voice.AgentSession({
      stt: new deepgram.STT({ model: "nova-3" }),
      llm: new openai.LLM({ model: "gpt-4.1-mini" }),
      // enableSsmlParsing lets ElevenLabs honour the <break> tags speechready writes for [pause ...].
      tts: new elevenlabs.TTS({ model: MODEL, enableSsmlParsing: true }),
      vad: await silero.VAD.load(),
      ttsTextTransforms: [textTransform({ provider: PROVIDER, model: MODEL, locale: "en-US" })],
    });
    await session.start({
      agent: new voice.Agent({ instructions: "You are a concise voice assistant. Answer in a few short sentences." }),
      room: ctx.room,
    });
    await session.generateReply({ instructions: "Greet the user and ask how you can help." });
  },
});

cli.runApp(new ServerOptions({ agent: fileURLToPath(import.meta.url) }));
