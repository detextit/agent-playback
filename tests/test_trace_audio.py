import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.trace_audio import (
    build_draft_prompt,
    infer_eval_pass,
    latest_session_path,
    parse_json_text,
    read_trace,
    render_codex_session_trace,
    validate_script,
)


class TraceAudioTests(unittest.TestCase):
    def test_parse_json_text_handles_fenced_json(self):
        payload = parse_json_text('```json\n{"pass": true}\n```')
        self.assertEqual(payload, {"pass": True})

    def test_validate_script_accepts_two_speakers(self):
        validate_script(
            {
                "briefing": [
                    {"speaker": "host", "text": "Here is the useful recap."},
                    {"speaker": "analyst", "text": "The agent added tests."},
                ]
            }
        )

    def test_prompt_includes_trace_and_listener(self):
        args = argparse.Namespace(
            listener="you",
            listener_pronunciation="",
            project="agent-playback",
            duration_seconds=60,
            trace_budget_chars=45000,
            trace_mode="compact",
            max_segments=4,
        )
        prompt = build_draft_prompt(args, "Ran tests and generated audio.")
        self.assertIn("you", prompt)
        self.assertIn("agent-playback", prompt)
        self.assertIn("Ran tests and generated audio.", prompt)
        self.assertIn("Do not open with a question", prompt)
        self.assertIn("concise trace audio report", prompt)
        self.assertIn("The host sets context", prompt)

    def test_render_codex_session_trace_skips_metadata_instructions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "session.jsonl"
            rows = [
                {
                    "timestamp": "2026-05-28T01:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "session-1",
                        "timestamp": "2026-05-28T01:00:00Z",
                        "cwd": "/tmp/project",
                        "base_instructions": {"text": "Do not include this in the trace."},
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:01Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "developer",
                        "content": [{"type": "input_text", "text": "hidden developer text"}],
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:02Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Please fix the CSV export."}],
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:03Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "arguments": json.dumps({"cmd": "pytest tests/test_csv.py"}),
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:04Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "2 passed",
                    },
                },
                {
                    "timestamp": "2026-05-28T01:00:05Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "CSV export is fixed."}],
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            trace = render_codex_session_trace(path)

        self.assertIn("Please fix the CSV export.", trace)
        self.assertIn("pytest tests/test_csv.py", trace)
        self.assertIn("2 passed", trace)
        self.assertIn("CSV export is fixed.", trace)
        self.assertNotIn("Do not include this", trace)
        self.assertNotIn("hidden developer text", trace)

    def test_read_trace_auto_converts_codex_session_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "session.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-28T01:00:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Full local transcript"}],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            args = argparse.Namespace(trace=str(path), trace_session=None)

            trace = read_trace(args)

        self.assertIn("Full local transcript", trace)

    def test_latest_session_path_uses_newest_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            older = root / "2026" / "05" / "27" / "older.jsonl"
            newer = root / "2026" / "05" / "28" / "newer.jsonl"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("{}", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))

            self.assertEqual(latest_session_path(root), newer)

    def test_eval_pass_requires_report_structure_and_boundaries(self):
        self.assertFalse(
            infer_eval_pass(
                {
                    "faithfulness": 5,
                    "coverage": 5,
                    "clarity": 5,
                    "personalization": 5,
                    "actionability": 5,
                    "report_structure": 3,
                    "boundary_awareness": 5,
                }
            )
        )
        self.assertFalse(
            infer_eval_pass(
                {
                    "faithfulness": 5,
                    "coverage": 5,
                    "clarity": 5,
                    "personalization": 5,
                    "actionability": 5,
                    "report_structure": 5,
                    "boundary_awareness": 3,
                }
            )
        )
        self.assertTrue(
            infer_eval_pass(
                {
                    "faithfulness": 4,
                    "coverage": 4,
                    "clarity": 4,
                    "personalization": 4,
                    "actionability": 4,
                    "report_structure": 4,
                    "boundary_awareness": 4,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
