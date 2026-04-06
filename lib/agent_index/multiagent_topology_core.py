from __future__ import annotations


def parse_user_pane_spec(spec: str) -> tuple[int, int]:
    """Parse multiagent --user-pane spec into (top_count, bottom_count).

    Supported examples:
      - "none"
      - "top"
      - "bottom:2"
      - "top:1,bottom:2"
    """
    raw = (spec or "").strip()
    if raw == "none":
        return 0, 0

    top = 0
    bottom = 0
    if not raw:
        raise ValueError("empty user-pane spec")

    for part in [item.strip() for item in raw.split(",") if item.strip()]:
        if ":" in part:
            side, count_raw = part.split(":", 1)
            side = side.strip()
            count_raw = count_raw.strip()
        else:
            side, count_raw = part, "1"
        if not count_raw.isdigit() or int(count_raw) <= 0:
            raise ValueError(f"invalid pane count in spec: {part}")
        count = int(count_raw)
        if side == "top":
            top = count
        elif side == "bottom":
            bottom = count
        else:
            raise ValueError(f"invalid pane side in spec: {part}")

    if top <= 0 and bottom <= 0:
        raise ValueError("user-pane spec must include top or bottom count")

    return top, bottom
