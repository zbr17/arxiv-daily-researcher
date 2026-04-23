#!/usr/bin/env python3
"""
ArXiv Daily Researcher - Simple Log/HTML Viewer

轻量化 WebUI：仅用于查看日志与 HTML 文件，不包含配置编辑能力。
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, List, NamedTuple

import streamlit as st
import streamlit.components.v1 as components


class FileItem(NamedTuple):
    path: Path
    label: str
    date_key: str


class HtmlItem(NamedTuple):
    path: Path
    label: str
    date_key: str
    source: str
    report_type: str


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _PROJECT_ROOT / "logs"
_REPORTS_DIR = _PROJECT_ROOT / "data" / "reports"

_LOG_DATE_PAT = re.compile(r"^(daily|trend|cron|startup)_(\d{8})_\d{6}\.log$")
_JSON_LINE_PATTERNS = {
    "overall": re.compile(r"\[ArXiv\]\[OverallStats\]\s+(\{.*\})"),
    "domain": re.compile(r"\[ArXiv\]\[DomainStats\]\s+(\{.*\})"),
    "filtered": re.compile(r"\[ArXiv\]\[FilteredByDate\]\s+(\{.*\})"),
}


def _date_from_yyyymmdd(v: str) -> str:
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"


def _extract_dates_from_name(stem: str) -> List[str]:
    return re.findall(r"\d{4}-\d{2}-\d{2}", stem)


def _safe_json_from_line(line: str, pat: re.Pattern) -> dict | None:
    m = pat.search(line)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _inject_custom_css() -> None:
    st.markdown(
        """
<style>
    .main .block-container {
        padding-top: 1.2rem;
    }
    .hero-card {
        background: linear-gradient(135deg, #0b5fff 0%, #06a5a1 100%);
        border-radius: 16px;
        padding: 16px 20px;
        color: #ffffff;
        box-shadow: 0 10px 30px rgba(9, 71, 181, 0.20);
        margin-bottom: 0.8rem;
    }
    .hero-title {
        font-size: 1.6rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.25;
    }
    .hero-sub {
        opacity: 0.95;
        margin-top: 6px;
        font-size: 0.96rem;
    }
    .tab-tip {
        font-size: 0.92rem;
        color: #4b5563;
        background: #f5f8ff;
        border: 1px solid #dbe6ff;
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 10px;
    }
    .src-label {
        font-size: 0.9rem;
        color: #334155;
        margin-top: 0.2rem;
        margin-bottom: 0.4rem;
        font-weight: 600;
    }
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=10)
def discover_logs() -> Dict[str, List[FileItem]]:
    grouped: Dict[str, List[FileItem]] = {}
    if not _LOG_DIR.exists():
        return grouped

    for f in _LOG_DIR.glob("*.log"):
        m = _LOG_DATE_PAT.match(f.name)
        if m:
            date_key = _date_from_yyyymmdd(m.group(2))
        else:
            date_key = dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")

        stat = f.stat()
        size_kb = stat.st_size / 1024
        mtime = dt.datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M:%S")
        label = f"{f.name}  ({size_kb:.1f} KB, {mtime})"
        grouped.setdefault(date_key, []).append(FileItem(path=f, label=label, date_key=date_key))

    for k in grouped:
        grouped[k].sort(key=lambda x: x.path.stat().st_mtime, reverse=True)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0], reverse=True))


@st.cache_data(ttl=10)
def build_daily_curve_data() -> List[dict]:
    rows = []
    grouped = discover_logs()
    daily_sum: Dict[str, dict] = {}

    for date_key, files in grouped.items():
        day_raw = 0
        day_filtered = 0
        day_kept = 0
        run_count = 0

        for item in files:
            try:
                for line in item.path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    rec = _safe_json_from_line(line, _JSON_LINE_PATTERNS["overall"])
                    if not rec:
                        continue
                    day_raw += int(rec.get("raw_total", 0))
                    day_filtered += int(rec.get("date_filtered", 0))
                    day_kept += int(rec.get("kept", 0))
                    run_count += 1
            except Exception:
                continue

        if run_count > 0:
            daily_sum[date_key] = {
                "raw_total": day_raw,
                "date_filtered": day_filtered,
                "kept": day_kept,
            }

    for date_key in sorted(daily_sum.keys()):
        rows.append({"date": date_key, "metric": "raw_total", "value": daily_sum[date_key]["raw_total"]})
        rows.append(
            {
                "date": date_key,
                "metric": "date_filtered",
                "value": daily_sum[date_key]["date_filtered"],
            }
        )
        rows.append({"date": date_key, "metric": "kept", "value": daily_sum[date_key]["kept"]})

    return rows


