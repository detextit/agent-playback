#!/usr/bin/env node
import fs from "node:fs";
import { WebSocket } from "ws";

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    args[key.slice(2)] = argv[i + 1];
    i += 1;
  }
  return args;
}

function requireArg(args, name) {
  if (!args[name]) {
    throw new Error(`missing --${name}`);
  }
  return args[name];
}

const args = parseArgs(process.argv.slice(2));
const apiKey = process.env.OPENAI_API_KEY;
if (!apiKey) {
  throw new Error("OPENAI_API_KEY is required.");
}

const model = requireArg(args, "model");
const voice = requireArg(args, "voice");
const instructions = requireArg(args, "instructions");
const text = requireArg(args, "text");
const outPath = requireArg(args, "out");
const transcriptOut = args["transcript-out"];
const baseUrl = (args.url || "wss://api.openai.com/v1/realtime").replace(/\/$/, "");
const url = `${baseUrl}?model=${encodeURIComponent(model)}`;

const audioChunks = [];
let transcript = "";
let done = false;

const ws = new WebSocket(url, {
  headers: {
    Authorization: `Bearer ${apiKey}`,
  },
});

const timeout = setTimeout(() => {
  ws.terminate();
  throw new Error("Timed out waiting for Realtime audio.");
}, 180000);

function send(payload) {
  ws.send(JSON.stringify(payload));
}

function startResponse() {
  send({
    type: "conversation.item.create",
    item: {
      type: "message",
      role: "user",
      content: [
        {
          type: "input_text",
          text,
        },
      ],
    },
  });
  send({
    type: "response.create",
    response: {
      output_modalities: ["audio"],
      instructions,
      audio: {
        output: {
          format: {
            type: "audio/pcm",
            rate: 24000,
          },
        },
      },
    },
  });
}

ws.on("open", () => {
  send({
    type: "session.update",
    session: {
      type: "realtime",
      instructions,
      output_modalities: ["audio"],
      reasoning: {
        effort: "low",
      },
      audio: {
        output: {
          voice,
          format: {
            type: "audio/pcm",
            rate: 24000,
          },
        },
      },
    },
  });
});

ws.on("message", (raw) => {
  const event = JSON.parse(raw.toString());
  if (event.type === "session.updated") {
    startResponse();
    return;
  }
  if (event.type === "response.output_audio.delta" || event.type === "response.audio.delta") {
    audioChunks.push(Buffer.from(event.delta, "base64"));
    return;
  }
  if (event.type === "response.output_audio_transcript.delta" || event.type === "response.audio_transcript.delta") {
    transcript += event.delta || "";
    return;
  }
  if (event.type === "response.done") {
    done = true;
    fs.mkdirSync(new URL(`file://${process.cwd()}/`).pathname, { recursive: true });
    fs.writeFileSync(outPath, Buffer.concat(audioChunks));
    if (transcriptOut) {
      fs.writeFileSync(transcriptOut, `${transcript.trim()}\n`);
    }
    clearTimeout(timeout);
    ws.close();
    return;
  }
  if (event.type === "error") {
    clearTimeout(timeout);
    ws.close();
    throw new Error(JSON.stringify(event.error || event));
  }
});

ws.on("close", () => {
  clearTimeout(timeout);
  if (!done) {
    process.exitCode = 1;
  }
});

ws.on("error", (error) => {
  clearTimeout(timeout);
  throw error;
});
