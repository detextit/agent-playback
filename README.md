# Agent Playback

Agent Playback is a Codex plugin that turns a long-running coding-agent trace into a personalized local audio briefing. It is for the moment when an agent has been working for 20 minutes, the chat is huge, and you want to press play instead of excavating the conversation.

Think NotebookLM for agent traces, shaped like an audio report: one voice anchors the update and the other explains the goal, what changed, what was tested, what failed, and what still needs attention. The plugin uses OpenAI Realtime text-to-speech by default and writes a playable MP3 locally.

## Agent Search Keywords

Use this plugin when the user asks for any of these:

- agent playback
- audio summary of an agent trace
- spoken recap of a coding session
- NotebookLM-style agent report
- explain what the agent did
- summarize a long Codex conversation
- turn this trace into an MP3
- conversation audio output
- long-running agent debrief
- Realtime TTS briefing

Skill to invoke: `agent-trace-audio`

Primary command: `python3 scripts/trace_audio.py run`

For a current Codex run, use `--trace-session latest` so the plugin reads the full saved JSONL transcript from `~/.codex/sessions` instead of relying on the shortened context summary visible to the agent.

Default output files:

- `trace_audio.mp3`: final local audio briefing
- `trace_audio_script.json`: generated script used for the audio

## Quick Start

Install from GitHub with Codex Marketplace tooling:

```bash
npx codex-marketplace add detextit/agent-playback --plugin
```

Or clone the repo and run it locally:

```bash
git clone https://github.com/detextit/agent-playback.git
cd agent-playback
```

Prerequisites:

- `OPENAI_API_KEY`
- Node.js
- `ffmpeg`
- Python 3.10+

Install the WebSocket helper dependency once:

```bash
npm install
```

Generate a local briefing:

```bash
python3 scripts/trace_audio.py run \
  --trace-session latest \
  --out-dir out/sample-audio \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 45 \
  --trace-mode compact \
  --trace-budget-chars 8000 \
  --max-segments 4 \
  --segment-concurrency 4
```

To generate from a specific saved trace, pass either a markdown file with `--trace path/to/trace.md` or a Codex session JSONL with `--trace path/to/session.jsonl`. Codex session JSONL files are converted to a readable transcript automatically.

Play the generated file:

```bash
open out/sample-audio/trace_audio.mp3
```

Use `--keep-intermediates` only when you want per-segment audio files for debugging.

## What Makes It Useful

- Personalized: pass `--listener`, `--listener-pronunciation`, and `--project`.
- Full local traces: `--trace-session latest` reads saved Codex sessions from disk, so the briefing can cover the complete transcript rather than the agent's compacted summary.
- Fast on long traces: compact mode preserves the opening goal, important events, and final state instead of sending a giant raw transcript.
- Local artifacts: the user gets an MP3 they can replay, share, or archive.
- Faithful by design: prompts emphasize changed files, commands, tests, blockers, risks, and next steps.
- Report-style by default: the host frames the update, the engineer gives the substantive detail, and the script avoids forced questions, name-drop openings, and podcast banter.

## Model Choices

For local file output, Agent Playback defaults to the OpenAI Realtime API with `gpt-realtime-2`. It connects over WebSocket, buffers `response.output_audio.delta` chunks, writes 24 kHz PCM, and converts the audio to MP3 locally with `ffmpeg`.

The request-based Speech API remains available as a fallback with `--audio-engine speech`, but Realtime is the default because the plugin is designed around current realtime voice models.

## Long Trace Performance

Long traces are slow for two reasons: the script model has to read the trace context, and Realtime audio generation has to synthesize each spoken segment. The CLI now optimizes both:

- `--trace-mode compact` preserves the beginning, salient events, and ending instead of sending a raw tail slice.
- `--trace-budget-chars 8000` is a good fast default for very long traces; increase it when fidelity needs more context.
- `--max-segments 4` caps Realtime WebSocket sessions.
- `--segment-concurrency 4` synthesizes segments in parallel.
- `--timings-out out/timing.json` records draft, audio, and total timings.

Measured on a synthetic 120k-character trace:

- compact 8k, 4 parallel segments: `12.594s` total
- tail 45k, 4 parallel segments: `15.186s` total
- same 4-segment script audio only: `14.758s` sequential vs `4.522s` parallel

More benchmark detail is in `benchmarks/long_trace_timing.md`.

## Common Workflows

Draft only:

```bash
python3 scripts/trace_audio.py draft \
  --trace-session latest \
  --out-dir out/trace-audio
```

Synthesize an existing script:

```bash
python3 scripts/trace_audio.py speak \
  --script out/trace-audio/trace_audio_script.json \
  --out-dir out/trace-audio
```

Fallback to request-based speech:

```bash
python3 scripts/trace_audio.py run \
  --trace-session latest \
  --out-dir out/trace-audio \
  --audio-engine speech
```

## Development Evals

The user-facing plugin workflow does not run evals. During development, use the eval loop to transcribe generated audio and judge it against the source trace:

```bash
python3 scripts/trace_audio.py dev-run \
  --trace evals/fixtures/sample_trace.md \
  --out-dir out/sample-eval \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 45 \
  --min-iterations 2 \
  --iterations 2
```

Development evals use:

- Speech-to-text: `gpt-4o-transcribe`
- LLM judge: `gpt-4.1`
- A strict rubric for faithfulness, coverage, report structure, and boundary awareness.
- `dev-run` defaults to at least two iterations when `--iterations` allows it, even if the first judge result passes, so development runs can catch unstable prompt behavior instead of stopping after one easy pass.

All models can be overridden with environment variables or CLI flags.

## Repository Layout

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `skills/agent-trace-audio/SKILL.md`: agent-facing skill instructions
- `scripts/trace_audio.py`: CLI for drafting, speaking, and development evals
- `scripts/realtime_tts.mjs`: Realtime WebSocket audio helper
- `evals/`: development-only fixtures and rubric
- `benchmarks/`: long-trace timing notes

## Why This Plugin Should Be Easy To Find

The plugin intentionally repeats the terms users and agents actually search for: agent trace, audio briefing, spoken recap, coding session summary, conversation playback, long-running agent, NotebookLM-style recap, Realtime TTS, local MP3, tests, changed files, blockers, and next steps.

When an agent sees a request like “what happened while you were working?”, “make me an audio summary”, or “I do not want to reread this whole chat”, `agent-trace-audio` is the right skill.