@st.cache_data(ttl=10)
def discover_html_files() -> Dict[str, List[HtmlItem]]:
    grouped: Dict[str, List[HtmlItem]] = {}
    if not _REPORTS_DIR.exists():
        return grouped

    candidates: List[HtmlItem] = []

    for f in (_REPORTS_DIR / "daily_research" / "html").glob("*/*.html"):
        source = f.parent.name
        candidates.append(
            HtmlItem(
                path=f,
                label="",
                date_key="",
                source=source,
                report_type="daily_research",
            )
        )

    for f in (_REPORTS_DIR / "trend_research" / "html").glob("*/*.html"):
        source = f.parent.name
        candidates.append(
            HtmlItem(
                path=f,
                label="",
                date_key="",
                source=source,
                report_type="trend_research",
            )
        )

    for f in (_REPORTS_DIR / "keyword_trend" / "html").glob("*.html"):
        candidates.append(
            HtmlItem(
                path=f,
                label="",
                date_key="",
                source="keyword_trend",
                report_type="keyword_trend",
            )
        )

    for item in candidates:
        f = item.path
        dates = _extract_dates_from_name(f.stem)
        if not dates:
            dates = [dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")]

        stat = f.stat()
        size_kb = stat.st_size / 1024
        rel = f.relative_to(_PROJECT_ROOT)
        label = f"{rel}  ({size_kb:.1f} KB)"

        for d in dates:
            grouped.setdefault(d, []).append(
                HtmlItem(
                    path=f,
                    label=label,
                    date_key=d,
                    source=item.source,
                    report_type=item.report_type,
                )
            )

    for k in grouped:
        grouped[k].sort(key=lambda x: x.path.stat().st_mtime, reverse=True)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0], reverse=True))


