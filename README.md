# Agent Playback

Agent Playback is a Codex plugin that turns a long-running coding-agent trace into a personalized local audio briefing. It is for the moment when an agent has been working for 20 minutes, the chat is huge, and you want to press play instead of excavating the conversation.

Think NotebookLM for agent traces, shaped like an audio report: one voice anchors the update and the other explains the goal, what changed, what was tested, what failed, and what still needs attention. The plugin uses the OpenAI Speech API with `gpt-4o-mini-tts` by default and writes a playable MP3 locally.

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

Privacy-first command: `python3 scripts/trace_audio.py speak`

For a current Codex run, the safest workflow is for the Codex agent to read its own working context, write an inspectable `trace_audio_script.json`, and then call `speak`. That sends only the narrated audio script to the audio API, not the raw Codex session trace.

Use `python3 scripts/trace_audio.py run --trace-session latest` only after explicit approval to export trace-derived content. That path reads the saved JSONL transcript from `~/.codex/sessions`, compacts it, and sends the compacted trace to the script model before synthesizing audio.

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
- Python 3.10+
- `ffmpeg` is recommended for cleanly combining multi-segment MP3s
- Node.js is needed only for the optional Realtime engine

Install the WebSocket helper dependency only if you plan to use `--audio-engine realtime`:

```bash
npm install
```

Generate a local briefing from an agent-authored script:

```json
{
  "title": "Agent Playback Report",
  "listener": "you",
  "project": "agent-playback",
  "duration_target_seconds": 45,
  "briefing": [
    {"speaker": "host", "text": "Here is the report on the agent playback work."},
    {"speaker": "analyst", "text": "The agent updated the plugin flow, verified the relevant commands, and left the remaining risks clear."}
  ],
  "coverage_notes": ["goal", "changes", "verification", "remaining risk"]
}
```

Save that JSON to `out/sample-audio/trace_audio_script.json`, then run:

```bash
python3 scripts/trace_audio.py speak \
  --script out/sample-audio/trace_audio_script.json \
  --out-dir out/sample-audio \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 45 \
  --segment-concurrency 4
```

Generate a local briefing from an approved trace export:

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
- Privacy-first audio: `speak` works from a reviewed script, so the audio API receives only the narration text.
- Full local traces: with explicit approval, `--trace-session latest` reads saved Codex sessions from disk, so the briefing can cover the complete transcript rather than the agent's compacted summary.
- Fast on long traces: compact mode preserves the opening goal, important events, and final state instead of sending a giant raw transcript.
- Local artifacts: the user gets an MP3 they can replay, share, or archive.
- Faithful by design: prompts emphasize changed files, commands, tests, blockers, risks, and next steps.
- Report-style by default: the host frames the update, the engineer gives the substantive detail, and the script avoids forced questions, name-drop openings, and podcast banter.

## Model Choices

For local file output, Agent Playback defaults to the OpenAI Speech API with `gpt-4o-mini-tts`. This keeps the audio step narrow: after a script is drafted or written locally, the API receives only the spoken segment text.

Realtime remains available with `--audio-engine realtime` for live-session behavior. That path uses the Realtime API with `gpt-realtime-2`, connects over WebSocket, buffers `response.output_audio.delta` chunks, writes 24 kHz PCM, and converts the audio to MP3 locally with `ffmpeg`.

## Long Trace Performance

Long traces are slow for two reasons: the script model has to read the trace context, and audio generation has to synthesize each spoken segment. The CLI optimizes both:

- `--trace-mode compact` preserves the beginning, salient events, and ending instead of sending a raw tail slice.
- `--trace-budget-chars 8000` is a good fast default for very long traces; increase it when fidelity needs more context.
- `--max-segments 4` caps synthesized speech segments.
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

This sends trace-derived content to the script model and should be used only when that export is approved.

Synthesize an existing script:

```bash
python3 scripts/trace_audio.py speak \
  --script out/trace-audio/trace_audio_script.json \
  --out-dir out/trace-audio
```

Optional Realtime synthesis:

```bash
python3 scripts/trace_audio.py run \
  --trace-session latest \
  --out-dir out/trace-audio \
  --audio-engine realtime
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
