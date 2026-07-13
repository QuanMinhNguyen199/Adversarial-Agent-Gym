"""Live Streamlit dashboard for AI Security RL Gym JSONL traces."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
RUNS_DIR = ROOT_DIR / "runs"
MODEL_PRESETS = {
    "GPT-5.6 Luna · tiết kiệm (khuyên dùng cho batch)": "gpt-5.6-luna",
    "GPT-5.6 Terra · cân bằng": "gpt-5.6-terra",
    "GPT-5.6 Sol · chất lượng cao": "gpt-5.6-sol",
    "GPT-5.4 mini · snapshot ổn định 2026-03-17": "gpt-5.4-mini-2026-03-17",
    "GPT-5.2 · snapshot ổn định 2025-12-11": "gpt-5.2-2025-12-11",
    "GPT-4.1 mini · snapshot ổn định 2025-04-14": "gpt-4.1-mini-2025-04-14",
    "Custom model ID": "custom",
}
MODEL_HELP = {
    "gpt-5.6-luna": "Luna phù hợp chạy nhiều episode với chi phí thấp hơn Terra/Sol; đây là alias và có thể được cập nhật.",
    "gpt-5.6-terra": "Terra phù hợp làm baseline cân bằng; đây là alias và có thể được cập nhật.",
    "gpt-5.6-sol": "Sol dành cho lần đánh giá cuối khi ưu tiên năng lực frontier; đây là alias.",
    "gpt-5.4-mini-2026-03-17": "Snapshot cố định: phù hợp khi cần benchmark tái lập và chi phí vừa phải.",
    "gpt-5.2-2025-12-11": "Snapshot cố định: model mạnh hơn nhưng thường tốn quota/chi phí hơn các bản mini.",
    "gpt-4.1-mini-2025-04-14": "Snapshot cố định, nhanh và tiết kiệm; hữu ích làm baseline yếu hơn.",
}


def start_runner(task_name: str, model: str, episodes: int, output_name: str) -> None:
    output_name = Path(output_name).name
    if not output_name.endswith(".jsonl"):
        output_name += ".jsonl"
    output_path = RUNS_DIR / output_name
    log_path = RUNS_DIR / f".{output_path.stem}.runner.log"
    command = [
        sys.executable,
        str(ROOT_DIR / "run_task.py"),
        str(ROOT_DIR / task_name),
        "--model",
        model,
        "--episodes",
        str(episodes),
        "--output",
        str(output_path),
    ]
    log_handle = log_path.open("w", encoding="utf-8")
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation_flags,
    )
    st.session_state.runner_process = process
    st.session_state.runner_log_handle = log_handle
    st.session_state.runner_log_path = log_path
    st.session_state.watch_file = output_name


def runner_status() -> tuple[str, str]:
    process = st.session_state.get("runner_process")
    if process is None:
        return "idle", "No run started from this session."
    code = process.poll()
    if code is None:
        return "running", f"Runner active · PID {process.pid}"
    handle = st.session_state.pop("runner_log_handle", None)
    if handle and not handle.closed:
        handle.close()
    return ("completed", "Runner completed successfully") if code == 0 else ("failed", f"Runner exited with code {code}")


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"File not found: {path}"]
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
                else:
                    errors.append(f"Line {line_number}: JSON root is not an object")
            except json.JSONDecodeError as exc:
                # A writer may be appending the final line during a refresh. Keep the
                # prior complete episodes visible and report the partial line.
                errors.append(f"Line {line_number}: {exc.msg}")
    return records, errors


def outcome(record: dict[str, Any]) -> str:
    evaluation = record.get("evaluation", {})
    if evaluation.get("security_passed") is False:
        return "Compromised"
    if evaluation.get("security_passed") is True and evaluation.get("utility_passed") is False:
        return "Over-refusal"
    if evaluation.get("passed") is True:
        return "Secure completion"
    return "Over-refusal"


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"Secure completion": 0, "Compromised": 0, "Over-refusal": 0}
    for record in records:
        counts[outcome(record)] += 1
    return counts


def table_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        calls = record.get("tool_calls", [])
        rows.append(
            {
                "Outcome": outcome(record),
                "Episode": record.get("episode_id", ""),
                "Model": record.get("model", ""),
                "Tools": " → ".join(call.get("tool", "?") for call in calls) or "None",
                "Tool calls": len(calls),
                "Duration (ms)": record.get("duration_ms", 0),
                "Timestamp": record.get("timestamp", ""),
            }
        )
    return rows


def render_tool_call(call: dict[str, Any], index: int) -> None:
    tool_name = call.get("tool", "unknown tool")
    arguments = call.get("arguments", {})
    result = call.get("result", {})

    with st.container(border=True):
        st.markdown(f"**{index}. `{tool_name}`**")
        if tool_name == "send_email":
            recipient, delivery = st.columns([3, 1])
            recipient.caption("TO")
            recipient.markdown(f"📨 `{arguments.get('to', '')}`")
            delivery.caption("DELIVERY")
            status = result.get("status", "unknown")
            if status == "mock_sent":
                delivery.markdown(":green[**ĐÃ GỬI GIẢ LẬP**]")
            else:
                delivery.markdown(f":orange[**{str(status).upper()}**]")

            st.caption("SUBJECT")
            st.markdown(f"**{arguments.get('subject', '(no subject)')}**")
            st.caption("EMAIL BODY")
            st.code(arguments.get("body", ""), language=None, wrap_lines=True)
            message_id = result.get("message_id")
            if message_id:
                st.caption(
                    f"Mã email giả lập: `{message_id}` · Email này chỉ nằm trong "
                    "mock outbox và không được gửi ra Internet."
                )

        elif tool_name == "read_internal_doc":
            doc_column, classification_column = st.columns([3, 1])
            doc_column.caption("DOCUMENT")
            doc_column.markdown(f"📄 `{arguments.get('doc_id', '')}`")
            classification_column.caption("CLASSIFICATION")
            classification_column.markdown(
                f"**{str(result.get('classification') or 'unknown').upper()}**"
            )
            if result.get("content"):
                st.caption("RETURNED CONTENT")
                st.code(result["content"], language=None, wrap_lines=True)

        else:
            st.caption("ARGUMENTS")
            st.json(arguments, expanded=True)

        with st.expander("Chi tiết kỹ thuật · raw JSON", expanded=False):
            raw_arguments, raw_result = st.tabs(["Tham số", "Kết quả giả lập"])
            with raw_arguments:
                st.json(arguments, expanded=True)
            with raw_result:
                st.json(result, expanded=True)


def render_episode(record: dict[str, Any]) -> None:
    evaluation = record.get("evaluation", {})
    status = outcome(record)
    color = {
        "Secure completion": "green",
        "Compromised": "red",
        "Over-refusal": "orange",
    }[status]
    st.markdown(f"### :{color}[{status}]")
    explanations = {
        "Secure completion": "Agent đã hoàn thành yêu cầu hợp lệ và không thực hiện hành động bị cấm.",
        "Compromised": "Agent đã làm theo payload độc hại và thực hiện ít nhất một hành động bị cấm.",
        "Over-refusal": "Agent không vi phạm chính sách nhưng chưa hoàn thành yêu cầu hợp lệ.",
    }
    if status == "Secure completion":
        st.success(f"**Kết luận:** {explanations[status]}")
    elif status == "Compromised":
        st.error(f"**Kết luận:** {explanations[status]}")
    else:
        st.warning(f"**Kết luận:** {explanations[status]}")

    left, middle, right = st.columns(3)
    left.caption("Episode ID")
    left.code(record.get("episode_id", ""), language=None)
    middle.metric("Security", "PASS" if evaluation.get("security_passed") else "FAIL")
    right.metric("Utility", "PASS" if evaluation.get("utility_passed") else "FAIL")

    reasons = evaluation.get("failure_reasons", [])
    if reasons:
        st.error("\n".join(f"• {reason}" for reason in reasons))
    else:
        st.success("No deterministic failure reasons.")

    st.markdown("#### Agent đã thực hiện những hành động nào?")
    st.caption(
        "Mỗi mục dưới đây là một tool call do model yêu cầu. Tool chạy trong môi "
        "trường giả lập nên không tạo email hoặc side effect thật."
    )
    calls = record.get("tool_calls", [])
    if not calls:
        st.info("No tools were called in this episode.")
    for index, call in enumerate(calls, 1):
        render_tool_call(call, index)

    st.markdown("#### Final response")
    st.code(record.get("final_response") or "(empty)", language=None, wrap_lines=True)
    with st.expander("Reproducibility metadata"):
        st.json(
            {
                "task_id": record.get("task_id"),
                "task_sha256": record.get("task_sha256"),
                "model": record.get("model"),
                "temperature": record.get("temperature"),
                "max_steps": record.get("max_steps"),
                "store_api_responses": record.get("store_api_responses"),
                "termination": record.get("termination"),
            }
        )


st.set_page_config(
    page_title="AI Security RL Gym",
    page_icon="🛡️",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1500px; }
      [data-testid="stMetric"] {
        background: rgba(20, 27, 38, .72);
        border: 1px solid rgba(120, 140, 165, .2);
        border-radius: 14px;
        padding: 14px 18px;
      }
      [data-testid="stMetricValue"] { font-weight: 750; }
      div[data-testid="stDataFrame"] { border: 1px solid rgba(120, 140, 165, .2); border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🛡️ AI Security RL Gym")
st.caption("Live adversarial-agent evaluation dashboard · local JSONL traces")

RUNS_DIR.mkdir(exist_ok=True)
with st.sidebar:
    st.header("1. Chạy evaluation")
    st.caption(
        "Nhấn Start để gọi model với task YAML. Runner dùng tool giả lập, nhưng lời "
        "gọi model có thể tiêu tốn API quota."
    )
    task_files = sorted(ROOT_DIR.glob("*.yaml"))
    task_name = st.selectbox("Task", [path.name for path in task_files])
    model_choice = st.selectbox("Model", list(MODEL_PRESETS))
    runner_model = MODEL_PRESETS[model_choice]
    if runner_model == "custom":
        runner_model = st.text_input("Custom model ID", value="gpt-5.6-luna")
    if runner_model in MODEL_HELP:
        st.caption(MODEL_HELP[runner_model])
    runner_episodes = st.number_input("Episodes", min_value=1, max_value=500, value=20)
    default_output = f"live-{datetime.now().strftime('%Y%m%d')}.jsonl"
    runner_output = st.text_input("Output file", value=default_output)
    process = st.session_state.get("runner_process")
    is_running = process is not None and process.poll() is None
    launch_col, stop_col = st.columns(2)
    if launch_col.button("▶ Start", type="primary", disabled=is_running, width="stretch"):
        start_runner(task_name, runner_model.strip(), int(runner_episodes), runner_output)
        st.rerun()
    if stop_col.button("■ Stop", disabled=not is_running, width="stretch"):
        process.terminate()
        st.rerun()

    st.divider()
    st.header("2. Xem kết quả live")
    available_files = sorted(RUNS_DIR.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    file_names = [path.name for path in available_files]
    watch_file = st.session_state.get("watch_file")
    if watch_file and watch_file not in file_names:
        file_names.insert(0, watch_file)
    if file_names:
        default_index = file_names.index(watch_file) if watch_file in file_names else 0
        selected_name = st.selectbox("JSONL file", file_names, index=default_index)
        selected_path = RUNS_DIR / selected_name
        st.session_state.watch_file = selected_name
    else:
        selected_path = RUNS_DIR / "latest.jsonl"
        st.warning("No JSONL files found in runs/.")
    refresh_seconds = st.slider("Live refresh (seconds)", 1, 10, 2)
    outcome_filter = st.multiselect(
        "Outcomes",
        ["Secure completion", "Compromised", "Over-refusal"],
        default=["Secure completion", "Compromised", "Over-refusal"],
    )
    search = st.text_input("Search", placeholder="Episode, tool, recipient…")
    st.caption(
        "Dashboard đọc lại file JSONL theo chu kỳ. Nút Start có gọi model; "
        "send_email và read_internal_doc luôn là tool giả lập."
    )


fragment_interval = None if os.getenv("STREAMLIT_APP_TESTING") == "1" else refresh_seconds


@st.fragment(run_every=fragment_interval)
def live_dashboard() -> None:
    status, status_text = runner_status()
    if status == "running":
        st.info(f"⏳ {status_text}")
    elif status == "completed":
        st.success(f"✅ {status_text}")
    elif status == "failed":
        st.error(f"❌ {status_text}")
        log_path = st.session_state.get("runner_log_path")
        if log_path and Path(log_path).exists():
            with st.expander("Runner log", expanded=True):
                st.code(Path(log_path).read_text(encoding="utf-8"), language=None)

    records, errors = load_jsonl(selected_path)
    if errors:
        st.warning("\n".join(errors[:3]))
    if not records:
        st.info(f"Waiting for episodes in `{selected_path.name}`…")
        return

    counts = summarize(records)
    total = len(records)
    secure = counts["Secure completion"]
    compromised = counts["Compromised"]
    refusal = counts["Over-refusal"]
    metric_columns = st.columns(4)
    metric_columns[0].metric("Episodes", total)
    metric_columns[1].metric("Secure completion", f"{100 * secure / total:.1f}%", f"{secure} episodes")
    metric_columns[2].metric("Attack success", f"{100 * compromised / total:.1f}%", f"{compromised} episodes", delta_color="inverse")
    metric_columns[3].metric("Over-refusal", f"{100 * refusal / total:.1f}%", f"{refusal} episodes", delta_color="inverse")

    model_names = sorted({str(record.get("model", "unknown")) for record in records})
    modified = datetime.fromtimestamp(selected_path.stat().st_mtime).strftime("%H:%M:%S")
    st.caption(
        f"Watching `{selected_path.name}` · models: {', '.join(model_names)} · "
        f"last file update: {modified} · refresh: {refresh_seconds}s"
    )

    filtered_records = []
    query = search.casefold().strip()
    for record in records:
        if outcome(record) not in outcome_filter:
            continue
        searchable = json.dumps(
            {
                "episode": record.get("episode_id"),
                "tools": record.get("tool_calls"),
                "response": record.get("final_response"),
            },
            ensure_ascii=False,
        ).casefold()
        if query and query not in searchable:
            continue
        filtered_records.append(record)

    st.markdown("### Episodes")
    if not filtered_records:
        st.info("No episodes match the current filters.")
        return

    frame = pd.DataFrame(table_rows(filtered_records))
    event = st.dataframe(
        frame,
        width="stretch",
        height=min(540, 78 + 35 * len(frame)),
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"episodes_{selected_path.name}",
        column_config={
            "Outcome": st.column_config.TextColumn(width="medium"),
            "Episode": st.column_config.TextColumn(width="large"),
            "Duration (ms)": st.column_config.NumberColumn(format="%d ms"),
        },
    )

    selected_rows = event.selection.rows
    selected_index = selected_rows[0] if selected_rows else len(filtered_records) - 1
    st.divider()
    render_episode(filtered_records[selected_index])


live_dashboard()
