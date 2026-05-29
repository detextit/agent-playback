---
name: agent-trace-audio
description: Create a personalized local audio briefing that explains an agent's working trace. Use when a user asks for agent playback, an audio summary, spoken report, NotebookLM-style recap, trace narration, conversation playback, coding-session debrief, local MP3, or wants to understand what a long-running agent did without rereading the whole conversation.
---

# Agent Trace Audio

Use this skill to turn a long-running agent trace into a local audio file the user can play. The result should feel like a concise audio report: one voice anchors the update, another explains the work done, and the conversation stays concrete and faithful to what happened.

## Requirements

- `OPENAI_API_KEY` must be set in the shell environment.
- The default implementation uses the OpenAI Speech API with `gpt-4o-mini-tts`.
- The CLI sends only each approved briefing segment to text-to-speech when using `speak`.
- `ffmpeg` is needed only when combining multiple MP3 segments cleanly. If `ffmpeg` is unavailable, the CLI writes a simple byte-concatenated MP3 fallback.
- Run `npm install` only when using the optional Realtime WebSocket engine, because the helper needs the `ws` package.

## Workflow

1. Gather the trace.
   - Prefer the agent's current working context and tool history to produce a short narration script yourself.
   - Do not send a saved Codex session JSONL or raw workspace trace to an external API unless the user explicitly approves that export.
   - Do not include secrets, raw API keys, tokens, or unrelated private content.

2. Write an inspectable script JSON locally. Use this shape:

```json
{
  "title": "short title",
  "listener": "you",
  "project": "agent-playback",
  "duration_target_seconds": 90,
  "briefing": [
    {"speaker": "host", "text": "Brief opening line."},
    {"speaker": "analyst", "text": "Concrete summary of the work, verification, and remaining risk."}
  ],
  "coverage_notes": ["facts intentionally covered"]
}
```

3. Synthesize audio from that script:

```bash
python3 scripts/trace_audio.py speak \
  --script out/trace-audio/trace_audio_script.json \
  --out-dir out/trace-audio \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 90 \
  --segment-concurrency 4
```

This sends only the spoken briefing segment text to the audio API. It does not send the raw trace.

4. Use trace-backed drafting only with explicit approval.
   - When approved, `--trace-session latest` reads the newest session under `~/.codex/sessions`, or an explicit `~/.codex/sessions/.../*.jsonl` path.
   - The CLI converts Codex session JSONL into a transcript and skips bulky system/developer metadata, so the script model sees the actual user messages, assistant messages, tool calls, and tool outputs.
   - If the user provides a separate trace file, pass it with `--trace`.
   - Do not include secrets, raw API keys, tokens, or unrelated private content.

Trace-backed command:

```bash
python3 scripts/trace_audio.py run \
  --trace-session latest \
  --out-dir out/trace-audio \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 90 \
  --trace-mode compact \
  --trace-budget-chars 8000 \
  --max-segments 4 \
  --segment-concurrency 4
```

If the trace is already saved as markdown, use `--trace tmp/agent-trace.md`. If you know the exact Codex session path, either use `--trace-session /path/to/session.jsonl` or pass the JSONL file with `--trace`.

Use Realtime only when you specifically need live-session behavior rather than script-to-audio synthesis:

```bash
python3 scripts/trace_audio.py run \
  --trace-session latest \
  --out-dir out/trace-audio \
  --audio-engine realtime
```

5. Report the outputs:
   - `trace_audio.mp3`: final audio file
   - `trace_audio_script.json`: generated briefing script

Use `--keep-intermediates` only when debugging segment-level audio.

For long traces, prefer compact mode. It keeps the opening goal, salient events such as file changes/tests/errors, and the ending state, while avoiding the latency and cost of sending an entire raw transcript.

## Briefing Shape

Ask for a spoken briefing that feels useful, lively, and operational, not like a generic meeting summary or podcast segment. The best output:

- starts with a direct report of the goal and outcome, not a question or the listener's name
- names the user's goal and the project
- explains the important decisions and why they were made
- separates completed work from attempted or blocked work
- mentions verification, test results, and residual risk
- avoids dumping low-level logs unless they explain an outcome
- uses a report rhythm: short framing from the host, substantive updates from the engineer
- ends with concrete next steps or a satisfying wrap-up

## Useful Commands

Draft only:

```bash
python3 scripts/trace_audio.py draft --trace-session latest --out-dir out/trace-audio
```

Requires explicit approval to send the trace-derived prompt to the script model.

Synthesize a previously drafted script:

```bash
python3 scripts/trace_audio.py speak --script out/trace-audio/trace_audio_script.json --out-dir out/trace-audio
```
