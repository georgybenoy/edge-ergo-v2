"""
Broad facial-expression classifier.

Classifies facial landmarks into one of four broad categories:
NEUTRAL, POSITIVE, NEGATIVE, REDUCED.

Non-goals (enforced):
  - No facial recognition or identity inference.
  - No medical/psychological diagnosis — never output "stressed",
    "depressed", "anxious", or similar clinical terms.
"""

# TODO: Phase 5 — implement ExpressionClassifier class
