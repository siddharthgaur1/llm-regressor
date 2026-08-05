# Quickstart

## 1. Install

```bash
pip install "llm-regressor[anthropic]"   # or [openai], [litellm], [ollama], [all]
```

The core package has no provider SDK in it. Pick the extra matching the
provider you use; `[all]` pulls in everything including the embedding backend.

## 2. Scaffold a suite

```bash
llm-regressor init
```

That writes a `suite.yaml` you can run immediately:

```yaml
tests:
  - id: factual_capital
    input: "What is the capital of France?"
    expected: "Paris"
    checks:
      - type: contains
        value: "Paris"
    category: factual

  - id: sentiment_classification
    input: "Classify the sentiment of: 'The product is terrible'"
    checks:
      - type: semantic_similarity
        reference: "negative sentiment"
        threshold: 0.6
      - type: length_range
        min: 1
        max: 200
    category: classification
```

## 3. Run it

Comparing two models:

```bash
export ANTHROPIC_API_KEY=...
llm-regressor run \
  --suite suite.yaml \
  --baseline claude-sonnet-5 \
  --candidate claude-haiku-4-5-20251001 \
  --html report.html
```

Comparing two prompts on the *same* model — which is the more common case,
and the one where a regression is easiest to miss:

```bash
llm-regressor run \
  --suite suite.yaml \
  --baseline-prompt prompts/v1.txt \
  --candidate-prompt prompts/v2.txt
```

!!! note "Prompt mode deliberately holds the model fixed"
    If you changed the model and the prompt at once, you cannot attribute the
    difference to either. Prompt mode uses one model on both sides so the
    delta means something.

## 4. Read the exit code

```bash
llm-regressor run --suite suite.yaml --baseline a --candidate b
echo $?   # 0 = no CRITICAL regression, 1 = at least one
```

That exit code is the whole product. Everything else — the terminal table,
the HTML report, the JSON — exists to explain a number your CI already acted
on.

## 5. Try it without an API key

If you have [Ollama](https://ollama.com) running locally, you can exercise
the full flow for free:

```python
from llm_regressor import Regressor, TestSuite, providers

suite = TestSuite.from_yaml("suite.yaml")
report = Regressor(
    baseline=providers.Ollama(model="llama3.1"),
    candidate=providers.Ollama(model="llama3.2"),
).run(suite)
report.summary()
```

## Next

- Put it in CI: **[GitHub Action](github-action.md)**
- See a regression caught end to end: **[Worked example](example.md)**
