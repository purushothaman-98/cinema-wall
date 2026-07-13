from __future__ import annotations

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from data import load_live, load_metadata, load_video_snapshots

st.set_page_config(page_title="Tamil Cinema Discussion Wall", page_icon="🎬", layout="wide")
st.markdown("""<style>
.stApp{background:#f4f1e8}.block-container{max-width:1450px;padding-top:1.5rem}
.hero{border-bottom:1px solid #d7d1c3;padding:22px 0 28px;margin-bottom:24px}
.kicker{font-size:11px;font-weight:800;letter-spacing:.16em;color:#ee5832}
.hero h1{font-size:52px;line-height:1;letter-spacing:-.05em;margin:8px 0 12px}
.hero p{font-size:17px;color:#686258;max-width:820px}
[data-testid="stMetric"]{background:#fbf9f3;border:1px solid #d7d1c3;padding:15px;border-radius:12px}
.poster-title{font-size:18px;font-weight:800;line-height:1.05;margin-top:8px}
.poster-meta{font-size:12px;color:#777064;margin-bottom:14px}
</style>""", unsafe_allow_html=True)

DATA_SCHEMA = "discussion-wall-v1"

@st.cache_data(ttl=900)
def get_data(schema: str):
    return load_live(), load_video_snapshots(), load_metadata()

frame, videos, meta = get_data(DATA_SCHEMA)

