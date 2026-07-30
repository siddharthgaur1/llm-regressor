# Contributing

1. Fork, clone, `pip install -e ".[dev,all]"`
2. `pytest` before you open a PR — coverage must stay above 80%.
3. New check types go in `llm_regressor/checks/{deterministic,llm_judge,statistical}.py` and get registered in that file's `REGISTRY` dict.
4. New providers subclass `llm_regressor.providers.base.BaseProvider` and implement `complete(prompt) -> CompletionResult`.
5. Keep the public API (`Regressor`, `TestSuite`, `Report`, `providers.*`) stable — it's what users import.

Bug reports and check-type/provider requests: open a GitHub issue.
