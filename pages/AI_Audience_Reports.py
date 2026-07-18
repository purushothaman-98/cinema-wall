from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="AI Audience Reports", page_icon="🧠", layout="wide")

LIVE = Path("data/live")
COMMENTS = LIVE / "comments.csv"
AI_REPORTS = LIVE / "ai_film_reports.json"

st.title("AI Audience Reports")
st.caption("Cached DeepSeek summaries and rule-based comment health signals from stored public YouTube comments. This is not a movie rating.")

@st.cache_data(ttl=300)
def load_comments() -> pd.DataFrame:
    try:
        frame = pd.read_csv(COMMENTS)
    except Exception:
        return pd.DataFrame()
    if frame.empty:
        return frame
    frame["created_at"] = pd.to_datetime(frame.get("created_at"), errors="coerce", utc=True)
    frame["likes"] = pd.to_numeric(frame.get("likes", 0), errors="coerce").fillna(0)
    for column, default in {
        "film": "Unknown",
        "channel": "Unknown",
        "language": "Unknown",
        "topic": "General reaction",
        "reaction_signal": "Mixed / unclear",
        "audience_value": "General opinion",
        "scam_risk": "Low",
        "promotional_flag": False,
        "possible_sarcasm": False,
        "text": "",
        "url": "",
    }.items():
        if column not in frame:
            frame[column] = default
    frame["promotional_flag"] = frame["promotional_flag"].fillna(False).astype(bool)
    frame["possible_sarcasm"] = frame["possible_sarcasm"].fillna(False).astype(bool)
    return frame

@st.cache_data(ttl=300)
def load_ai() -> dict:
    try:
        return json.loads(AI_REPORTS.read_text(encoding="utf-8"))
    except Exception:
        return {}

comments = load_comments()
ai = load_ai()

if comments.empty:
    st.warning("No stored comments are available yet.")
    st.stop()

films = sorted(comments["film"].dropna().astype(str).unique())
film = st.selectbox("Film", films)
film_comments = comments[comments["film"].astype(str).eq(film)].copy()

report = ai.get("films", {}).get(film, {}) if isinstance(ai, dict) else {}
if report:
    st.subheader("DeepSeek audience reading")
    st.write(report.get("audience_summary", "No summary text returned."))
    cols = st.columns(3)
    for col, title, key in [
        (cols[0], "Praise", "main_praise"),
        (cols[1], "Criticism", "main_criticism"),
        (cols[2], "Promotion / scam patterns", "promotion_or_scam_patterns"),
    ]:
        with col:
            st.markdown(f"#### {title}")
            values = report.get(key, [])
            if values:
                for value in values[:6]:
                    st.write(f"- {value}")
            else:
                st.caption("No strong pattern reported.")
    with st.expander("Questions, sarcasm cues and reviewer differences", expanded=True):
        for title, key in [
            ("Useful questions", "useful_questions"),
            ("Sarcasm or comedy cues", "sarcasm_or_comedy_cues"),
            ("Reviewer audience differences", "reviewer_audience_differences"),
        ]:
            st.markdown(f"**{title}**")
            values = report.get(key, [])
            if values:
                for value in values[:8]:
                    st.write(f"- {value}")
            else:
                st.caption("No strong pattern reported.")
        if report.get("sample_size_warning"):
            st.warning(report["sample_size_warning"])
else:
    st.info("No cached DeepSeek report exists yet for this film. Add DEEPSEEK_API_KEY in GitHub Secrets and run the monitor once.")

st.subheader("Rule-based comment health")
value_counts = film_comments["audience_value"].value_counts().rename_axis("Category").reset_index(name="Comments")
value_counts["Share"] = value_counts["Comments"] / len(film_comments) * 100
health_cols = st.columns(6)
health_cols[0].metric("Comments", f"{len(film_comments):,}")
health_cols[1].metric("Promotional", f"{film_comments['promotional_flag'].mean():.1%}")
health_cols[2].metric("Scam risk", f"{film_comments['scam_risk'].isin(['Medium', 'High']).mean():.1%}")
health_cols[3].metric("Sarcasm cues", f"{film_comments['possible_sarcasm'].mean():.1%}")
health_cols[4].metric("Questions", f"{film_comments.get('is_question', pd.Series(False, index=film_comments.index)).fillna(False).astype(bool).mean():.1%}")
health_cols[5].metric("Critical wording", f"{film_comments['reaction_signal'].eq('Critical').mean():.1%}")

left, right = st.columns(2, gap="large")
with left:
    fig = px.bar(value_counts.sort_values("Share"), x="Share", y="Category", orientation="h", text="Comments", color="Category")
    fig.update_traces(texttemplate="%{x:.1f}% · %{text:,}", textposition="outside")
    fig.update_layout(height=430, showlegend=False, xaxis_title="Share of collected comments (%)", yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
with right:
    lang = film_comments.groupby(["language", "audience_value"], as_index=False).size().rename(columns={"size": "Comments"})
    lang["Share"] = lang["Comments"] / lang.groupby("language")["Comments"].transform("sum") * 100
    fig = px.bar(lang, x="language", y="Share", color="audience_value", barmode="stack")
    fig.update_layout(height=430, legend_title=None, xaxis_title=None, yaxis_title="Within-language share (%)")
    st.plotly_chart(fig, width="stretch")

st.subheader("Evidence comments")
show = film_comments.sort_values(["likes", "created_at"], ascending=[False, False]).copy()
show["Comment"] = show["text"].astype(str).str.slice(0, 320)
st.dataframe(
    show[["channel", "audience_value", "reaction_signal", "topic", "language", "likes", "Comment", "url"]].head(300),
    hide_index=True,
    width="stretch",
    column_config={"url": st.column_config.LinkColumn("Open")},
)

with st.expander("Method notes"):
    st.write("Rule-based columns are generated during collection and stored in comments.csv. DeepSeek summaries are cached in ai_film_reports.json only when DEEPSEEK_API_KEY is configured. Page loading never calls DeepSeek directly.")
    if ai:
        st.json({k: ai.get(k) for k in ["generated_at", "model", "method", "errors"]})
