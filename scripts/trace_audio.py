#!/usr/bin/env python3
"""Generate local audio briefings for agent traces."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
DEFAULT_SCRIPT_MODEL = os.environ.get("TRACECAST_SCRIPT_MODEL", "gpt-4.1-mini")
DEFAULT_JUDGE_MODEL = os.environ.get("TRACECAST_JUDGE_MODEL", "gpt-4.1")
DEFAULT_AUDIO_ENGINE = os.environ.get("TRACECAST_AUDIO_ENGINE", "realtime")
DEFAULT_REALTIME_MODEL = os.environ.get("TRACECAST_REALTIME_MODEL", "gpt-realtime-2")
DEFAULT_TTS_MODEL = os.environ.get("TRACECAST_TTS_MODEL", "gpt-4o-mini-tts")
DEFAULT_STT_MODEL = os.environ.get("TRACECAST_STT_MODEL", "gpt-4o-transcribe")
DEFAULT_HOST_VOICE = os.environ.get("TRACECAST_HOST_VOICE", "marin")
DEFAULT_ANALYST_VOICE = os.environ.get("TRACECAST_ANALYST_VOICE", "cedar")
MAX_TRACE_CHARS = int(os.environ.get("TRACECAST_MAX_TRACE_CHARS", "12000"))
IMPORTANT_TRACE_RE = re.compile(
    r"("
    r"\berror\b|\bfailed\b|\bfail\b|\bpassed\b|\bpass\b|\btest\b|\blint\b|"
    r"\bcreated\b|\bupdated\b|\bdeleted\b|\bchanged\b|\bimplemented\b|"
    r"\bblocked\b|\brisk\b|\bTODO\b|\bfix\b|\bbug\b|"
    r"`[^`]+`|\b[A-Za-z0-9_./-]+\.(py|js|ts|tsx|jsx|json|md|toml|yaml|yml)\b|"
    r"\b(npm|pnpm|yarn|python3?|pytest|uv|cargo|go|git|node|ffmpeg)\b"
    r")",
    re.IGNORECASE,
)


def require_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required.")
    return api_key


def read_text(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now() -> float:
    return time.perf_counter()


def summarize_elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def http_json(api_key: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API request failed ({exc.code}): {detail}") from exc


def http_binary(api_key: str, url: str, payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI audio request failed ({exc.code}): {detail}") from exc


def http_multipart(
    api_key: str,
    url: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
) -> str:
    boundary = f"----tracecast-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI multipart request failed ({exc.code}): {detail}") from exc
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and isinstance(payload.get("text"), str):
            return payload["text"]
    except json.JSONDecodeError:
        pass
    return text


def response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    pieces: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                pieces.append(content["text"])
    return "\n".join(pieces).strip()


def parse_json_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def compact_trace(trace: str, budget_chars: int, mode: str) -> str:
    if budget_chars <= 0 or len(trace) <= budget_chars:
        return trace
    if mode == "tail":
        return trace[-budget_chars:]

    lines = trace.splitlines()
    head_budget = max(1200, budget_chars // 5)
    tail_budget = max(2500, budget_chars // 2)
    head = trace[:head_budget]
    tail = trace[-tail_budget:]

    important: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        if IMPORTANT_TRACE_RE.search(stripped):
            important.append(stripped)
            seen.add(stripped)

    remaining = max(0, budget_chars - len(head) - len(tail) - 500)
    middle = "\n".join(important)
    if len(middle) > remaining:
        middle = middle[-remaining:]

    compacted = (
        "Trace compacted for audio briefing. Preserved beginning, salient events, and ending.\n\n"
        "BEGINNING:\n"
        f"{head}\n\n"
        "SALIENT EVENTS:\n"
        f"{middle}\n\n"
        "ENDING:\n"
        f"{tail}"
    )
    return compacted[-budget_chars:]


def prepare_trace(args: argparse.Namespace, trace: str) -> str:
    return compact_trace(trace, args.trace_budget_chars, args.trace_mode)


def build_draft_prompt(args: argparse.Namespace, trace: str, feedback: str = "") -> str:
    trace = prepare_trace(args, trace)
    feedback_block = f"\nPrevious eval feedback to address:\n{feedback}\n" if feedback else ""
    pronunciation = (
        f"\nListener pronunciation: {args.listener_pronunciation}"
        if args.listener_pronunciation
        else ""
    )
    return f"""
