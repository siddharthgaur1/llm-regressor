# Your prompt tests are green and your prompt is broken

There is a category of bug that survives code review, survives CI, and shows
up three weeks later in a support queue. It looks like this:

```diff
  Always reply with a JSON object containing `reply` and `order_id`.
+ Be warm and personable.
```

One added sentence. The reviewer reads it, agrees replies should be warmer,
approves. Every test passes, because there were no tests — or because the
tests that exist check that the code calls the API, not what the API says
back.

What actually happened: the model read two instructions in tension and
resolved them in favour of the more recent one. Replies got warmer. They also
stopped being JSON. The ticketing integration downstream parses that JSON.

The failure is not exotic. The reason it ships is structural: **nobody ran the
old prompt and the new prompt against the same inputs at the moment the diff
was under review.** That comparison is cheap, and almost nobody does it,
because the tooling for it does not fit the shape of a normal test suite.

This post is about why it doesn't fit, why the obvious fix — a golden dataset
with expected outputs — fails in a specific and instructive way, and what to
do instead. The code is [`llm-regressor`](https://github.com/siddharthgaur1/llm-regressor),
MIT, and every technique below is implemented there.

---

## Why `assert output == expected` doesn't work

The instinct is to write the test you would write for any other function:

```python
def test_refund_reply():
    assert bot("I want a refund for order 4471.") == EXPECTED_REPLY
```

This fails immediately, and for three different reasons that people tend to
conflate.

**1. The output space is large and mostly correct.** "I can help with that
refund." and "Happy to help with your refund." are both fine. Exact match
calls one of them a bug. You will spend more time updating expected strings
than reading results, and within a month someone will bulk-update the golden
file to make CI green without reading the diff.

**2. The output is nondeterministic even at temperature 0.** This surprises
people. Temperature 0 is not a guarantee of determinism — it is a greedy
sampling strategy, and the logits it is greedy over can move. Batched
inference on GPUs is not bitwise reproducible across different batch
compositions, floating-point reduction order varies, and MoE models route
tokens differently depending on what else is in the batch. Providers also
update model weights behind a stable-looking alias. So an exact-match test
flakes, and a flaky test is a test that gets deleted.

**3. Not every property you care about is in the text.** Latency. Cost. Whether
the model gives the same answer twice. None of these are assertions about a
single output string.

The usual response to (1) and (2) is to loosen the assertion — substring
match, fuzzy match, an LLM judge with a threshold. That helps. But it
introduces the failure mode that makes this genuinely hard.

## The real problem: a threshold you cannot set

Say you replace exact match with an LLM-as-judge score:

```python
score = judge("Does this response contain hallucinations?", response)
assert score >= 0.7
```

Now, what is 0.7?

You picked it because it sounded reasonable. You have no idea whether a
correct response typically scores 0.95 or 0.72 for your task, and you have no
idea how much that number moves between two runs of the *same* prompt.

Which means when a run scores 0.68, you cannot distinguish between:

- the prompt got worse, or
- the judge was in a mood.

Set the threshold at 0.7 and you get false alarms. Set it at 0.5 and you miss
real regressions. Neither is a calibration problem you can solve by picking a
better number, because **an absolute threshold discards the only information
that would let you tell signal from noise: what the same test scored before
the change.**

## The fix: measure the delta, not the level

Run both configurations. Same suite, same inputs, in the same session:

```python
report = Regressor(
    baseline=providers.Anthropic(model="claude-sonnet-5", system_prompt=v1),
    candidate=providers.Anthropic(model="claude-sonnet-5", system_prompt=v2),
).run(suite)
```

Now "0.68" is not a number floating in space. It is 0.68 against a baseline
that scored 0.71 on the identical input, minutes earlier, through the same
API, with the same judge. Judge drift, provider-side model updates, and
sampling noise mostly apply to both sides and cancel.

This is why the comparison has to be *paired* and *simultaneous*. A score
recorded last month against a prompt you no longer have is not a baseline; it
is a rumour. The most common way teams get this wrong is storing golden scores
in a file and comparing today's run against them. Six weeks later the provider
ships a model update, every score shifts by 0.04, and you cannot tell whether
your prompt regressed or the ground moved.

## Not every difference deserves to block a merge

Once you are measuring deltas, the temptation is to fail the build on any of
them. Do that and the tool gets disabled — not because it was wrong, but
because it was noisy, and a check that cries wolf trains people to click
through it.

So the deltas get sorted by what they justify:

| Severity | What it means | Blocks? |
| --- | --- | --- |
| CRITICAL | A check failed outright — invalid JSON, missing required fact, judge below threshold | **Yes**, exit 1 |
| WARNING | Still passing, but >20% below baseline, or measurably less consistent | No |
| INFO | Latency or cost moved | No |

The interesting line is WARNING. A candidate that scores 0.75 where the
baseline scored 1.0 has passed every threshold — and something clearly
changed. Failing the build on it produces arguments about whether 0.75 is
"really" worse. Discarding it loses the signal entirely. Recording it as a
visible non-blocking note is the only option that survives contact with a
team that has deadlines.

Latency and cost are INFO for a specific reason: wall-clock latency measured
from a CI runner is too noisy to gate on. You would be failing merges over
someone else's noisy neighbour. But it is worth *recording*, so that when
someone asks in three months whether the prompt rewrite made things slower,
there is a number rather than a memory.

## Checking variance directly

Deltas handle "did it get worse". They do not handle "did it get *flakier*",
which is its own regression and one that ships constantly. A prompt that is
right 100% of the time and a prompt that is right 70% of the time both look
fine if you sample them once and get lucky.

So sample more than once and measure the spread:

```python
report = Regressor(baseline=v1, candidate=v2).run(suite, samples=5)
```

Five completions per side per test. Compute mean pairwise similarity within
each side — embedding cosine similarity if `sentence-transformers` is
installed, `difflib` otherwise — and compare the two. If the candidate's
internal agreement drops more than 0.15 below the baseline's, that is a
WARNING even when every individual response passed every check.

This is the check that catches the prompt edit which "works when I try it".
It is also the expensive one: `samples=5` is five times the API bill. The
honest recommendation is `samples=1` on the pull request gate and `samples=5`
on a nightly run, where consistency drift matters and turnaround does not.

**A caveat worth stating plainly**: that 0.15, and the 20% drop rule above,
are defaults. They are not calibrated against human-labelled data, and this
tool ships no evidence about how well an LLM judge agrees with your reviewers.
They are starting points that make WARNING mean "go look", not "this is
measurably worse". Anyone telling you their judge thresholds are principled
without showing you the agreement study is guessing too — they are just not
saying so.

## Check structure, not only content

Back to the opening example. Here is what the three checks did:

```yaml
- id: refund_request
  input: "I want a refund for order 4471."
  checks:
    - type: json_valid
    - type: contains
      value: "4471"
```

Candidate response:

> Of course — I'm sorry about the trouble with order 4471! I can help with that refund.

The `contains` check **passed**. The order number is right there. The facts
were never wrong; the *shape* was. Only `json_valid` caught it.

This generalises. When a prompt change breaks something, it very often breaks
formatting rather than facts, because formatting instructions are the ones
that compete with every other instruction in the prompt for the model's
attention. A suite full of factual assertions and no structural ones will sail
straight past the most common failure mode.

The cheap checks earn their place here. `json_valid` costs nothing, needs no
API call, and caught what four kinds of semantic checking would have missed.
Put the free deterministic checks in first and reach for a judge only for
things a regex genuinely cannot express.

## Wiring it into CI

The whole point is to run at review time, so the exit code is the product:

```yaml
- uses: siddharthgaur1/llm-regressor@v0.1.0
  with:
    suite: tests/suite.yaml
    baseline-prompt: prompts/main.txt
    candidate-prompt: prompts/candidate.txt
```

Three implementation details that turned out to matter more than expected:

**Run the gate after reporting, not instead of it.** The obvious composite
step lets the tool's own non-zero exit fail the job. That skips the artifact
upload and the PR comment — so the one time you most need the report is the
one time you cannot see it. Capture the result, publish it, then fail.

**Hold the model fixed in prompt mode.** If you changed the model and the
prompt in the same run, you cannot attribute the difference to either. Prompt
mode uses one model on both sides on purpose.

**Scope the trigger.** `on.pull_request.paths` limited to your prompts and
suite. Every run costs real money —
`tests × judge checks × samples × 2 sides` — and a regression suite that
fires on README typos gets removed for the bill, not for the results.

## What this does not solve

Being explicit about the edges, since a tool that oversells is a tool you stop
trusting the first time it is confidently wrong:

- **Your suite is the ceiling.** These techniques tell you whether behaviour
  changed on the inputs you thought to include. A regression on a category of
  input that is not in the suite is invisible, and no amount of statistical
  sophistication fixes that. The unglamorous work is curating inputs.
- **Judges inherit the judge model's blind spots.** Using the baseline model
  as its own judge is cheap and usually fine, but if you are grading factuality
  in a domain the model is weak in, you are asking someone to mark their own
  homework.
- **Cost figures are estimates.** They come from a pricing table in the client
  and a mid-tier guess for unrecognised model names. Directionally useful, not
  an invoice.
- **Pattern checks are not security controls.** `no_injection_risk` catches a
  model that has *started* emitting `DROP TABLE`. It will not stop an
  adversary, and it must not gate anything that executes generated code.

## The short version

1. Exact-match golden tests fail on LLM output — the space is too large and
   the output is not deterministic even at temperature 0.
2. Absolute thresholds on judge scores fail differently: you cannot tell a
   regression from judge noise without a reference point.
3. Run both configurations in the same session and compare them to each other.
   That is what makes a threshold interpretable.
4. Sort the deltas by what they justify. Only unambiguous failures block, or
   the check gets switched off.
5. Sample repeatedly to catch variance regressions, which single-shot testing
   cannot see.
6. Check structure, not just facts. The free checks catch the common bugs.
7. State your thresholds are uncalibrated, because they are.

```bash
pip install llm-regressor
```

The worked example from the opening runs offline with no API key:

```bash
git clone https://github.com/siddharthgaur1/llm-regressor
cd llm-regressor && pip install -e .
python examples/prompt_regression_demo.py   # exits 1
```

Docs: <https://siddharthgaur1.github.io/llm-regressor/>
