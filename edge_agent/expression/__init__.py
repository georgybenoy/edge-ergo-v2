"""
EdgeErgo — Expression Module.

Provides:
  - ExpressionClassifier: Lightweight rule-based classifier mapping facial metrics to broad categories.
  - ExpressionCategory: Broad categories (Neutral, Positive, Negative, Reduced, Eye-closure, Uncertain).
  - ExpressionResult: Typed result structure with category, confidence, and validation status.

NON-GOALS (PRD §6, §27):
  No emotional or psychological diagnosis (stress, depression, anxiety, burnout).
"""

from edge_agent.expression.classifier import (
    ExpressionCategory,
    ExpressionClassifier,
    ExpressionResult,
)

__all__ = [
    "ExpressionCategory",
    "ExpressionClassifier",
    "ExpressionResult",
]
