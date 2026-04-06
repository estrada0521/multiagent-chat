from __future__ import annotations

import json
import re


def build_pane_trace_view_model(
    *,
    agent: str,
    agents: list[str] | None,
    bg: str,
    text: str,
    chat_base_path: str = "",
) -> dict[str, object]:
    base_path = (chat_base_path or "").rstrip("/")
    bg_value = (bg or "").strip() or "rgb(10, 10, 10)"
    text_value = (text or "").strip() or "rgb(252, 252, 252)"
    all_agents = agents or ([agent] if agent else [])
    initial_agent = agent or (all_agents[0] if all_agents else "")
    agents_json = json.dumps(all_agents, ensure_ascii=True)
    initial_agent_json = json.dumps(initial_agent, ensure_ascii=True)
    bg_json = json.dumps(bg_value, ensure_ascii=True)
    text_json = json.dumps(text_value, ensure_ascii=True)

    bg_effective = "rgb(30, 30, 30)"
    header_overlay_bg = "rgba(30, 30, 30, 0.78)"
    rgb_match = re.search(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", text_value)
    if rgb_match:
        tr, tg, tb = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
        body_fg = f"rgba({tr}, {tg}, {tb}, 0.78)"
        body_dim_fg = f"rgba({tr}, {tg}, {tb}, {0.38 if (tr + tg + tb) >= 384 else 0.42})"
    else:
        body_fg = text_value
        body_dim_fg = text_value

    return {
        "base_path": base_path,
        "bg_value": bg_value,
        "text_value": text_value,
        "all_agents": all_agents,
        "initial_agent": initial_agent,
        "agents_json": agents_json,
        "initial_agent_json": initial_agent_json,
        "bg_json": bg_json,
        "text_json": text_json,
        "bg_effective": bg_effective,
        "header_overlay_bg": header_overlay_bg,
        "body_fg": body_fg,
        "body_dim_fg": body_dim_fg,
        "trace_path_prefix": base_path or "",
    }
