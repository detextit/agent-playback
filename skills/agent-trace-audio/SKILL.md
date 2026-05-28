---
name: agent-trace-audio
description: Create a personalized local audio briefing that explains an agent's working trace. Use when a user asks for agent playback, an audio summary, spoken report, NotebookLM-style recap, trace narration, conversation playback, coding-session debrief, local MP3, or wants to understand what a long-running agent did without rereading the whole conversation.
---

# Agent Trace Audio

Use this skill to turn a long-running agent trace into a local audio file the user can play. The result should feel like a short standup checkpoint: one voice asks focused questions, another explains the work done, and the conversation stays concrete and faithful to what happened.

## Requirements

- `OPENAI_API_KEY` must be set in the shell environment.
- Run `npm install` once from the plugin root so the Realtime WebSocket helper can use the `ws` package.
- The default implementation uses the OpenAI Realtime API with `gpt-realtime-2`. It connects over WebSocket, listens for `response.output_audio.delta`, buffers `pcm16` chunks, and converts them to MP3 locally.
- The CLI uses `gpt-realtime-2` for speech.
- `ffmpeg` is required for the default Realtime path because Realtime emits raw PCM audio that must be converted to MP3. With `--audio-engine speech`, `ffmpeg` is only needed when combining multiple MP3 segments cleanly.

## Workflow

1. Gather the trace.
   - Prefer the current conversation and terminal actions if the user says "this run" or "this thread".
   - Include concrete file paths, commands, tests, failures, decisions, and unresolved risks.
   - Do not include secrets, raw API keys, tokens, or unrelated private content.
2. Save the trace as a markdown file when running locally, for example:

```bash
mkdir -p tmp
$EDITOR tmp/agent-trace.md
```

3. Generate audio:

```bash
python3 scripts/trace_audio.py run \
  --trace tmp/agent-trace.md \
  --out-dir out/trace-audio \
  --listener "Sarath" \
  --project "agent-playback" \
  --duration-seconds 90 \
  --trace-mode compact \
  --trace-budget-chars 8000 \
  --max-segments 4 \
  --segment-concurrency 4
```

Use the request-based Speech API fallback only when Realtime is unavailable:

```bash
python3 scripts/trace_audio.py run \
  --trace tmp/agent-trace.md \
  --out-dir out/trace-audio \
  --audio-engine speech
```

4. Report the outputs:
   - `trace_audio.mp3`: final audio file
   - `trace_audio_script.json`: generated briefing script

Use `--keep-intermediates` only when debugging segment-level audio.

For long traces, prefer compact mode. It keeps the opening goal, salient events such as file changes/tests/errors, and the ending state, while avoiding the latency and cost of sending an entire raw transcript.

## Briefing Shape

Ask for a spoken briefing that feels personal, lively, and operational, not like a generic meeting summary or podcast segment. The best output:

- starts with a direct question about what happened
- names the user's goal and the project
- explains the important decisions and why they were made
- separates completed work from attempted or blocked work
- mentions verification, test results, and residual risk
- avoids dumping low-level logs unless they explain an outcome
- uses a standup rhythm: short questions from the lead, substantive answers from the engineer
- ends with concrete next steps or a satisfying wrap-up

## Useful Commands

Draft only:

```bash
python3 scripts/trace_audio.py draft --trace tmp/agent-trace.md --out-dir out/trace-audio
```

Synthesize a previously drafted script:

```bash
python3 scripts/trace_audio.py speak --script out/trace-audio/trace_audio_script.json --out-dir out/trace-audio
```
