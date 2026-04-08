from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import quote as url_quote


def normalized_font_label(name: str) -> str:
    label = re.sub(r"\.(ttf|ttc|otf)$", "", name, flags=re.IGNORECASE)
    label = re.sub(
        r"[-_](Variable|Italic|Italics|Roman|Romans|Regular|Medium|Light|Bold|Heavy|Black|Condensed|Rounded|Mono)\b",
        "",
        label,
        flags=re.IGNORECASE,
    )
    label = re.sub(r"\s+", " ", label).strip(" -_")
    return label


def available_chat_font_choices(*, path_class=Path, normalized_font_label_fn=normalized_font_label):
    seen = set()
    choices = [
        ("preset-gothic", "Default Gothic"),
        ("preset-mincho", "Default Mincho"),
    ]
    curated_families = [
        ("system:Hiragino Sans", "Hiragino Sans"),
        ("system:Hiragino Kaku Gothic ProN", "Hiragino Kaku Gothic ProN"),
        ("system:Hiragino Maru Gothic ProN", "Hiragino Maru Gothic ProN"),
        ("system:Hiragino Mincho ProN", "Hiragino Mincho ProN"),
        ("system:Yu Gothic", "Yu Gothic"),
        ("system:Yu Gothic UI", "Yu Gothic UI"),
        ("system:Yu Mincho", "Yu Mincho"),
        ("system:Meiryo", "Meiryo"),
        ("system:BIZ UDPGothic", "BIZ UDPGothic"),
        ("system:BIZ UDPMincho", "BIZ UDPMincho"),
        ("system:Noto Sans JP", "Noto Sans JP"),
        ("system:Noto Serif JP", "Noto Serif JP"),
        ("system:Zen Kaku Gothic New", "Zen Kaku Gothic New"),
        ("system:Zen Maru Gothic", "Zen Maru Gothic"),
        ("system:Shippori Mincho", "Shippori Mincho"),
        ("system:Sawarabi Gothic", "Sawarabi Gothic"),
        ("system:Sawarabi Mincho", "Sawarabi Mincho"),
    ]
    for value, label in curated_families:
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        choices.append((value, label))
    for root in (
        path_class("/System/Library/Fonts"),
        path_class("/Library/Fonts"),
        path_class.home() / "Library/Fonts",
    ):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
                continue
            label = normalized_font_label_fn(path.name)
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            choices.append((f"system:{label}", label))
            if len(choices) >= 96:
                break
        if len(choices) >= 96:
            break
    return choices


def hub_settings_html(
    *,
    saved: bool,
    load_hub_settings_fn,
    available_chat_font_choices_fn,
    settings_template: str,
    pwa_hub_manifest_url: str,
    pwa_icon_192_url: str,
    pwa_apple_touch_icon_url: str,
    hub_header_css: str,
    hub_header_html: str,
    hub_header_js: str,
):
    settings = load_hub_settings_fn()
    font_mode = settings["agent_font_mode"]
    user_message_font = settings.get("user_message_font", "preset-gothic")
    agent_message_font = settings.get("agent_message_font", "preset-mincho")
    message_text_size = int(settings.get("message_text_size", 13) or 13)
    chat_auto = settings.get("chat_auto_mode", False)
    chat_awake = settings.get("chat_awake", False)
    chat_sound = settings.get("chat_sound", False)
    chat_browser_notifications = settings.get("chat_browser_notifications", False)
    bold_mode_mobile = settings.get("bold_mode_mobile", False)
    bold_mode_desktop = settings.get("bold_mode_desktop", False)
    font_choices = available_chat_font_choices_fn()
    font_options = lambda selected: "".join(
        f'<option value="{html.escape(value)}"' + (' selected' if value == selected else '') + f'>{html.escape(label)}</option>'
        for value, label in font_choices
    )
    notice = '<div style="margin:0 0 14px;color:rgb(170,190,172);font-size:13px;line-height:1.5;">Saved.</div>' if saved else ""
    page = settings_template
    page = (
        page
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__NOTICE_HTML__", notice)
        .replace("__USER_MESSAGE_FONT_OPTIONS__", font_options(user_message_font))
        .replace("__AGENT_MESSAGE_FONT_OPTIONS__", font_options(agent_message_font))
        .replace("__FONT_MODE__", font_mode)
        .replace("__MESSAGE_TEXT_SIZE__", str(message_text_size))
        .replace("__CHAT_AUTO_CHECKED__", " checked" if chat_auto else "")
        .replace("__CHAT_AWAKE_CHECKED__", " checked" if chat_awake else "")
        .replace("__CHAT_SOUND_CHECKED__", " checked" if chat_sound else "")
        .replace("__CHAT_BROWSER_NOTIF_CHECKED__", " checked" if chat_browser_notifications else "")
        .replace("__BOLD_MODE_MOBILE_CHECKED__", " checked" if bold_mode_mobile else "")
        .replace("__BOLD_MODE_DESKTOP_CHECKED__", " checked" if bold_mode_desktop else "")
    )
    return (
        page
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
    )


