# Evals

Run the sample eval:

```bash
npm install
python3 scripts/trace_audio.py dev-run \
  --trace evals/fixtures/sample_trace.md \
  --out-dir out/sample-eval \
  --listener "Sarath" \
  --project "agent-playback" \
  --duration-seconds 45 \
  --iterations 2
```

Artifacts:

- `trace_audio.mp3`: synthesized local audio
- `trace_audio_script.json`: generated two-speaker script
- `trace_audio_transcript.txt`: speech-to-text transcript of the audio
- `trace_audio_eval.json`: LLM judge result
