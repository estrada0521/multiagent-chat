"""Gemini text-message → runtime label rules.

Gemini does not expose structured tool calls in its native log; instead the
parser reads planning / thinking text and classifies it by keyword matching.

PATTERN_LABEL_RULES is checked in order against the lowercased first line of
each message.  The first matching pattern wins.  If no pattern matches,
DEFAULT_LABEL is used.

To change how a Gemini action appears in the running indicator:
  1. Find or add the relevant pattern below.
  2. Change the label to any frontend canonical label:
     Read / Write / Edit / Search / Explore / Run / Delete / Thinking
"""
from __future__ import annotations

# (regex_pattern, label)
# Patterns are tested with re.search against the lowercased first line.
PATTERN_LABEL_RULES: list[tuple[str, str]] = [
    # Image inspection (must come before generic "read" / "check" rules)
    (r"\b(image|screenshot|photo|picture|attached)\b.{0,80}\b(view|look|inspect|examine|check|read)\b", "Read"),
    (r"\b(view|look|inspect|examine|check|read)\b.{0,80}\b(image|screenshot|photo|picture|attached)\b", "Read"),
    # Search / find
    (r"\b(search|find|locate|look\s+for|grep|rg)\b", "Search"),
    # Git operations
    (r"\b(commit|committing)\b", "Run"),
    # Testing / verification
    (r"\b(test|verify|validate|check\s+whether)\b", "Run"),
    # Execution
    (r"\b(run|execute|restart|launch|start)\b", "Run"),
    # Editing / modifying
    (r"\b(update|modify|change|adjust|refine|fix|align|add|remove|replace|ensure|include|clean|simplify|deduplicate)\b", "Edit"),
    # Writing / creating
    (r"\b(write|create|scaffold|generate|add\s+a\s+new)\b", "Write"),
    # Reading / inspecting
    (r"\b(read|open|inspect|examine|review|check|look\s+at|analy[sz]e)\b", "Read"),
]

# Label when no pattern matches (agent is planning / thinking)
DEFAULT_LABEL: str = "Thinking"
