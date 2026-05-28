# Trace Audio Eval Rubric

The audio briefing should pass only when a busy user can understand what happened without rereading the trace.

Scores use a 1 to 5 scale.

- Faithfulness: no invented files, tests, results, failures, or decisions.
- Coverage: includes the user goal, agent actions, important changes, verification, blockers or failures, residual risks, and next steps.
- Clarity: sounds natural when spoken and avoids raw-log overload.
- Personalization: names the listener or project and frames the briefing around their likely follow-up needs.
- Actionability: makes the current state and next useful action obvious.

Automatic fail conditions:

- Faithfulness below 4.
- Coverage below 4.
- Any claim that a test passed, file changed, or issue was fixed when the trace does not support it.
- A dull compliance-style opening instead of a useful hook.