Create a concise audio briefing script for an agent working trace.

Listener: {args.listener}
Project: {args.project}
Target duration: {args.duration_seconds} seconds
Mode: two-speaker conversational briefing
{pronunciation}

Return only JSON with this shape:
{{
  "title": "short title",
  "listener": "listener name",
  "project": "project name",
  "duration_target_seconds": 90,
  "briefing": [
    {{"speaker": "host", "text": "spoken line"}},
    {{"speaker": "analyst", "text": "spoken line"}}
  ],
  "coverage_notes": ["facts intentionally covered"]
}}

Rules:
- Use at most {args.max_segments} briefing segments total.
- Open with a sharp, inviting hook about the work. Do not start with "this is AI-generated" or any compliance-style disclaimer.
- Explain what the user asked for, what the agent did, what changed, what was tested, and what remains.
- Be faithful to the trace. Do not invent completed work, files, test results, or external facts.
- Make it personal to the listener and project.
- Make the format fun and attractive: crisp podcast energy, tasteful back-and-forth, vivid phrasing, and a satisfying wrap-up. Avoid being goofy, theatrical, or salesy.
- The Listener field is the only approved spoken listener label. If Listener is "the user" or "you", do not infer or say a personal name from the trace.
- Use natural speech. Avoid markdown, bullets, code fences, and long file dumps in spoken lines.
- Include concrete file names and commands only when they matter to understanding the outcome.
- Do not infer that multiple eval iterations ran from a command's `--iterations` limit. Only state an iteration count when the trace reports the actual result.
- End with next steps or residual risk.
- Keep the combined script close to the target duration.
{feedback_block}
Trace:
{trace}
""".strip()


def draft_script(args: argparse.Namespace, trace: str, feedback: str = "") -> dict[str, Any]:
    api_key = require_api_key()
    payload = http_json(
        api_key,
        f"{API_BASE}/responses",
        {
            "model": args.script_model,
            "instructions": (
                "You turn coding-agent work traces into accurate, compact, spoken audio "
                "briefings. You optimize for faithfulness, listener usefulness, and "
                "a lively, polished, podcast-like delivery."
            ),
            "input": build_draft_prompt(args, trace, feedback),
            "temperature": 0.4,
        },
    )
    script = parse_json_text(response_text(payload))
    validate_script(script)
    if len(script["briefing"]) > args.max_segments:
        script["briefing"] = script["briefing"][: args.max_segments]
    return script


def validate_script(script: dict[str, Any]) -> None:
    briefing = script.get("briefing")
    if not isinstance(briefing, list) or not briefing:
        raise ValueError("script JSON must include a non-empty briefing array.")
    for index, segment in enumerate(briefing):
        if not isinstance(segment, dict):
            raise ValueError(f"briefing[{index}] must be an object.")
        if segment.get("speaker") not in {"host", "analyst"}:
            raise ValueError(f"briefing[{index}].speaker must be host or analyst.")
        if not isinstance(segment.get("text"), str) or not segment["text"].strip():
            raise ValueError(f"briefing[{index}].text must be non-empty.")


def voice_for_segment(segment: dict[str, str], args: argparse.Namespace) -> str:
    return args.host_voice if segment["speaker"] == "host" else args.analyst_voice


def instructions_for_segment(segment: dict[str, str], args: argparse.Namespace) -> str:
    pronunciation = ""
    if args.listener_pronunciation:
        pronunciation = (
            f" If saying the listener name {args.listener}, pronounce it as "
            f"{args.listener_pronunciation}."
        )
    if segment["speaker"] == "host":
        return (
            "Sound like a polished tech podcast host: bright, warm, curious, and crisp. "
            "Keep the energy attractive and modern without sounding like an ad." + pronunciation
        )
    return (
        "Sound like a sharp senior engineer co-host: concrete, lightly witty, and easy "
        "to follow. Bring momentum, but keep the facts precise." + pronunciation
    )


def synthesize_segment_speech_api(api_key: str, text: str, voice: str, instructions: str, path: Path, args: argparse.Namespace) -> None:
    audio = http_binary(
        api_key,
        f"{API_BASE}/audio/speech",
        {
            "model": args.tts_model,
            "voice": voice,
            "input": text,
            "instructions": instructions,
            "response_format": "mp3",
        },
    )
    path.write_bytes(audio)


def convert_pcm_to_mp3(pcm_path: Path, mp3_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to convert Realtime pcm16 output to MP3.")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "s16le",
            "-ar",
            "24000",
            "-ac",
            "1",
            "-i",
            str(pcm_path),
            str(mp3_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def synthesize_segment_realtime(text: str, voice: str, instructions: str, path: Path, args: argparse.Namespace) -> None:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for Realtime WebSocket audio generation.")
    pcm_path = path.with_suffix(".pcm")
    transcript_path = path.with_suffix(".realtime_transcript.txt")
    script_path = Path(__file__).with_name("realtime_tts.mjs")
    if not script_path.is_file():
        raise RuntimeError(f"missing Realtime helper script: {script_path}")
    realtime_url = os.environ.get(
        "OPENAI_REALTIME_URL",
        f"{API_BASE.replace('https://', 'wss://').replace('http://', 'ws://')}/realtime",
    )
    prompt = (
        "Read the following briefing segment aloud exactly as written. "
        "Do not add an introduction, preamble, summary, sign-off, or extra words.\n\n"
        f"{text}"
    )
    command = [
        node,
        str(script_path),
        "--model",
        args.realtime_model,
        "--voice",
        voice,
        "--instructions",
        instructions,
        "--text",
        prompt,
        "--out",
        str(pcm_path),
        "--url",
        realtime_url,
    ]
    if args.keep_intermediates:
        command.extend(["--transcript-out", str(transcript_path)])
    subprocess.run(
        command,
        check=True,
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.DEVNULL,
    )
    convert_pcm_to_mp3(pcm_path, path)


def synthesize_segment(api_key: str, text: str, voice: str, instructions: str, path: Path, args: argparse.Namespace) -> None:
    if args.audio_engine == "realtime":
        synthesize_segment_realtime(text, voice, instructions, path, args)
        return
    synthesize_segment_speech_api(api_key, text, voice, instructions, path, args)


def concat_audio(segment_paths: list[Path], output_path: Path) -> None:
    if len(segment_paths) == 1:
        output_path.write_bytes(segment_paths[0].read_bytes())
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        output_path.write_bytes(b"".join(path.read_bytes() for path in segment_paths))
        return
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.resolve()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def speak_script(args: argparse.Namespace, script: dict[str, Any]) -> Path:
    api_key = require_api_key()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = out_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    segment_jobs: list[tuple[int, dict[str, str], Path]] = []
    for index, segment in enumerate(script["briefing"], start=1):
        path = segments_dir / f"{index:02d}_{segment['speaker']}.mp3"
        segment_jobs.append((index, segment, path))

    def synthesize_job(job: tuple[int, dict[str, str], Path]) -> Path:
        _, segment, path = job
        synthesize_segment(
            api_key,
            segment["text"],
            voice_for_segment(segment, args),
            instructions_for_segment(segment, args),
            path,
            args,
        )
        return path

    if args.segment_concurrency <= 1 or len(segment_jobs) <= 1:
        segment_paths = [synthesize_job(job) for job in segment_jobs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.segment_concurrency) as executor:
            by_index = {
                future: job[0]
                for job, future in (
                    (job, executor.submit(synthesize_job, job)) for job in segment_jobs
                )
            }
            completed: dict[int, Path] = {}
            for future in concurrent.futures.as_completed(by_index):
                completed[by_index[future]] = future.result()
        segment_paths = [completed[index] for index, _, _ in segment_jobs]

    output_path = out_dir / "trace_audio.mp3"
    concat_audio(segment_paths, output_path)
    if not args.keep_intermediates:
        shutil.rmtree(segments_dir, ignore_errors=True)
        concat_path = out_dir / "concat.txt"
        if concat_path.exists():
            concat_path.unlink()
    return output_path


def transcribe_audio(args: argparse.Namespace, audio_path: Path) -> str:
    api_key = require_api_key()
    prompt = (
        "This audio is an AI-generated briefing about a coding agent trace. "
        "Preserve names of tools, files, commands, APIs, and models."
    )
    return http_multipart(
        api_key,
        f"{API_BASE}/audio/transcriptions",
        {
            "model": args.stt_model,
            "response_format": "text",
            "prompt": prompt,
        },
        "file",
        audio_path,
    ).strip()


def judge_audio(args: argparse.Namespace, trace: str, script: dict[str, Any], transcript: str) -> dict[str, Any]:
    api_key = require_api_key()
    prompt = f"""
