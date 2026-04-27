"""Gemini: プラン文からランタイムラベルへ（このファイルのみ編集すれば Gemini 表示が変わる）。"""

from __future__ import annotations

PATTERN_LABEL_RULES: list[tuple[str, str]] = [
    (
        r"\b(image|screenshot|photo|picture|attached)\b.{0,80}\b(view|look|inspect|examine|check|read)\b",
        "Read",
    ),
    (
        r"\b(view|look|inspect|examine|check|read)\b.{0,80}\b(image|screenshot|photo|picture|attached)\b",
        "Read",
    ),
    (r"\b(search|find|locate|look\s+for|grep|rg)\b", "Search"),
    (r"\b(commit|committing)\b", "Run"),
    (r"\b(test|verify|validate|check\s+whether)\b", "Run"),
    (r"\b(run|execute|restart|launch|start)\b", "Run"),
    (
        r"\b(update|modify|change|adjust|refine|fix|align|add|remove|replace|ensure|include|clean|simplify|deduplicate)\b",
        "Edit",
    ),
    (r"\b(write|create|scaffold|generate|add\s+a\s+new)\b", "Write"),
    (r"\b(read|open|inspect|examine|review|check|look\s+at|analy[sz]e)\b", "Read"),
]

DEFAULT_LABEL: str = "Thinking"
