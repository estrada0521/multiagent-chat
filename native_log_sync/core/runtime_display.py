"""ランタイム用イベント dict の共通形だけ。

各エージェントの `runtime_tools.py` が決めたメイン行（例: Read）とサブ行（例: パス文字列）を
受け取り、`text` に単純結合するだけ。パス相対化・grep 要約・JSON パース等は行わない。
"""

from __future__ import annotations


def runtime_event(main: str, sub: str = "", *, source_id: str) -> dict:
    """`main` と `sub` を空白1つで連結して `text` を作る（どちらか片方のみでも可）。"""
    m = str(main or "").strip()
    s = str(sub or "").strip()
    if m and s:
        text = f"{m} {s}"
    elif m:
        text = m
    elif s:
        text = s
    else:
        text = ""
    return {"kind": "fixed", "text": text, "source_id": source_id}
