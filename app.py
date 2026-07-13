from __future__ import annotations

from collections import Counter
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import aggregate, load_live, load_metadata, load_video_snapshots
from sentiment import NEGATIVE, POSITIVE, add_sentiment

st.set_page_config(page_title="Tamil Film Pulse · Daily Scanner", page_icon="📡", layout="wide")
st.markdown("""<style>
.stApp{background:#f3f0e7}.block-container{max-width:1450px;padding-top:1.4rem}
[data-testid="stMetric"]{background:#faf8f2;border:1px solid #d8d3c7;padding:16px;border-radius:12px}
.hero{border-top:1px solid #d8d3c7;border-bottom:1px solid #d8d3c7;padding:35px 0 28px;margin:4px 0 22px}
.kicker{font-size:11px;font-weight:800;letter-spacing:.17em;color:#ed5b2f}.hero h1{font-size:58px;line-height:.98;letter-spacing:-.055em;margin:8px 0 15px}.hero p{font-size:17px;color:#686359;max-width:760px}
.status{display:inline-flex;align-items:center;gap:7px;border:1px solid #d8d3c7;background:#faf8f2;padding:7px 11px;border-radius:20px;font-size:10px;font-weight:800;letter-spacing:.1em}.dot{width:8px;height:8px;border-radius:50%;background:#3b8b72}.waiting{background:#d2aa52}.film-title{font-size:30px;font-weight:800;letter-spacing:-.04em}.subtle{color:#777267;font-size:12px}
</style>""", unsafe_allow_html=True)


ANALYSIS_SCHEMA_VERSION = "tamil-tanglish-v2"

@st.cache_data(ttl=900)
def get_data(schema_version: str):
    frame = load_live()
    # Rebuild derived analysis columns even when the stored CSV predates this schema.
    if not frame.empty:
        frame = add_sentiment(frame)
    return frame, load_video_snapshots(), load_metadata()


def top_terms(texts, limit=12):
    joined = " ".join(texts.fillna("").str.lower())
    lexicon = list(POSITIVE) + list(NEGATIVE)
    return Counter({term: len(re.findall(re.escape(term), joined)) for term in lexicon if term in joined}).most_common(limit)


frame, videos, meta = get_data(ANALYSIS_SCHEMA_VERSION)
with st.sidebar:
    st.title("📡 Tamil Cinema Scanner")
    st.caption("Automatically refreshed from the latest GitHub scan")
    if not frame.empty:
        selected_films = st.multiselect("Films on the wall", sorted(frame.film.unique()), default=sorted(frame.film.unique()))
        platforms = st.multiselect("Sources", sorted(frame.platform.unique()), default=sorted(frame.platform.unique()))
        minimum_likes = st.number_input("Minimum likes", 0, value=0)
        window = st.select_slider("Conversation window", [7, 14, 30, 90, 365], value=90, format_func=lambda x: f"Last {x} days")
    st.divider()
    st.markdown("**Scan rhythm**")
    st.caption("Every day at 11:30 UTC. Recent Tamil releases are discovered automatically, then selected review channels and public Reddit JSON discussions are scanned.")
    if st.button("Refresh dashboard cache"):
        st.cache_data.clear(); st.rerun()

status = meta.get("status", "waiting")
last_scan = pd.to_datetime(meta.get("last_scan"), errors="coerce", utc=True)
status_text = "SCANNER HEALTHY" if status == "healthy" else "PARTIAL SCAN" if status == "partial" else "WAITING FOR FIRST SCAN"
st.markdown(f"""<div class="hero"><span class="kicker">THE DAILY TAMIL CINEMA RADAR</span><h1>Reviews in.<br>Noise filtered out.</h1><p>The wall discovers recent releases, follows established Tamil review channels and reads public Reddit JSON discussions without Reddit OAuth.</p><span class="status"><i class="dot {'waiting' if status != 'healthy' else ''}"></i>{status_text}</span></div>""", unsafe_allow_html=True)

if frame.empty:
    st.warning("The scanner is ready but has not produced its first dataset yet. Add the two repository secrets, then run **Daily Tamil film scanner** once from GitHub Actions.")
    st.code("TMDB_API_KEY\nYOUTUBE_API_KEY", language=None)
    st.stop()

cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(window))
filtered = frame[(frame.film.isin(selected_films)) & (frame.platform.isin(platforms)) & (frame.likes >= minimum_likes) & (frame.created_at >= cutoff)].copy()
# Keep filtered views schema-safe after old Streamlit cache entries or legacy CSVs.
filtered = add_sentiment(filtered)
if filtered.empty:
    st.info("No scanned comments match these filters."); st.stop()

summary = aggregate(filtered)
cols = st.columns(5)
cols[0].metric("Films on wall", len(summary))
cols[1].metric("Comments stored", f"{len(frame):,}")
cols[2].metric("Current view", f"{len(filtered):,}")
cols[3].metric("Average pulse", f"{filtered.sentiment_score.mean():.0f}/100")
cols[4].metric("Last scan", last_scan.strftime("%d %b, %H:%M UTC") if pd.notna(last_scan) else "Pending")

st.subheader("This week’s wall")
left, right = st.columns([1.55, 1], gap="large")
with left:
    chart = summary.copy(); chart["change_label"] = chart.weekly_change.map(lambda x: f"{x:+.1f}")
    fig = px.bar(chart.sort_values("score"), x="score", y="film", orientation="h", color="score", text="score",
                 color_continuous_scale=[(0,"#c64f44"),(.5,"#d2aa52"),(1,"#3b8b72")], range_x=[0,100], hover_data={"weekly_change":":+.1f","mentions":True})
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig.update_layout(height=max(360,len(chart)*62), coloraxis_showscale=False, xaxis_title="Pulse score", yaxis_title=None, margin=dict(l=5,r=25,t=10,b=5), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")
with right:
    film = st.selectbox("Inspect a film", summary.film.tolist())
    movie = filtered[filtered.film == film]; row = summary[summary.film == film].iloc[0]
    catalog={item["title"]:item for item in meta.get("movie_catalog",[]) if isinstance(item,dict)}
    poster=catalog.get(film,{}).get("poster_url")
    head_left,head_right=st.columns([1,2])
    with head_left:
        if poster: st.image(poster,width="stretch")
    with head_right:
        st.markdown(f'<div class="film-title">{film}</div><div class="subtle">{len(movie):,} useful comments · last seen {row.last_seen:%d %b}</div>', unsafe_allow_html=True)
    st.metric("Pulse", f"{row.score:.0f}/100", f"{row.weekly_change:+.1f} vs previous week")
    counts = movie.sentiment.value_counts(normalize=True).reindex(["Positive","Neutral","Negative"],fill_value=0)*100
    pie=go.Figure(go.Pie(labels=counts.index,values=counts.values,hole=.64,marker_colors=["#3b8b72","#d2aa52","#c64f44"],textinfo="label+percent"))
    pie.update_layout(height=260,margin=dict(l=0,r=0,t=5,b=0),showlegend=False,paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(pie,width="stretch")

st.subheader("YouTube versus Reddit")
platform_scores=filtered.groupby(["film","platform"],as_index=False).agg(score=("sentiment_score","mean"),mentions=("text","size"))
compare=px.bar(platform_scores,x="film",y="score",color="platform",barmode="group",range_y=[0,100],color_discrete_map={"YouTube":"#e8563f","Reddit":"#6e77b7"},hover_data="mentions")
compare.update_layout(height=400,yaxis_title="Pulse score",xaxis_title=None,legend_title=None,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(compare,width="stretch")

st.subheader("Language and aspect intelligence")
language_col,aspect_col=st.columns([1,1.4],gap="large")
with language_col:
    language_counts=filtered["language"].value_counts().reset_index(); language_counts.columns=["Language","Comments"]
    language_fig=px.pie(language_counts,names="Language",values="Comments",hole=.55,color_discrete_sequence=["#ed5b2f","#3b8b72","#6e77b7","#d2aa52"])
    language_fig.update_layout(height=340,margin=dict(l=0,r=0,t=10,b=0),legend_title=None,paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(language_fig,width="stretch")
with aspect_col:
    aspect_rows=[]
    for _, comment in filtered[~filtered["low_information"]].iterrows():
        scores = comment["aspect_scores"] if isinstance(comment["aspect_scores"], dict) else {}
        for aspect, score in scores.items():
            aspect_rows.append({"Aspect": aspect, "Score": score, "Weight": comment["analysis_weight"]})
    if aspect_rows:
        aspects=pd.DataFrame(aspect_rows)
        aspects["Weighted"]=aspects.Score*aspects.Weight
        aspect_summary=aspects.groupby("Aspect",as_index=False).agg(total=("Weighted","sum"),weight=("Weight","sum"),mentions=("Score","size"))
        aspect_summary["Pulse"]=aspect_summary.total/aspect_summary.weight
        aspect_fig=px.bar(aspect_summary.sort_values("Pulse"),x="Pulse",y="Aspect",orientation="h",color="Pulse",
            range_x=[0,100],hover_data="mentions",color_continuous_scale=[(0,"#c64f44"),(.5,"#d2aa52"),(1,"#3b8b72")])
        aspect_fig.update_layout(height=340,coloraxis_showscale=False,xaxis_title="Aspect sentiment",yaxis_title=None,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(aspect_fig,width="stretch")
    else: st.info("Aspect scores will appear when story, acting, music, pacing and other film elements are mentioned.")

if not videos.empty:
    st.subheader("Review video signal — views accumulated between scans")
    period_label = st.segmented_control("Growth interval", ["Day", "Week", "Month", "Year"], default="Week")
    days = {"Day": 1, "Week": 7, "Month": 30, "Year": 365}[period_label]
    latest = videos.sort_values("scanned_at").groupby("video_id").tail(1)
    prior_cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(days))
    prior = videos[videos.scanned_at <= prior_cutoff].sort_values("scanned_at").groupby("video_id").tail(1)[["video_id","views"]].rename(columns={"views":"prior_views"})
    growth = latest.merge(prior,on="video_id",how="left")
    growth["view_growth"] = (growth.views-growth.prior_views).where(growth.prior_views.notna())
    growth["engagement"] = (growth.likes+growth.comments)/growth.views.clip(lower=1)*1000
    view_chart = px.scatter(growth, x="view_growth", y="engagement", size="views", color="film", hover_name="title",
        hover_data=["channel","trusted_channel","signal_score"], labels={"view_growth":f"Views gained / {period_label.lower()}","engagement":"Likes + comments per 1,000 views"})
    view_chart.update_layout(height=430,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    if growth.view_growth.notna().any(): st.plotly_chart(view_chart,width="stretch")
    else: st.info(f"The {period_label.lower()} view-growth signal will appear after enough daily snapshots accumulate. Current public totals are already stored.")
    st.dataframe(growth[["film","channel","title","views","view_growth","likes","comments","signal_score"]].sort_values("views",ascending=False),
        width="stretch",hide_index=True,column_config={"view_growth":st.column_config.NumberColumn(f"{period_label} views",format="%.0f")})

trend_col,term_col=st.columns([1.5,1],gap="large")
with trend_col:
    st.subheader("Pulse history")
    trend=filtered.assign(date=filtered.created_at.dt.date).groupby(["date","film"],as_index=False).sentiment_score.mean()
    line=px.line(trend,x="date",y="sentiment_score",color="film",markers=True)
    line.update_layout(height=370,yaxis_range=[0,100],yaxis_title="Pulse",xaxis_title=None,legend_title=None,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(line,width="stretch")
with term_col:
    st.subheader("Cinema-language signals")
    terms=pd.DataFrame(top_terms(filtered.text),columns=["term","mentions"])
    if not terms.empty:
        bars=px.bar(terms.sort_values("mentions"),x="mentions",y="term",orientation="h",color_discrete_sequence=["#ed5b2f"])
        bars.update_layout(height=370,xaxis_title="Occurrences",yaxis_title=None,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(bars,width="stretch")

with st.expander("Open the scanner log and comments"):
    st.caption(f"Scanner status: {status}. Source errors: {len(meta.get('errors', []))}.")
    if meta.get("errors"): st.warning("\n".join(meta["errors"]))
    st.markdown("**Monitored Reddit forums:** "+", ".join(meta.get("reddit_forums", [])))
    st.markdown("**Preferred YouTube channels:** "+", ".join(meta.get("youtube_channels", [])))
    shown=filtered[["film","platform","source","content_type","language","text","sentiment","sentiment_score","confidence","likes","created_at","url"]].sort_values("created_at",ascending=False)
    st.dataframe(shown,width="stretch",hide_index=True,column_config={"url":st.column_config.LinkColumn("Source")})
    st.download_button("Download current view",shown.to_csv(index=False),"tamil-film-weekly-scan.csv","text/csv")

st.caption("Tamil Film Pulse · Daily snapshots · Reddit public JSON + YouTube Data API · Conversation signal, not a quality or box-office rating")
