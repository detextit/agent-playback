# Trace Audio Eval Rubric

The audio briefing should pass only when a busy user can understand what happened without rereading the trace.

Scores use a 1 to 5 scale.

- Faithfulness: no invented files, tests, results, failures, or decisions.
- Coverage: includes the user goal, agent actions, important changes, verification, blockers or failures, residual risks, and next steps.
- Clarity: sounds natural when spoken and avoids raw-log overload.
- Personalization: uses the project and listener context where useful without forced name drops.
- Actionability: makes the current state and next useful action obvious.
- Report structure: opens with a direct report, then covers goal, progress, changes, verification, boundaries, and next steps.
- Boundary awareness: names failed checks, setup limits, missing verification, residual risks, or uncertainty when the trace supports them.

Automatic fail conditions:

- Faithfulness below 4.
- Coverage below 4.
- Report structure below 4.
- Boundary awareness below 4.
- Any other score below 3.
- Any claim that a test passed, file changed, or issue was fixed when the trace does not support it.
- A podcast-style exchange where both speakers riff, summarize equally, or bury the actual work update.
- An opening question, forced listener-name hook, or dull compliance-style opening instead of a useful report lead.
