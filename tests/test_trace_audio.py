import argparse
import json
import unittest

from scripts.trace_audio import build_draft_prompt, infer_eval_pass, parse_json_text, validate_script


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
            listener="Sarath",
            listener_pronunciation="SAR-uth",
            project="agent-playback",
            duration_seconds=60,
            trace_budget_chars=45000,
            trace_mode="compact",
            max_segments=4,
        )
        prompt = build_draft_prompt(args, "Ran tests and generated audio.")
        self.assertIn("Sarath", prompt)
        self.assertIn("agent-playback", prompt)
        self.assertIn("Ran tests and generated audio.", prompt)
        self.assertIn("Do not start with \"this is AI-generated\"", prompt)
        self.assertIn("standup-style question-and-answer", prompt)
        self.assertIn("The host asks short, practical questions", prompt)

    def test_eval_pass_requires_standup_format_and_boundaries(self):
        self.assertFalse(
            infer_eval_pass(
                {
                    "faithfulness": 5,
                    "coverage": 5,
                    "clarity": 5,
                    "personalization": 5,
                    "actionability": 5,
                    "standup_format": 3,
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
                    "standup_format": 5,
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
                    "standup_format": 4,
                    "boundary_awareness": 4,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
