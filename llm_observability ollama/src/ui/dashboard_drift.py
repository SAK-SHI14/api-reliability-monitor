"""
Drift & Trace Dashboard — Streamlit page.

Renders:
  1. Live canary health summary (last run results)
  2. Per-prompt-hash drift timeline (cosine sim, length z-score, quality rates)
  3. Trace explorer — searchable/filterable table of all recent traces
  4. Cost attribution heatmap by tag
"""

import json
import time
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.storage.trace_store import TraceStore
from src.drift.drift_detector import DriftDetector, DriftReport


SEVERITY_COLOUR = {
    "none":     "#22c55e",   # green
    "warning":  "#f59e0b",   # amber
    "critical": "#ef4444",   # red
}


def render_drift_dashboard(store: TraceStore, detector: DriftDetector):
    st.set_page_config(
        page_title="LLM Drift & Trace Monitor",
        layout="wide",
        page_icon="🔬",
    )
    st.title("🔬 LLM Drift & Trace Monitor")

    # ── Top-level metrics ─────────────────────────────────────────────
    model_summary = store.get_model_summary(days=7)
    recent_traces = store.get_recent_traces(hours=24)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Traces (24 h)", len(recent_traces))
    avg_ttft = sum(t["ttft_ms"] for t in recent_traces) / max(len(recent_traces), 1)
    col2.metric("Avg TTFT (ms)", f"{avg_ttft:.0f}")
    avg_tps = sum(t["tokens_per_second"] for t in recent_traces) / max(len(recent_traces), 1)
    col3.metric("Avg Throughput (tok/s)", f"{avg_tps:.1f}")
    truncated = sum(1 for t in recent_traces if t["is_truncated"])
    col4.metric("Truncations (24 h)", truncated)

    st.divider()

    # ── Drift analysis ────────────────────────────────────────────────
    st.subheader("📡 Model Drift Analysis")

    reports: list[DriftReport] = detector.analyse_all(days=30)

    if not reports:
        st.info("Not enough trace history yet. Drift analysis requires at least 30 traces per prompt hash.")
    else:
        # Summary cards
        drifted = [r for r in reports if r.overall_drifted]
        stable  = [r for r in reports if not r.overall_drifted]

        dcol1, dcol2, dcol3 = st.columns(3)
        dcol1.metric("Prompts monitored", len(reports))
        dcol2.metric("Drifted", len(drifted), delta=f"{len(drifted)} need attention" if drifted else None, delta_color="inverse")
        dcol3.metric("Stable", len(stable))

        for report in sorted(reports, key=lambda r: r.severity, reverse=True):
            colour = SEVERITY_COLOUR[report.severity]
            with st.expander(
                f"{report.prompt_hash[:8]}… — {report.model} [{report.severity.upper()}]",
                expanded=report.severity in ("critical", "warning"),
            ):
                st.markdown(f"**{report.summary}**")

                # Signal table
                signal_rows = [
                    {
                        "Signal": s.name.replace("_", " ").title(),
                        "Value": round(s.value, 4),
                        "Threshold": s.threshold,
                        "Drifted": "🔴 Yes" if s.is_drifted else "🟢 No",
                        "Detail": s.description,
                    }
                    for s in report.signals
                ]
                st.dataframe(pd.DataFrame(signal_rows), use_container_width=True, hide_index=True)

                # Baseline vs Current stats
                b, c = report.baseline, report.current
                compare_rows = [
                    {"Metric": "Avg response length (chars)", "Baseline": f"{b.avg_response_length:.0f}", "Current": f"{c.avg_response_length:.0f}"},
                    {"Metric": "Avg latency (ms)",            "Baseline": f"{b.avg_latency_ms:.0f}",      "Current": f"{c.avg_latency_ms:.0f}"},
                    {"Metric": "Avg TTFT (ms)",               "Baseline": f"{b.avg_ttft_ms:.0f}",         "Current": f"{c.avg_ttft_ms:.0f}"},
                    {"Metric": "Avg tokens/sec",              "Baseline": f"{b.avg_tokens_per_second:.1f}","Current": f"{c.avg_tokens_per_second:.1f}"},
                    {"Metric": "Truncation rate",             "Baseline": f"{b.truncation_rate:.1%}",      "Current": f"{c.truncation_rate:.1%}"},
                    {"Metric": "Refusal rate",                "Baseline": f"{b.refusal_rate:.1%}",         "Current": f"{c.refusal_rate:.1%}"},
                ]
                st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

    st.divider()

    # ── Per-hash trace timeline ───────────────────────────────────────
    st.subheader("📈 Per-Prompt Trace Timeline")

    all_hashes = store.get_all_tracked_hashes()
    if all_hashes:
        selected_hash = st.selectbox(
            "Select prompt hash",
            options=all_hashes,
            format_func=lambda h: f"{h[:8]}…",
        )
        traces = store.get_traces_for_hash(selected_hash, days=30)

        if traces:
            df = pd.DataFrame(traces)
            df["datetime"] = pd.to_datetime(df["request_ts"], unit="s", utc=True)

            tab1, tab2, tab3 = st.tabs(["Response length", "Latency & TTFT", "Tokens/sec"])

            with tab1:
                fig = px.line(
                    df, x="datetime", y="response_length",
                    title="Response length over time",
                    labels={"response_length": "Chars", "datetime": ""},
                )
                fig.add_hline(
                    y=df["response_length"].mean(),
                    line_dash="dash", line_color="gray",
                    annotation_text="mean",
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df["datetime"], y=df["total_latency_ms"], name="Total latency"))
                fig2.add_trace(go.Scatter(x=df["datetime"], y=df["ttft_ms"], name="TTFT"))
                fig2.update_layout(title="Latency over time (ms)", xaxis_title="", yaxis_title="ms")
                st.plotly_chart(fig2, use_container_width=True)

            with tab3:
                fig3 = px.line(
                    df, x="datetime", y="tokens_per_second",
                    title="Throughput (tokens/sec)",
                )
                st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No traces recorded yet.")

    st.divider()

    # ── Trace explorer ────────────────────────────────────────────────
    st.subheader("🔍 Trace Explorer")

    recent = store.get_recent_traces(hours=48, limit=500)
    if recent:
        df_exp = pd.DataFrame(recent)
        df_exp["datetime"] = pd.to_datetime(df_exp["request_ts"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
        df_exp["cost"] = df_exp["estimated_cost_usd"].map(lambda x: f"${x:.5f}")
        df_exp["truncated"] = df_exp["is_truncated"].map(lambda x: "⚠️" if x else "")
        df_exp["refusal"]   = df_exp["is_refusal"].map(lambda x: "🚫" if x else "")

        display_cols = [
            "datetime", "prompt_hash", "model", "provider",
            "prompt_tokens", "completion_tokens",
            "ttft_ms", "total_latency_ms", "tokens_per_second",
            "cost", "finish_reason", "truncated", "refusal",
        ]
        df_exp["prompt_hash"] = df_exp["prompt_hash"].str[:8] + "…"

        # Filter controls
        fcol1, fcol2 = st.columns(2)
        models = ["All"] + sorted(df_exp["model"].unique().tolist())
        sel_model = fcol1.selectbox("Filter by model", models)
        sel_finish = fcol2.selectbox("Filter by finish reason", ["All", "stop", "length", "error", "content_filter"])

        mask = pd.Series([True] * len(df_exp))
        if sel_model != "All":
            mask &= df_exp["model"] == sel_model
        if sel_finish != "All":
            mask &= df_exp["finish_reason"] == sel_finish

        st.dataframe(
            df_exp[mask][display_cols].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recent traces.")

    st.divider()

    # ── Throughput analysis (replaces cost attribution — Ollama is free) ──
    st.subheader("⚡ Throughput & Hardware Performance")

    tag_key = st.text_input("Group throughput by tag key", value="feature")
    cost_data = store.get_cost_by_tag(tag_key, days=30)

    if recent:
        df_tps = pd.DataFrame(recent)
        df_tps["datetime"] = pd.to_datetime(df_tps["request_ts"], unit="s", utc=True)
        df_tps = df_tps[df_tps["tokens_per_second"] > 0]

        if not df_tps.empty:
            fig_tps = px.line(
                df_tps.sort_values("datetime"),
                x="datetime", y="tokens_per_second",
                color="model",
                title="Tokens/sec over time (higher = faster local inference)",
                labels={"tokens_per_second": "tok/s", "datetime": ""},
            )
            st.plotly_chart(fig_tps, use_container_width=True)

            # Model comparison bar
            model_tps = (
                df_tps.groupby("model")["tokens_per_second"]
                .mean()
                .reset_index()
                .sort_values("tokens_per_second", ascending=False)
            )
            fig_bar = px.bar(
                model_tps, x="model", y="tokens_per_second",
                title="Average throughput by model",
                labels={"tokens_per_second": "avg tok/s"},
                color="tokens_per_second",
                color_continuous_scale="Greens",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No throughput data yet.")

    # Auto-refresh
    time.sleep(30)
    st.rerun()


if __name__ == "__main__":
    # Standalone entrypoint: streamlit run dashboard_drift.py
    store = TraceStore("data/observability.db")
    detector = DriftDetector(store)
    render_drift_dashboard(store, detector)