def hub_crons_html(
    *,
    jobs,
    session_records,
    notice="",
    prefill_session="",
    prefill_agent="",
    edit_job=None,
    load_hub_settings_fn,
    all_agent_names,
    crons_template: str,
    pwa_hub_manifest_url: str,
    pwa_icon_192_url: str,
    pwa_apple_touch_icon_url: str,
    hub_header_css: str,
    hub_header_html: str,
    hub_header_js: str,
):
    settings = load_hub_settings_fn()
    session_map = {}
    for record in session_records or []:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or "").strip()
        if not name or name in session_map:
            continue
        session_map[name] = {
            "name": name,
            "agents": [str(agent).strip() for agent in (record.get("agents") or []) if str(agent).strip()],
            "status": str(record.get("status") or "").strip(),
        }

    selected_session = str((edit_job or {}).get("session") or prefill_session or "").strip()
    selected_agent = str((edit_job or {}).get("agent") or prefill_agent or "").strip()
    if selected_session and selected_session not in session_map:
        session_map[selected_session] = {
            "name": selected_session,
            "agents": [selected_agent] if selected_agent else [],
            "status": "unknown",
        }
    if selected_session and selected_agent and selected_agent not in session_map.get(selected_session, {}).get("agents", []):
        session_map[selected_session]["agents"] = [*session_map[selected_session].get("agents", []), selected_agent]

    all_agents = []
    seen_agents = set()
    for agent in all_agent_names:
        if agent not in seen_agents:
            seen_agents.add(agent)
            all_agents.append(agent)
    for record in session_map.values():
        for agent in record.get("agents", []):
            if agent not in seen_agents:
                seen_agents.add(agent)
                all_agents.append(agent)
    if selected_agent and selected_agent not in seen_agents:
        seen_agents.add(selected_agent)
        all_agents.append(selected_agent)

    def _session_option(name: str, label: str, is_selected: bool) -> str:
        selected_attr = ' selected' if is_selected else ''
        return f'<option value="{html.escape(name)}"{selected_attr}>{html.escape(label)}</option>'

    session_options = ['<option value="">Select session</option>']
    for name in sorted(session_map.keys(), key=lambda item: item.lower()):
        record = session_map[name]
        status = str(record.get("status") or "").strip()
        label = name if not status else f"{name} ({status})"
        session_options.append(_session_option(name, label, name == selected_session))
    session_options_html = "".join(session_options)

    initial_agent_options = ['<option value="">Select agent</option>']
    for agent in (session_map.get(selected_session, {}).get("agents") or all_agents):
        selected_attr = ' selected' if agent == selected_agent else ''
        initial_agent_options.append(f'<option value="{html.escape(agent)}"{selected_attr}>{html.escape(agent)}</option>')
    initial_agent_values = {
        str(agent).strip()
        for agent in (session_map.get(selected_session, {}).get("agents") or all_agents)
        if str(agent).strip()
    }
    if selected_agent and selected_agent not in initial_agent_values:
        initial_agent_options.append(
            f'<option value="{html.escape(selected_agent)}" selected>{html.escape(selected_agent)}</option>'
        )
    agent_options_html = "".join(initial_agent_options)

    notice_html = (
        f'<div class="notice">{html.escape(str(notice or "").strip())}</div>'
        if str(notice or "").strip()
        else ""
    )

    jobs_html = []
    for job in jobs or []:
        job_id = str(job.get("id") or "").strip()
        name = html.escape(str(job.get("name") or "").strip() or "Untitled cron")
        session_name = str(job.get("session") or "").strip()
        agent = str(job.get("agent") or "").strip()
        schedule = html.escape(str(job.get("schedule_label") or "").strip() or "Daily")
        next_run = html.escape(str(job.get("next_run_at") or "").strip() or "—")
        last_run = html.escape(str(job.get("last_run_at") or "").strip() or "—")
        last_status = html.escape(str(job.get("last_status") or "").strip() or "idle")
        last_detail = html.escape(str(job.get("last_status_detail") or "").strip() or "")
        enabled = bool(job.get("enabled"))
        checked_attr = " checked" if enabled else ""
        open_href = f"/open-session?session={url_quote(session_name)}" if session_name else "/"
        edit_href = f"/crons?edit={url_quote(job_id)}"
        prompt_source = str(job.get("prompt") or "").strip()
        prompt_preview_raw = next((line.strip() for line in prompt_source.splitlines() if line.strip()), "")
        if not prompt_preview_raw:
            prompt_preview_raw = "No prompt"
        if len(prompt_preview_raw) > 180:
            prompt_preview_raw = f"{prompt_preview_raw[:179].rstrip()}…"
        prompt_preview = html.escape(prompt_preview_raw)
        jobs_html.append(
            f'''
            <div class="swipe-row" data-job-id="{html.escape(job_id)}">
              <div class="swipe-act swipe-act-right" data-action="delete">
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                <span>Delete</span>
              </div>
              <div class="mob-session-row cron-job-row" tabindex="0">
                <div class="mob-row-head">
                  <button class="mob-row-expand-btn" data-expand-row="1" type="button" aria-label="Toggle cron details">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                  </button>
                  <div class="mob-row-name">{name}</div>
                  <div class="mob-row-tools">
                    <form class="cron-enable-form" method="post" action="/crons/toggle" data-stop-row="1">
                      <input type="hidden" name="id" value="{html.escape(job_id)}">
                      <input type="hidden" name="enabled" value="{'1' if enabled else '0'}">
                      <label class="cron-switch" data-stop-row="1" title="Enable or disable this cron">
                        <input class="cron-switch-input" type="checkbox"{checked_attr} data-stop-row="1" aria-label="Enable or disable this cron">
                        <span class="cron-switch-ui" aria-hidden="true"></span>
                      </label>
                    </form>
                  </div>
                </div>
                <div class="mob-row-preview">{schedule} · {html.escape(session_name or "—")} · {html.escape(agent or "—")}</div>
                <div class="mob-row-detail">
                  <div class="cron-detail-copy">{prompt_preview}</div>
                  <div class="mob-row-meta">
                    <span><strong>Next</strong> {next_run}</span>
                    <span><strong>Last</strong> {last_run}</span>
                    <span><strong>Status</strong> {last_status}</span>
                  </div>
                  {f'<div class="cron-detail-note">{last_detail}</div>' if last_detail else ''}
                  <div class="cron-detail-actions" data-stop-row="1">
                    <a class="card-link" href="{edit_href}" data-stop-row="1">Edit</a>
                    <a class="card-link" href="{open_href}" data-stop-row="1">Open</a>
                    <form method="post" action="/crons/run" data-stop-row="1">
                      <input type="hidden" name="id" value="{html.escape(job_id)}">
                      <button class="card-link" type="submit">Run now</button>
                    </form>
                  </div>
                </div>
              </div>
              <form class="cron-delete-form" method="post" action="/crons/delete" onsubmit="return window.confirm('Delete this cron?');">
                <input type="hidden" name="id" value="{html.escape(job_id)}">
              </form>
            </div>
            '''
        )
    jobs_html_str = "".join(jobs_html) or '<div class="mob-empty">No cron jobs yet.</div>'

    current_name = html.escape(str((edit_job or {}).get("name") or "").strip())
    current_time = html.escape(str((edit_job or {}).get("time") or "").strip())
    current_prompt = html.escape(str((edit_job or {}).get("prompt") or "").strip())
    current_enabled = bool((edit_job or {}).get("enabled", True))
    current_id = html.escape(str((edit_job or {}).get("id") or "").strip())
    form_enabled_value = "1" if current_enabled else "0"
    form_row_html = (
        "Edit Cron"
        if edit_job
        else '<span class="cron-compose-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg><span>New Cron</span></span>'
    )
    form_expanded = " expanded" if (edit_job or not jobs or prefill_session or prefill_agent) else ""
    total_jobs = len(jobs or [])
    enabled_jobs = sum(1 for job in (jobs or []) if bool(job.get("enabled")))
    paused_jobs = max(0, total_jobs - enabled_jobs)
    sessions_json = json.dumps(list(session_map.values()), ensure_ascii=False).replace("</", "<\\/")
    all_agents_json = json.dumps(all_agents, ensure_ascii=False).replace("</", "<\\/")
    preferred_agent_json = json.dumps(selected_agent or "", ensure_ascii=False).replace("</", "<\\/")

    return (
        crons_template
        .replace("__HUB_MANIFEST_URL__", pwa_hub_manifest_url)
        .replace("__PWA_ICON_192_URL__", pwa_icon_192_url)
        .replace("__APPLE_TOUCH_ICON_URL__", pwa_apple_touch_icon_url)
        .replace("__HUB_HEADER_CSS__", hub_header_css)
        .replace("__HUB_HEADER_HTML__", hub_header_html)
        .replace("__HUB_HEADER_JS__", hub_header_js)
        .replace("__NOTICE_HTML__", notice_html)
        .replace("__FORM_ID__", current_id)
        .replace("__FORM_NAME__", current_name)
        .replace("__FORM_TIME__", current_time)
        .replace("__FORM_PROMPT__", current_prompt)
        .replace("__FORM_ENABLED_VALUE__", form_enabled_value)
        .replace("__FORM_ROW_HTML__", form_row_html)
        .replace("__FORM_EXPANDED__", form_expanded)
        .replace("__SESSION_OPTIONS__", session_options_html)
        .replace("__AGENT_OPTIONS__", agent_options_html)
        .replace("__CRON_ROWS__", jobs_html_str)
        .replace("__CRON_TOTAL__", str(total_jobs))
        .replace("__CRON_ENABLED__", str(enabled_jobs))
        .replace("__CRON_PAUSED__", str(paused_jobs))
        .replace("__CRON_SESSIONS_JSON__", sessions_json)
        .replace("__CRON_ALL_AGENTS_JSON__", all_agents_json)
        .replace("__PREFERRED_AGENT__", preferred_agent_json)
    )
