"""Rule registry. Importing this package registers all built-in rules."""
from .base import Rule, all_rules, register  # noqa: F401
from . import (  # noqa: F401
    boundary_value,
    early_goodbye,
    enough_for_today,
    false_memory,
    premature_praise,
    question_barrage,
    repeated_question,
    scripted_chain,
)