def render_logs_tab() -> None:
    st.subheader("日志查看")
    st.markdown(
        '<div class="tab-tip">按日期查看日志，并展示 ArXiv 过滤前后统计与日期过滤详情。</div>',
        unsafe_allow_html=True,
    )

    grouped = discover_logs()
    if not grouped:
        st.info(f"未发现日志目录或日志文件: `{_LOG_DIR}`")
        return

    curve_data = build_daily_curve_data()
    if curve_data:
        st.markdown("**ArXiv 每日统计曲线**")
        st.vega_lite_chart(
            {"values": curve_data},
            {
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {"field": "date", "type": "temporal", "title": "日期"},
                    "y": {"field": "value", "type": "quantitative", "title": "数量"},
                    "color": {"field": "metric", "type": "nominal", "title": "指标"},
                },
                "height": 320,
            },
            use_container_width=True,
        )

    dates = list(grouped.keys())
    selected_date = st.selectbox("选择日志日期", dates, index=0)
    files = grouped[selected_date]
    label_to_item = {f.label: f for f in files}
    selected_label = st.selectbox("选择日志文件", list(label_to_item.keys()), index=0)
    selected = label_to_item[selected_label]

    lines = selected.path.read_text(encoding="utf-8", errors="ignore").splitlines()
    overall_stats = []
    domain_stats = []
    filtered_details = []

    for line in lines:
        rec = _safe_json_from_line(line, _JSON_LINE_PATTERNS["overall"])
        if rec:
            overall_stats.append(rec)
            continue
        rec = _safe_json_from_line(line, _JSON_LINE_PATTERNS["domain"])
        if rec:
            domain_stats.append(rec)
            continue
        rec = _safe_json_from_line(line, _JSON_LINE_PATTERNS["filtered"])
        if rec:
            filtered_details.append(rec)

    if overall_stats:
        last = overall_stats[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("原始论文数(raw_total)", int(last.get("raw_total", 0)))
        c2.metric("被日期过滤(date_filtered)", int(last.get("date_filtered", 0)))
        c3.metric("最终保留(kept)", int(last.get("kept", 0)))

    if domain_stats:
        st.markdown("**分领域统计**")
        st.dataframe(domain_stats, use_container_width=True, hide_index=True)

    if filtered_details:
        st.markdown("**被日期过滤论文详情**")
        show_n = st.slider("显示条数", min_value=10, max_value=min(500, len(filtered_details)), value=min(100, len(filtered_details)))
        st.dataframe(filtered_details[:show_n], use_container_width=True, hide_index=True)

    st.markdown("**日志原文**")
    max_lines = st.slider("展示最后 N 行", min_value=50, max_value=5000, value=600, step=50)
    tail = "\n".join(lines[-max_lines:])
    st.text_area("log tail", tail, height=420)


def render_html_tab() -> None:
    st.subheader("HTML 查看")
    st.markdown(
        '<div class="tab-tip">按日期和来源快速定位 HTML；默认源码预览（低内存），可切换渲染模式。</div>',
        unsafe_allow_html=True,
    )

    grouped = discover_html_files()
    if not grouped:
        st.info(f"未发现 HTML 报告文件: `{_REPORTS_DIR}`")
        return

    dates = list(grouped.keys())
    selected_date = st.selectbox("选择 HTML 日期", dates, index=0)
    files = grouped[selected_date]

    # 一级：来源按钮（arxiv/nature/...）
    by_source: Dict[str, List[HtmlItem]] = {}
    for f in files:
        by_source.setdefault(f.source, []).append(f)

    sources = sorted(by_source.keys())
    if not sources:
        st.info("当前日期没有可用 HTML 文件。")
        return

    if "selected_html_source" not in st.session_state or st.session_state["selected_html_source"] not in sources:
        st.session_state["selected_html_source"] = sources[0]

    st.markdown('<div class="src-label">选择来源</div>', unsafe_allow_html=True)
    source_cols = st.columns(min(6, len(sources)))
    for idx, source in enumerate(sources):
        col = source_cols[idx % len(source_cols)]
        btn_type = "primary" if source == st.session_state["selected_html_source"] else "secondary"
        if col.button(source, key=f"src_btn_{selected_date}_{source}", type=btn_type, use_container_width=True):
            st.session_state["selected_html_source"] = source

    selected_source = st.session_state["selected_html_source"]
    source_files = by_source.get(selected_source, [])
    if not source_files:
        st.info("当前来源没有可用 HTML 文件。")
        return

    # 二级：具体文件
    label_to_item = {f.label: f for f in source_files}
    selected_label = st.selectbox("选择具体 HTML 文件", list(label_to_item.keys()), index=0)
    selected = label_to_item[selected_label]

    stat = selected.path.stat()
    st.caption(
        f"{selected.path.relative_to(_PROJECT_ROOT)} | {stat.st_size / 1024:.1f} KB | "
        f"更新时间: {dt.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    html_content = selected.path.read_text(encoding="utf-8", errors="ignore")
    st.download_button(
        label="下载当前 HTML",
        data=html_content,
        file_name=selected.path.name,
        mime="text/html",
    )

    mode = st.radio(
        "预览模式",
        ["源码预览(推荐)", "渲染预览(占用更高)"],
        horizontal=True,
    )

    if mode == "源码预览(推荐)":
        lines = html_content.splitlines()
        max_lines = st.slider("展示前 N 行", min_value=50, max_value=min(4000, max(50, len(lines))), value=min(500, max(50, len(lines))))
        st.code("\n".join(lines[:max_lines]), language="html")
        return

    height = st.slider("渲染高度", min_value=400, max_value=2200, value=900, step=100)
    components.html(html_content, height=height, scrolling=True)


def main() -> None:
    st.set_page_config(page_title="ArXiv Simple Viewer", page_icon="📄", layout="wide")
    _inject_custom_css()
    st.markdown(
        """
        <div class="hero-card">
            <p class="hero-title">论文运行观测台</p>
            <div class="hero-sub">轻量查看日志曲线与 HTML 报告，不包含配置编辑功能</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_logs, tab_html = st.tabs(["📘 日志中心", "📄 HTML 报告"])
    with tab_logs:
        render_logs_tab()
    with tab_html:
        render_html_tab()


if __name__ == "__main__":
    main()
