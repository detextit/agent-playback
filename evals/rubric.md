# Trace Audio Eval Rubric

The audio briefing should pass only when a busy user can understand what happened without rereading the trace.

Scores use a 1 to 5 scale.

- Faithfulness: no invented files, tests, results, failures, or decisions.
- Coverage: includes the user goal, agent actions, important changes, verification, blockers or failures, residual risks, and next steps.
- Clarity: sounds natural when spoken and avoids raw-log overload.
- Personalization: names the listener or project and frames the briefing around their likely follow-up needs.
- Actionability: makes the current state and next useful action obvious.
- Standup format: one voice asks short, practical questions while the other gives the substantive work update.
- Boundary awareness: names failed checks, setup limits, missing verification, residual risks, or uncertainty when the trace supports them.

Automatic fail conditions:

- Faithfulness below 4.
- Coverage below 4.
- Standup format below 4.
- Boundary awareness below 4.
- Any other score below 3.
- Any claim that a test passed, file changed, or issue was fixed when the trace does not support it.
- A podcast-style exchange where both speakers riff, summarize equally, or bury the actual work update.
- A dull compliance-style opening instead of a useful standup question.