Judge this generated audio briefing for an agent working trace.

Expected listener: {args.listener}
Expected listener pronunciation hint: {args.listener_pronunciation or "none provided"}

Return only JSON:
{{
  "pass": true,
  "scores": {{
    "faithfulness": 1,
    "coverage": 1,
    "clarity": 1,
    "personalization": 1,
    "actionability": 1
  }},
  "missing_or_wrong": ["specific issues"],
  "best_parts": ["specific strengths"],
  "prompt_adjustments": ["instructions to improve the next iteration"]
}}

Scoring:
- 5 is excellent, 4 is good, 3 is acceptable but needs revision, 1-2 fails.
- Fail if faithfulness is below 4 or coverage is below 4.
- Coverage should reward goal, actions, changes, verification, blockers, and next steps.
- Faithfulness should penalize invented files, tests, claims, or outcomes.
- If the transcript appears to omit or substitute the expected listener name, mention it under missing_or_wrong and cap personalization at 4 unless the rest of the personalization is excellent.
- Compare iteration counts exactly. Fail faithfulness if the audio says a different actual iteration count than the trace or eval artifacts report.

Source trace:
{trace[-MAX_TRACE_CHARS:]}

Generated script JSON:
{json.dumps(script, ensure_ascii=False)}

Speech-to-text transcript of final audio:
{transcript}
""".strip()
    payload = http_json(
        api_key,
        f"{API_BASE}/responses",
        {
            "model": args.judge_model,
            "instructions": (
                "You are a strict evaluator for audio briefings over coding-agent traces. "
                "You care most about faithfulness and whether a busy user can understand "
                "what happened without rereading the full trace."
            ),
            "input": prompt,
            "temperature": 0,
        },
    )
    result = parse_json_text(response_text(payload))
    if not isinstance(result.get("pass"), bool):
        scores = result.get("scores", {})
        result["pass"] = bool(
            isinstance(scores, dict)
            and scores.get("faithfulness", 0) >= 4
            and scores.get("coverage", 0) >= 4
        )
    return result


def command_draft(args: argparse.Namespace) -> None:
    timings: dict[str, float | int] = {}
    trace = read_text(args.trace)
    timings["input_chars"] = len(trace)
    prepared = prepare_trace(args, trace)
    timings["prepared_chars"] = len(prepared)
    start = now()
    script = draft_script(args, trace)
    timings["draft_seconds"] = summarize_elapsed(start)
    timings["segments"] = len(script.get("briefing", []))
    out_path = Path(args.out_dir) / "trace_audio_script.json"
    write_json(out_path, script)
    write_timings(args, timings)
    print(out_path)


def command_speak(args: argparse.Namespace) -> None:
    timings: dict[str, float | int] = {}
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    validate_script(script)
    timings["segments"] = len(script.get("briefing", []))
    start = now()
    audio_path = speak_script(args, script)
    timings["speak_seconds"] = summarize_elapsed(start)
    write_timings(args, timings)
    print(audio_path)


def command_eval(args: argparse.Namespace) -> None:
    trace = read_text(args.trace)
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    transcript = transcribe_audio(args, Path(args.audio))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trace_audio_transcript.txt").write_text(transcript + "\n", encoding="utf-8")
    result = judge_audio(args, trace, script, transcript)
    write_json(out_dir / "trace_audio_eval.json", result)
    print(out_dir / "trace_audio_eval.json")


def command_run(args: argparse.Namespace) -> None:
    timings: dict[str, float | int] = {}
    total_start = now()
    trace = read_text(args.trace)
    timings["input_chars"] = len(trace)
    prepared = prepare_trace(args, trace)
    timings["prepared_chars"] = len(prepared)
    out_dir = Path(args.out_dir)
    start = now()
    script = draft_script(args, trace)
    timings["draft_seconds"] = summarize_elapsed(start)
    timings["segments"] = len(script.get("briefing", []))
    write_json(out_dir / "trace_audio_script.json", script)
    start = now()
    audio_path = speak_script(args, script)
    timings["speak_seconds"] = summarize_elapsed(start)
    timings["total_seconds"] = summarize_elapsed(total_start)
    write_timings(args, timings)
    print(audio_path)


def command_dev_run(args: argparse.Namespace) -> None:
    trace = read_text(args.trace)
    out_dir = Path(args.out_dir)
    feedback = ""
    final_result: dict[str, Any] | None = None
    for iteration in range(1, args.iterations + 1):
        script = draft_script(args, trace, feedback)
        write_json(out_dir / "trace_audio_script.json", script)
        audio_path = speak_script(args, script)
        transcript = transcribe_audio(args, audio_path)
        (out_dir / "trace_audio_transcript.txt").write_text(transcript + "\n", encoding="utf-8")
        result = judge_audio(args, trace, script, transcript)
        result["iteration"] = iteration
        write_json(out_dir / "trace_audio_eval.json", result)
        final_result = result
        if result.get("pass") or iteration == args.iterations:
            break
        feedback = json.dumps(result, ensure_ascii=False)
        time.sleep(1)
    print(out_dir / "trace_audio.mp3")
    if final_result is not None:
        print(json.dumps({"pass": final_result.get("pass"), "iteration": final_result.get("iteration")}))


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", default="out/trace-audio")
    parser.add_argument("--listener", default=os.environ.get("USER", "the user"))
    parser.add_argument("--listener-pronunciation", default=os.environ.get("TRACECAST_LISTENER_PRONUNCIATION", ""))
    parser.add_argument("--project", default=Path.cwd().name)
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument("--script-model", default=DEFAULT_SCRIPT_MODEL)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--audio-engine", choices=["realtime", "speech"], default=DEFAULT_AUDIO_ENGINE)
    parser.add_argument("--realtime-model", default=DEFAULT_REALTIME_MODEL)
    parser.add_argument("--tts-model", default=DEFAULT_TTS_MODEL)
    parser.add_argument("--stt-model", default=DEFAULT_STT_MODEL)
    parser.add_argument("--host-voice", default=DEFAULT_HOST_VOICE)
    parser.add_argument("--analyst-voice", default=DEFAULT_ANALYST_VOICE)
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument("--trace-budget-chars", type=int, default=MAX_TRACE_CHARS)
    parser.add_argument("--trace-mode", choices=["compact", "tail"], default="compact")
    parser.add_argument("--max-segments", type=int, default=4)
    parser.add_argument("--segment-concurrency", type=int, default=4)
    parser.add_argument("--timings-out")


def write_timings(args: argparse.Namespace, timings: dict[str, float | int]) -> None:
    if not args.timings_out:
        return
    payload = {
        "audio_engine": args.audio_engine,
        "realtime_model": args.realtime_model,
        "script_model": args.script_model,
        "trace_budget_chars": args.trace_budget_chars,
        "trace_mode": args.trace_mode,
        "max_segments": args.max_segments,
        "segment_concurrency": args.segment_concurrency,
        "timings": timings,
    }
    write_json(Path(args.timings_out), payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft", help="Draft a briefing script JSON.")
    draft.add_argument("--trace", default="-")
    add_common_args(draft)
    draft.set_defaults(func=command_draft)

    speak = subparsers.add_parser("speak", help="Create audio from a script JSON.")
    speak.add_argument("--script", required=True)
    add_common_args(speak)
    speak.set_defaults(func=command_speak)

    evaluate = subparsers.add_parser("eval", help="Transcribe and judge an existing audio file.")
    evaluate.add_argument("--trace", required=True)
    evaluate.add_argument("--script", required=True)
    evaluate.add_argument("--audio", required=True)
    add_common_args(evaluate)
    evaluate.set_defaults(func=command_eval)

    run = subparsers.add_parser("run", help="Draft and synthesize a local audio briefing.")
    run.add_argument("--trace", default="-")
    add_common_args(run)
    run.set_defaults(func=command_run)

    dev_run = subparsers.add_parser("dev-run", help="Development loop: draft, synthesize, transcribe, judge, and iterate.")
    dev_run.add_argument("--trace", default="-")
    dev_run.add_argument("--iterations", type=int, default=2)
    add_common_args(dev_run)
    dev_run.set_defaults(func=command_dev_run)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"trace_audio.py: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
