from __future__ import annotations

from collections import Counter
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from collectors import collect_reddit, collect_youtube
from data import aggregate, load_demo, load_upload
from sentiment import NEGATIVE, POSITIVE, add_sentiment

st.set_page_config(page_title="Tamil Film Pulse", page_icon="🎬", layout="wide")

st.markdown("""
<style>
.stApp{background:#f3f0e7}.block-container{max-width:1450px;padding-top:1.7rem}
[data-testid="stMetric"]{background:#faf8f2;border:1px solid #d8d3c7;padding:16px;border-radius:12px}
.hero{border-top:1px solid #d8d3c7;border-bottom:1px solid #d8d3c7;padding:38px 0 32px;margin:4px 0 25px}
.kicker{font-size:11px;font-weight:800;letter-spacing:.17em;color:#ed5b2f}.hero h1{font-size:58px;line-height:.98;letter-spacing:-.055em;margin:8px 0 16px}.hero p{font-size:17px;color:#686359;max-width:720px}
.demo{display:inline-block;background:#171713;color:white;padding:7px 11px;border-radius:20px;font-size:10px;font-weight:800;letter-spacing:.12em}
.film-title{font-size:30px;font-weight:800;letter-spacing:-.04em}.subtle{color:#777267;font-size:12px}
.quote{font-family:Georgia,serif;font-size:21px;font-style:italic;border-left:3px solid #ed5b2f;padding-left:16px;margin:16px 0}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def demo_data():
    return add_sentiment(load_demo())


def top_terms(texts: pd.Series, limit: int = 12):
    lexicon = list(POSITIVE) + list(NEGATIVE)
    joined = " ".join(texts.fillna("").str.lower())
    return Counter({term: len(re.findall(re.escape(term), joined)) for term in lexicon if term in joined}).most_common(limit)


with st.sidebar:
    st.title("🎬 Tamil Film Pulse")
    st.caption("Public conversation dashboard")
    source_mode = st.radio("Data source", ["Demonstration data", "Upload CSV", "Collect from APIs"])
    frame = None
    if source_mode == "Upload CSV":
        upload = st.file_uploader("Comment dataset", type="csv")
        if upload:
            try:
                frame = add_sentiment(load_upload(upload))
            except ValueError as exc:
                st.error(str(exc))
    elif source_mode == "Collect from APIs":
        film_input = st.text_input("Film title")
        platform_input = st.selectbox("Platform", ["YouTube", "Reddit"])
        query_input = st.text_input("YouTube video IDs (comma-separated)" if platform_input == "YouTube" else "Reddit search query")
        max_comments = st.slider("Maximum comments", 50, 500, 200, 50)
        if st.button("Collect public comments", type="primary"):
            try:
                if platform_input == "YouTube":
                    frame = collect_youtube([x.strip() for x in query_input.split(",") if x.strip()], st.secrets["YOUTUBE_API_KEY"], film_input, max_comments)
                else:
                    frame = collect_reddit(query_input, film_input, st.secrets["REDDIT_CLIENT_ID"], st.secrets["REDDIT_CLIENT_SECRET"], st.secrets["REDDIT_USER_AGENT"], max_comments)
                frame = add_sentiment(frame)
                st.session_state["collected"] = frame
            except Exception as exc:
                st.error(f"Collection failed: {exc}")
        frame = st.session_state.get("collected")
    if frame is None:
        frame = demo_data()
    st.divider()
    platforms = st.multiselect("Platforms", sorted(frame.platform.unique()), default=sorted(frame.platform.unique()))
    min_likes = st.number_input("Minimum likes", min_value=0, value=0)
    st.caption("Scores describe the collected conversation, not film quality or box-office success.")

filtered = frame[frame.platform.isin(platforms) & (frame.likes.fillna(0) >= min_likes)].copy()
if filtered.empty:
    st.warning("No comments match the current filters.")
    st.stop()

st.markdown(f"""<div class="hero"><span class="kicker">THE AUDIENCE, MEASURED</span><h1>What is Tamil cinema<br>really feeling?</h1><p>Compare Tamil, Tanglish and English reactions across YouTube and Reddit.</p>{'<span class="demo">DEMO DATA</span>' if source_mode == 'Demonstration data' else ''}</div>""", unsafe_allow_html=True)

summary = aggregate(filtered)
metric_cols = st.columns(4)
metric_cols[0].metric("Films tracked", len(summary))
metric_cols[1].metric("Comments analysed", f"{len(filtered):,}")
metric_cols[2].metric("Average pulse", f"{filtered.sentiment_score.mean():.0f}/100")
metric_cols[3].metric("Positive conversation", f"{(filtered.sentiment == 'Positive').mean()*100:.0f}%")

st.subheader("Film sentiment ranking")
left, right = st.columns([1.55, 1], gap="large")
with left:
    fig = px.bar(summary.sort_values("score"), x="score", y="film", orientation="h", text="score",
                 color="score", color_continuous_scale=[(0,"#c64f44"),(.5,"#d2aa52"),(1,"#3b8b72")], range_x=[0,100])
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", hovertemplate="%{y}<br>Pulse %{x:.1f}<extra></extra>")
    fig.update_layout(height=390, coloraxis_showscale=False, xaxis_title="Pulse score", yaxis_title=None, margin=dict(l=5,r=25,t=10,b=5), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

with right:
    film = st.selectbox("Inspect a film", summary.film.tolist())
    movie = filtered[filtered.film == film]
    row = summary[summary.film == film].iloc[0]
    st.markdown(f'<div class="film-title">{film}</div><div class="subtle">{len(movie):,} public comments in this view</div>', unsafe_allow_html=True)
    st.progress(float(row.score / 100), text=f"Pulse score · {row.score:.0f}/100")
    sentiment_counts = movie.sentiment.value_counts(normalize=True).reindex(["Positive","Neutral","Negative"], fill_value=0) * 100
    pie = go.Figure(go.Pie(labels=sentiment_counts.index, values=sentiment_counts.values, hole=.65, marker_colors=["#3b8b72","#d2aa52","#c64f44"], textinfo="label+percent"))
    pie.update_layout(height=245, margin=dict(l=0,r=0,t=5,b=0), showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(pie, width="stretch")

st.subheader("Platform comparison")
platform_scores = filtered.groupby(["film","platform"], as_index=False).agg(score=("sentiment_score","mean"), mentions=("text","size"))
compare = px.bar(platform_scores, x="film", y="score", color="platform", barmode="group", range_y=[0,100], color_discrete_map={"YouTube":"#e8563f","Reddit":"#6e77b7"}, hover_data="mentions")
compare.update_layout(height=400, yaxis_title="Pulse score", xaxis_title=None, legend_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(compare, width="stretch")

trend_col, topic_col = st.columns([1.45, 1], gap="large")
with trend_col:
    st.subheader("Conversation over time")
    dated = filtered.dropna(subset=["created_at"]).copy()
    dated["date"] = pd.to_datetime(dated.created_at, utc=True).dt.date
    trend = dated.groupby(["date","film"], as_index=False).sentiment_score.mean()
    trend_fig = px.line(trend, x="date", y="sentiment_score", color="film", markers=True)
    trend_fig.update_layout(height=365, yaxis_range=[0,100], yaxis_title="Pulse score", xaxis_title=None, legend_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(trend_fig, width="stretch")
with topic_col:
    st.subheader("Tamil-cinema signals")
    terms = pd.DataFrame(top_terms(filtered.text), columns=["term","mentions"])
    if not terms.empty:
        term_fig = px.bar(terms.sort_values("mentions"), x="mentions", y="term", orientation="h", color_discrete_sequence=["#ed5b2f"])
        term_fig.update_layout(height=365, xaxis_title="Occurrences", yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(term_fig, width="stretch")
    else:
        st.info("No known Tamil-cinema sentiment terms were detected.")

with st.expander("Explore analysed comments"):
    labels = st.multiselect("Sentiment", ["Positive","Neutral","Negative"], default=["Positive","Neutral","Negative"])
    shown = filtered[filtered.sentiment.isin(labels)][["film","platform","text","sentiment","sentiment_score","likes","created_at","url"]]
    st.dataframe(shown.sort_values("likes", ascending=False), width="stretch", hide_index=True, column_config={"url": st.column_config.LinkColumn("Source")})
    st.download_button("Download analysed CSV", shown.to_csv(index=False), "tamil_film_sentiment.csv", "text/csv")

st.caption("Tamil Film Pulse · Public conversation analysis · Transparent baseline model · API terms and quotas apply")
