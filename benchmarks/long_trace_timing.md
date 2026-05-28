# Long Trace Timing

Benchmarks run against synthetic traces generated under `tmp/bench_traces`.

## Draft Timing

| Case | Input chars | Prepared chars | Draft seconds | Segments |
| --- | ---: | ---: | ---: | ---: |
| 10k raw | 10,000 | 10,000 | 4.724 | 4 |
| 45k raw | 45,000 | 45,000 | 5.821 | 4 |
| 120k compact 8k | 120,000 | 7,625 | 8.209 | 4 |
| 120k tail 45k | 120,000 | 45,000 | 6.665 | 4 |

Draft calls have normal model/network variance, so treat single-run numbers as directional.

## Realtime Audio Timing

Same 4-segment script:

| Mode | Speak seconds |
| --- | ---: |
| Sequential segments | 14.758 |
| 4 parallel segments | 4.522 |

## End-to-End Long Trace Timing

| Case | Input chars | Prepared chars | Draft seconds | Speak seconds | Total seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 120k compact 8k, 4 parallel segments | 120,000 | 7,625 | 8.081 | 4.506 | 12.594 |
| 120k tail 45k, 4 parallel segments | 120,000 | 45,000 | 9.724 | 5.461 | 15.186 |

## Current Recommendations

- Use `--trace-mode compact` for long traces.
- Start with `--trace-budget-chars 8000`; raise it only when summaries miss important context.
- Keep `--max-segments 4` for fast, polished briefings.
- Keep `--segment-concurrency 4` unless hitting rate limits.
- Use `--timings-out` when tuning on real traces.