with st.sidebar:
    st.title("🎬 Tamil Cinema Wall")
    st.caption("Daily public discussion scanner")
    if not frame.empty:
        films = sorted(frame["film"].dropna().unique())
        sources = sorted(frame["platform"].dropna().unique())
        selected_films = st.multiselect("Films", films, default=films)
        selected_sources = st.multiselect("Sources", sources, default=sources)
        window = st.select_slider("Conversation window", [7, 14, 30, 90, 365, 730], value=90,
                                  format_func=lambda x: f"Last {x} days")
        minimum_likes = st.number_input("Minimum likes", min_value=0, value=0)
    st.divider()
    st.markdown("**Scan rhythm**")
    st.caption("Full YouTube and archive-based Reddit scan every day at 11:30 UTC.")
    if st.button("Scan Reddit now", type="primary", width="stretch"):
        token = st.secrets.get("GITHUB_ACTION_TOKEN", "")
        if not token:
            st.error("Add a valid GITHUB_ACTION_TOKEN in Streamlit secrets.")
        else:
            response = requests.post(
                "https://api.github.com/repos/purushothaman-98/cinema-wall/actions/workflows/reddit-scan.yml/dispatches",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"},
                json={"ref": "main"}, timeout=20,
            )
            if response.status_code == 204:
                st.success("Reddit archive scan started.")
            else:
                st.error(f"GitHub returned {response.status_code}. Check the token's Actions permission.")
    if st.button("Refresh dashboard data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown("""<div class="hero"><span class="kicker">TAMIL FILM CONVERSATION TRACKER</span>
<h1>What people are discussing.<br>How attention changes.</h1>
<p>Public YouTube comments and archived Reddit discussions are collected, separated by film and source,
and shown as activity—not as a review score or quality rating.</p></div>""", unsafe_allow_html=True)

if frame.empty:
    st.warning("No discussion dataset is available yet. Run the daily scanner from GitHub Actions.")
    st.stop()

frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce", utc=True)
cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(window))
filtered = frame[
    frame["film"].isin(selected_films)
    & frame["platform"].isin(selected_sources)
    & (pd.to_numeric(frame["likes"], errors="coerce").fillna(0) >= minimum_likes)
    & (frame["created_at"] >= cutoff)
].copy()
if filtered.empty:
    st.info("No collected discussions match these filters.")
    st.stop()

last_scan = pd.to_datetime(meta.get("last_scan"), errors="coerce", utc=True)
reddit_count = int((filtered["platform"] == "Reddit").sum())
youtube_count = int((filtered["platform"] == "YouTube").sum())
metrics = st.columns(5)
metrics[0].metric("Films tracked", filtered["film"].nunique())
metrics[1].metric("Comments analyzed", f"{len(filtered):,}")
metrics[2].metric("YouTube comments", f"{youtube_count:,}")
metrics[3].metric("Reddit discussions", f"{reddit_count:,}")
metrics[4].metric("Last scan", last_scan.strftime("%d %b · %H:%M UTC") if pd.notna(last_scan) else "Pending")

st.subheader("Films currently on the wall")
catalog = {item.get("title"): item for item in meta.get("movie_catalog", []) if isinstance(item, dict)}
film_totals = filtered.groupby("film").size().to_dict()
wall_films = [name for name in selected_films if name in catalog][:10]
if not wall_films:
    wall_films = selected_films[:10]
for start in range(0, len(wall_films), 5):
    cols = st.columns(5)
    for col, title in zip(cols, wall_films[start:start + 5]):
        item = catalog.get(title, {})
        with col:
            if item.get("poster_url"):
                st.image(item["poster_url"], width="stretch")
            st.markdown(f'<div class="poster-title">{title}</div>', unsafe_allow_html=True)
            release = item.get("release_date") or "Release date unavailable"
            st.markdown(f'<div class="poster-meta">{release} · {film_totals.get(title, 0):,} discussions</div>',
                        unsafe_allow_html=True)

st.subheader("Discussion activity over time")
daily = (
    filtered.dropna(subset=["created_at"])
    .assign(date=lambda x: x["created_at"].dt.floor("D"))
    .groupby(["date", "platform"], as_index=False)
    .size()
    .rename(columns={"size": "discussions"})
)
daily["7-day average"] = daily.groupby("platform")["discussions"].transform(
    lambda values: values.rolling(7, min_periods=1).mean()
)
activity = px.line(daily, x="date", y="7-day average", color="platform", markers=True,
                   color_discrete_map={"YouTube": "#ed5837", "Reddit": "#6874b7"},
                   labels={"date": None, "7-day average": "Daily discussions · 7-day average"})
activity.update_layout(height=420, legend_title=None, paper_bgcolor="rgba(0,0,0,0)",
                       plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
st.plotly_chart(activity, width="stretch")

left, right = st.columns([1.35, 1], gap="large")
with left:
    st.subheader("Discussion volume by film and source")
    volume = filtered.groupby(["film", "platform"], as_index=False).size().rename(columns={"size": "discussions"})
    bars = px.bar(volume, x="film", y="discussions", color="platform", barmode="group",
                  color_discrete_map={"YouTube": "#ed5837", "Reddit": "#6874b7"})
    bars.update_layout(height=420, xaxis_title=None, yaxis_title="Collected discussions",
                       legend_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(bars, width="stretch")
with right:
    st.subheader("What was analyzed")
    breakdown = filtered.groupby(["platform", "content_type"], as_index=False).size().rename(columns={"size": "items"})
    fig = px.sunburst(breakdown, path=["platform", "content_type"], values="items",
                      color="platform", color_discrete_map={"YouTube": "#ed5837", "Reddit": "#6874b7"})
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

st.subheader("Collected comments and discussions")
table_columns = ["film", "platform", "source", "content_type", "text", "likes", "created_at", "url"]
shown = filtered[table_columns].sort_values("created_at", ascending=False)
st.dataframe(shown, width="stretch", hide_index=True,
             column_config={"url": st.column_config.LinkColumn("Open source"),
                            "created_at": st.column_config.DatetimeColumn("Published", format="DD MMM YYYY, HH:mm")})
st.download_button("Download filtered discussions", shown.to_csv(index=False),
                   "tamil-cinema-discussions.csv", "text/csv")

with st.expander("Scanner status and sources"):
    st.write(f"Status: **{meta.get('status', 'unknown')}**")
    st.write("Reddit forums: " + ", ".join(meta.get("reddit_forums", [])))
    st.write("YouTube channels: " + ", ".join(meta.get("youtube_channels", [])))
    for note in meta.get("notes", []):
        st.info(note)
    errors = meta.get("errors", [])
    if errors:
        st.caption(f"{len(errors)} source warnings from the latest run")
        st.code("\n".join(errors), language=None)

st.caption("Tamil Cinema Wall · Counts represent collected public discussions, not audience size, film quality or box office.")
