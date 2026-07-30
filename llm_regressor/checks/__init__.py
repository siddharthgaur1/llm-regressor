from .deterministic import REGISTRY as DETERMINISTIC_CHECKS
from .llm_judge import REGISTRY as JUDGE_CHECKS
from . import statistical

ALL_CHECKS = {**DETERMINISTIC_CHECKS, **JUDGE_CHECKS}

__all__ = ["DETERMINISTIC_CHECKS", "JUDGE_CHECKS", "ALL_CHECKS", "statistical"]
