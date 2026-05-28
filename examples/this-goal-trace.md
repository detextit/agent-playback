# This Goal Run Trace

User goal:

Create a Codex plugin with a skill that generates a personalized conversation-style audio output explaining an agent's working trace. The plugin should address the pain of users needing to dig through long chats after coding agents or other long-running agents have been working for a while. The output should be a local audio file. The work should include evals using speech-to-text and an LLM judge to iterate on the speech synthesis prompt. The plugin should be tested on this goal run.

Repository state:

- Working directory: `/Users/sarath/Github/misc/report-plugin`
- The directory was empty and was not a Git repository.
- The plugin is named `agent-playback` to match the GitHub repository and public package identity.

Official docs consulted:

- OpenAI Realtime and audio guide: the latest realtime voice-agent path uses `gpt-realtime-2`; server-to-server Realtime integrations can use WebSockets.
- OpenAI Realtime conversations guide: server-side apps can buffer `response.output_audio.delta` chunks and write them to a file.
- OpenAI Realtime WebSocket guide: connect to `wss://api.openai.com/v1/realtime?model=gpt-realtime-2` with an API key.
- OpenAI Speech to text guide: file transcription supports `gpt-4o-transcribe` for bounded audio files.

Files created or changed:

- `.codex-plugin/plugin.json`: updated plugin metadata for Agent Playback.
- `skills/agent-trace-audio/SKILL.md`: added the Codex skill workflow for trace audio briefings.
- `scripts/trace_audio.py`: added a CLI that drafts a two-speaker briefing, synthesizes MP3 audio, transcribes it, judges it, and iterates when needed.
- `scripts/realtime_tts.mjs`: added a Realtime WebSocket helper that uses `gpt-realtime-2`, buffers `response.output_audio.delta`, and writes PCM audio for local MP3 conversion.
- `package.json` and `package-lock.json`: added the `ws` dependency for server-to-server Realtime WebSocket access.
- `evals/fixtures/sample_trace.md`: added a sample agent trace.
- `evals/rubric.md`: added the eval rubric.
- `evals/README.md`: documented the sample eval command.
- `tests/test_trace_audio.py`: added unit tests for JSON parsing, script validation, and prompt construction.
- `README.md`: documented the plugin and quick start.
- `.gitignore`: ignored local output and cache files.

Implementation decisions:

- Updated the default audio engine to the latest Realtime voice model, `gpt-realtime-2`, after the user challenged the initial request-based Speech API choice.
- Kept `--audio-engine speech` as an explicit fallback, but Realtime is now the default.
- Used a two-speaker script format with `host` and `analyst` segments. Each segment opens a Realtime WebSocket session with the requested voice, writes `audio/pcm` at 24 kHz, converts to MP3 with `ffmpeg`, then concatenates segments.
- Added environment and CLI overrides for script, judge, Realtime, fallback TTS, STT, and voice models.
- The normal plugin workflow now only drafts and synthesizes audio. The eval loop remains available through `dev-run` for development.

Verification completed:

- `python3 -m unittest discover -s tests` passed.
- `python3 -m py_compile scripts/trace_audio.py tests/test_trace_audio.py` passed.
- `node --check scripts/realtime_tts.mjs` passed.
- The plugin validator initially failed because the local system Python lacked `PyYAML`.
- A throwaway virtualenv at `/tmp/report-plugin-validate-venv` was created, `PyYAML` was installed there, and plugin validation passed with `/Users/sarath/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py`.
- A live end-to-end run was executed with `python3 scripts/trace_audio.py run --trace examples/this-goal-trace.md --out-dir out/this-goal-run --listener Sarath --project agent-playback --duration-seconds 45`.
- The normal live run produced `out/this-goal-run/trace_audio.mp3` and `trace_audio_script.json`.
- The first live judge result passed on iteration 1 with scores of 5 for faithfulness, coverage, clarity, personalization, and actionability.
- A live Realtime end-to-end run was executed with `python3 scripts/trace_audio.py run --trace examples/this-goal-trace.md --out-dir out/this-goal-run-realtime --listener 'you' --project agent-playback --duration-seconds 35`.
- The Realtime run produced `out/this-goal-run-realtime/trace_audio.mp3` and `trace_audio_script.json`.
- The Realtime judge result passed on iteration 1 with scores of 5 for faithfulness, coverage, clarity, personalization, and actionability.

Residual risk:

- The plugin can now read saved Codex session JSONL files from `~/.codex/sessions` with `--trace-session latest`, but users should pass an explicit session path when multiple Codex sessions are active.
- The generated audio quality depends on access to the configured OpenAI models and on the completeness of the trace the agent provides.
