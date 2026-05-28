# Evals

Run the sample eval:

```bash
npm install
python3 scripts/trace_audio.py dev-run \
  --trace evals/fixtures/sample_trace.md \
  --out-dir out/sample-eval \
  --listener "you" \
  --project "agent-playback" \
  --duration-seconds 45 \
  --min-iterations 2 \
  --iterations 2
```

Artifacts:

- `trace_audio.mp3`: synthesized local audio
- `trace_audio_script.json`: generated two-speaker script
- `trace_audio_transcript.txt`: speech-to-text transcript of the audio
- `trace_audio_eval.json`: LLM judge result

The judge is intentionally strict about report structure and boundaries. A passing result needs a direct report opening, substantive work detail, and mention of failures, skipped checks, residual risks, or setup limits when the trace includes them.
