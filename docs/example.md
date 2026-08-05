# Worked example: the regression a diff review misses

A support bot replies to customers. Its system prompt ends with:

> Always reply with a JSON object containing `reply` and `order_id`.

Support asks for warmer replies. Someone adds one sentence:

```diff
  Always reply with a JSON object containing `reply` and `order_id`.
+ Be warm and personable.
```

The change is reviewed and merged. The replies do get warmer. What nobody
notices is that the model now reads the two instructions as being in tension
and quietly drops the JSON wrapper — and the ticketing integration downstream
parses that JSON.

## The suite

```yaml
tests:
  - id: refund_request
    input: "I want a refund for order 4471."
    category: support
    checks:
      - type: json_valid
      - type: contains
        value: "4471"

  - id: escalation
    input: "This is the third time I've contacted you. Escalate this."
    category: support
    checks:
      - type: json_valid
      - type: not_contains
        value: "I cannot"

  - id: order_status
    input: "Where is order 9982?"
    category: support
    checks:
      - type: json_valid
      - type: contains
        value: "9982"
```

## The run

```bash
llm-regressor run \
  --suite tests/support_suite.yaml \
  --baseline-prompt prompts/v1.txt \
  --candidate-prompt prompts/v2.txt \
  --html report.html
```

```text
                          scripted:support-bot  vs  scripted:support-bot
┌────────────────┬──────────┬─────────────────────────────────────────────────────────────────────┐
│ Test ID        │ Severity │ Message                                                             │
├────────────────┼──────────┼─────────────────────────────────────────────────────────────────────┤
│ refund_request │ CRITICAL │ json_valid failed: invalid JSON: Expecting value: line 1 column 1   │
│                │          │ (char 0)                                                            │
│ escalation     │ CRITICAL │ json_valid failed: invalid JSON: Expecting value: line 1 column 1   │
│                │          │ (char 0)                                                            │
│ order_status   │ CRITICAL │ json_valid failed: invalid JSON: Expecting value: line 1 column 1   │
│                │          │ (char 0)                                                            │
│ __latency__    │ PASS     │ candidate p95 910ms vs baseline p95 820ms (threshold 1.5x)          │
│ __cost__       │ PASS     │ candidate avg cost $0.00040 vs baseline $0.00040 (threshold 2.0x)   │
└────────────────┴──────────┴─────────────────────────────────────────────────────────────────────┘
Regressions: 3 CRITICAL, 0 WARNING, 0 INFO
Overall: FAILED

By category:
  support: {'CRITICAL': 3, 'WARNING': 0, 'INFO': 0, 'PASS': 0}
  meta: {'CRITICAL': 0, 'WARNING': 0, 'INFO': 0, 'PASS': 2}
```

Exit code 1. In CI, the pull request does not merge.

## Run it yourself

That transcript is the real output of a script in this repository, not an
illustration:

```bash
pip install -e .
python examples/prompt_regression_demo.py
```

It uses scripted providers rather than a live API, so it is free,
deterministic, and needs no key. Swap `_Scripted` for
`providers.Anthropic(...)` and it becomes a real run against real models.

## What to notice

**The `contains` checks passed.** "…trouble with order 4471!" still contains
`4471`. Only `json_valid` caught it. A suite that only checked for the right
facts would have gone green, because the facts were right — it was the
*shape* that broke. Check structure as well as content.

**Latency and cost were PASS, and they were still worth printing.** 820ms →
910ms is not a regression, and blocking on it would be noise. But the run
records it, so when someone asks in three months whether the prompt rewrite
made things slower, there is a number instead of a memory.

**Every failure names the check that fired.** `json_valid failed: invalid
JSON: Expecting value: line 1 column 1 (char 0)` tells you the response
wasn't JSON at all rather than being malformed JSON — which points at a
dropped wrapper, not a truncation. Detail strings are the difference between
a report you act on and one you re-run manually to understand.

## The wider point

The `json_valid` check is trivial. Writing it took ten seconds. The reason
this class of bug ships is not that the check is hard, it is that nobody runs
it against the *old* prompt and the *new* prompt on the same inputs at the
moment the diff is under review.

That comparison is the entire idea. Everything else here is plumbing.
