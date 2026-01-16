"""Custom check functions for regression tests.

Each check function takes list[AgentStep] and returns tuple[bool, str] (passed, reasoning).
"""

from __future__ import annotations

from regression_tests.custom_checks.hidden_multivalue_warning import (
    check_knowledge_base_hidden_multivalue_warning,
)
from regression_tests.custom_checks.net_terms_formula_field import (
    check_net_terms_formula_field_added,
)
from regression_tests.custom_checks.no_misleading_training_suggestions import (
    check_no_misleading_training_suggestions,
)

__all__ = [
    "check_knowledge_base_hidden_multivalue_warning",
    "check_net_terms_formula_field_added",
    "check_no_misleading_training_suggestions",
]
