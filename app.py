from __future__ import annotations

import html
import json
import math
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_live, load_metadata, load_video_snapshots
from youtube_analysis import top_terms

st.set_page_config(page_title="Tamil Cinema YouTube Radar", page_icon="▶️", layout="wide")

PALETTE = ["#ff4b2b", "#ff9f1c", "#2ec4b6", "#3a86ff", "#8338ec", "#ff006e", "#8ac926", "#6c757d", "#e76f51", "#00b4d8"]
st.markdown("""<style>
.stApp{background:#f7f3ea}.block-container{max-width:1480px;padding-top:1.3rem}
.hero{background:linear-gradient(115deg,#141414 0%,#3a1710 54%,#ff4b2b 140%);color:white;padding:42px 46px;border-radius:22px;margin:2px 0 24px;box-shadow:0 18px 45px rgba(55,27,18,.16)}
.kicker{font-size:11px;font-weight:900;letter-spacing:.19em;color:#ffb39f}.hero h1{font-size:58px;line-height:.96;letter-spacing:-.055em;margin:10px 0 15px}.hero p{font-size:17px;color:#eaded8;max-width:820px;margin:0}
[data-testid="stMetric"]{background:#fffdf8;border:1px solid #ddd3c3;padding:16px;border-radius:14px;box-shadow:0 5px 16px rgba(46,36,24,.04)}
.poster-card{background:#fffdf8;border:1px solid #ddd3c3;border-radius:14px;overflow:hidden;margin-bottom:12px}
.poster-card img{width:100%;aspect-ratio:2/3;object-fit:cover;display:block}.poster-copy{padding:10px 11px 12px}.poster-title{font-size:17px;font-weight:850;line-height:1.05}.poster-meta{font-size:11px;color:#766d61;margin-top:5px;line-height:1.45}
.section-note{color:#756d62;font-size:13px;margin-top:-8px;margin-bottom:12px}
.badge{display:inline-block;background:#ffe6df;color:#a22d16;border-radius:20px;padding:5px 9px;font-size:10px;font-weight:800;letter-spacing:.05em}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_data(schema: str):
    return load_live(), load_video_snapshots(), load_metadata()

comments, videos, meta = get_data("youtube-radar-v3")
if not comments.empty:
    if "channel" not in comments:
        comments["channel"] = comments.get("source", "Unknown")
    if "video_id" not in comments:
        comments["video_id"] = comments.get("parent_id", "")
    if "video_title" not in comments:
        comments["video_title"] = ""
    comments["channel"] = comments["channel"].fillna(comments.get("source", "Unknown"))
    comments["likes"] = pd.to_numeric(comments.get("likes", 0), errors="coerce").fillna(0)
    if "content_format" not in comments:
        comments["content_format"] = "Unknown"
    if not videos.empty and "content_format" in videos:
        format_map = (
            videos.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
            .set_index("video_id")["content_format"]
        )
        inferred = comments["video_id"].astype(str).map(format_map)
        comments["content_format"] = comments["content_format"].where(
            comments["content_format"].isin(["Video", "Short"]), inferred
        ).fillna("Video")
    else:
        comments["content_format"] = comments["content_format"].replace("Unknown", "Video").fillna("Video")

catalog_items = meta.get("movie_catalog_history") or meta.get("movie_catalog", [])
catalog = {item.get("title"): item for item in catalog_items if isinstance(item, dict)}

def audience_summary(frame: pd.DataFrame) -> str:
    useful = frame[~frame["low_information"]].copy() if not frame.empty else frame
    if useful.empty:
        return "Not enough useful audience comments yet."
    signalled = useful[useful["reaction_signal"].ne("Mixed / unclear")]
    if len(signalled) >= 3:
        shares = signalled["reaction_signal"].value_counts(normalize=True)
        mood = shares.index[0]
        mood_text = (
            "mostly appreciative" if mood == "Appreciative"
            else "mostly critical" if mood == "Critical"
            else "mixed"
        )
    else:
        mood_text = "mixed or still developing"
    topic = useful["topic"].value_counts().index[0]
    return f"Audience response is {mood_text}; conversation is led by {topic.lower()} ({len(useful):,} analyzed comments)."

def valid_text(value: object) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip().lower() not in {"", "nan", "none", "null"}

def reviewer_context(row: pd.Series) -> str:
    raw = row.get("description", "")
    description = str(raw).replace("\n", " ").strip() if valid_text(raw) else ""
    description = " ".join(part for part in description.split() if not part.startswith("http"))
    if description:
        return description[:220] + ("…" if len(description) > 220 else "")
    return f'The public review is titled “{row.get("title", "Tamil film review")}”.'

def render_movie_page(movie: str) -> None:
    item = catalog.get(movie, {})
    film_comments = comments[comments["film"].eq(movie)].copy()
    film_videos = (
        videos[videos["film"].eq(movie)].sort_values("scanned_at").drop_duplicates("video_id", keep="last")
        if not videos.empty else pd.DataFrame()
    )
    st.markdown('<a href="./" style="text-decoration:none;font-weight:800;color:#d53c1c">← Back to all films</a>', unsafe_allow_html=True)
    backdrop = item.get("backdrop_url")
    if isinstance(backdrop, str):
        st.markdown(
            f'<div style="height:260px;border-radius:20px;background:linear-gradient(90deg,rgba(10,10,10,.82),rgba(10,10,10,.18)),url({backdrop}) center/cover;margin:16px 0"></div>',
            unsafe_allow_html=True,
        )
    poster_col, detail_col = st.columns([1, 3], gap="large")
    with poster_col:
        poster = item.get("poster_url")
        if isinstance(poster, str):
            st.markdown(f'<img src="{poster}" style="width:100%;border-radius:16px">', unsafe_allow_html=True)
    with detail_col:
        st.markdown('<span class="badge">FILM PAGE</span>', unsafe_allow_html=True)
        st.title(movie)
        original = item.get("original_title")
        if original and original != movie:
            st.caption(original)
        fact_cols = st.columns(3)
        fact_cols[0].metric("Release date", item.get("release_date") or "Unavailable")
        fact_cols[1].metric("Runtime", f'{item.get("runtime")} min' if item.get("runtime") else "Unavailable")
        video_count = int(film_videos["content_format"].eq("Video").sum()) if not film_videos.empty else 0
        short_count = int(film_videos["content_format"].eq("Short").sum()) if not film_videos.empty else 0
        fact_cols[2].metric("Coverage", f"{video_count} videos · {short_count} Shorts")
        if item.get("overview"):
            st.write(item["overview"])
        facts = []
        if item.get("director"):
            facts.append(f"**Director:** {item['director']}")
        if item.get("genres"):
            facts.append("**Genres:** " + ", ".join(item["genres"]))
        if facts:
            st.markdown("  \n".join(facts))
        if item.get("cast"):
            st.markdown("**Main cast:** " + ", ".join(item["cast"][:8]))
        verified_at = pd.to_datetime(meta.get("last_video_discovery"), errors="coerce", utc=True)
        tmdb_id = item.get("tmdb_id")
        verification = verified_at.strftime("%d %b %Y, %H:%M UTC") if pd.notna(verified_at) else "latest discovery"
        source_link = f"https://www.themoviedb.org/movie/{tmdb_id}" if tmdb_id else "https://www.themoviedb.org/"
        st.caption(f"Release, runtime, cast and crew facts cross-checked from [TMDB]({source_link}) during {verification}.")

    insight = meta.get("film_insights", {}).get(movie, {})
    st.subheader("Audience intelligence brief")
    if insight:
        st.write(insight.get("summary", ""))
        brief_metrics = st.columns(4)
        brief_metrics[0].metric("Useful comments", f"{insight.get('useful_comments', 0):,}")
        brief_metrics[1].metric("Clear reaction signals", f"{insight.get('explicit_reaction_comments', 0):,}")
        brief_metrics[2].metric("Appreciative signals", f"{insight.get('appreciative_signals', 0):,}")
        brief_metrics[3].metric("Detailed or questions", f"{insight.get('substantive_share', 0):.0%}")
        st.caption("Reaction figures count explicit wording in comments, not viewers and not a film rating. Neutral or ambiguous comments are not forced into positive/negative categories.")
        reviewer_rows = pd.DataFrame(insight.get("reviewers", []))
        if not reviewer_rows.empty:
            st.markdown("#### How each reviewer’s audience responds")
            reviewer_rows["Audience reading"] = reviewer_rows.apply(
                lambda row: (
                    f"{int(row['appreciative_signals'])} appreciative vs {int(row['critical_signals'])} critical signals; "
                    f"{int(row['questions'])} questions. Leading topic: {str(row['leading_topic']).lower()}."
                ), axis=1,
            )
            st.dataframe(
                reviewer_rows[["channel", "useful_comments", "Audience reading"]],
                width="stretch", hide_index=True,
                column_config={"channel": "Reviewer/channel", "useful_comments": "Useful comments"},
            )
    else:
        st.info("The evidence brief will appear after the next completed scanner run.")

    st.subheader("What reviewers cover—and how their audiences respond")
    st.caption("Reviewer wording comes from the public video title/description. Audience response is derived from comments attached to that exact video; no reviewer opinion is invented.")
    if film_videos.empty:
        st.info("Reviewer details will appear after the next monitor scan.")
    else:
        for _, row in film_videos.sort_values(["views", "comments"], ascending=False).iterrows():
            video_id = str(row.get("video_id", ""))
            audience = film_comments[film_comments["video_id"].astype(str).eq(video_id)]
            title = html.escape(str(row.get("title", "Review video")))
            channel = html.escape(str(row.get("channel", "Unknown channel")))
            url = f"https://youtube.com/watch?v={video_id}"
            with st.container(border=True):
                thumb_col, review_col = st.columns([1, 3], gap="large")
                with thumb_col:
                    thumb = row.get("thumbnail_url")
                    if not valid_text(thumb) or not str(thumb).startswith("http"):
                        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    st.image(str(thumb), width="stretch")
                with review_col:
                    st.markdown(f"### [{title}]({url})")
                    format_name = row.get("content_format", "Video")
                    st.caption(f"{format_name} · {channel} · {int(row.get('views', 0)):,} views · {int(row.get('comments', 0)):,} public comments")
                    st.markdown(f"**How the reviewer frames it:** {reviewer_context(row)}")
                    st.markdown(f"**How this video’s audience responds:** {audience_summary(audience)}")
                    useful_audience = audience[~audience["low_information"]].copy() if not audience.empty else audience
                    if not useful_audience.empty:
                        sample = useful_audience.sort_values(["likes", "created_at"], ascending=False).iloc[0]
                        st.caption(f'Most-liked useful comment: “{str(sample["text"])[:220]}”')

    if not film_comments.empty:
        chart_col, reaction_col = st.columns([1.4, 1], gap="large")
        with chart_col:
            st.subheader("Audience conversation over time")
            timeline = (
                film_comments.assign(day=film_comments["created_at"].dt.floor("D"))
                .groupby("day", as_index=False).size().rename(columns={"size": "Comments"})
            )
            fig = px.area(timeline, x="day", y="Comments", color_discrete_sequence=["#ff4b2b"])
            fig.update_layout(height=350, xaxis_title="Published date", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(fig, width="stretch")
        with reaction_col:
            st.subheader("Audience reaction signals")
            reactions = film_comments["reaction_signal"].value_counts().rename_axis("Reaction").reset_index(name="Comments")
            fig = px.pie(
                reactions, names="Reaction", values="Comments", hole=.58,
                color="Reaction", color_discrete_map={
                    "Appreciative": "#2ec4b6", "Critical": "#ff4b2b", "Mixed / unclear": "#ffb703"
                },
            )
            fig.update_layout(height=350, legend_title=None, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        st.subheader("Recent audience comments")
        page_columns = ["channel", "video_title", "topic", "reaction_signal", "text", "likes", "created_at", "url"]
        st.dataframe(
            film_comments[page_columns].sort_values(["likes", "created_at"], ascending=False),
            width="stretch", hide_index=True,
            column_config={"url": st.column_config.LinkColumn("Open"),
                           "created_at": st.column_config.DatetimeColumn("Published", format="DD MMM YYYY, HH:mm")},
        )

movie_param = st.query_params.get("movie")
if movie_param:
    render_movie_page(str(movie_param))
    st.stop()

with st.sidebar:
    st.title("▶ Tamil Cinema Radar")
    st.caption("Scheduled every 30 minutes · actual timing is measured")
    if not comments.empty:
        all_films = sorted(comments["film"].dropna().unique())
        selected_films = st.multiselect("Films", all_films, default=all_films)
        all_channels = sorted(comments["channel"].dropna().unique())
        selected_channels = st.multiselect("Channels", all_channels, default=all_channels)
        all_formats = [value for value in ["Video", "Short"] if value in comments["content_format"].unique()]
        selected_formats = st.multiselect("Formats", all_formats, default=all_formats)
        window = st.select_slider(
            "Analysis window",
            options=[6, 12, 24, 72, 168, 720, 2160],
            value=168,
            format_func=lambda hours: (
                f"{hours} hours" if hours < 24 else
                f"{hours // 24} days" if hours < 720 else
                f"{hours // 720} months"
            ),
        )
        minimum_likes = st.number_input("Minimum comment likes", min_value=0, value=0)
        include_noise = st.toggle("Include low-information reactions", value=False)
    st.divider()
    st.markdown("**Collection rhythm**")
    st.caption("GitHub schedules a monitor every 30 minutes, but runners can start late. The dashboard measures the actual interval. New video and Shorts selection refreshes once every 24 hours.")
    if st.button("Refresh dashboard data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown("""<div class="hero"><span class="kicker">TAMIL CINEMA · YOUTUBE INTELLIGENCE</span>
<h1>Reviews move fast.<br>The radar moves faster.</h1>
<p>A continuously archived tracker for recent Tamil films: normalized 30-minute velocity, video reach, channel contribution,
language mix, discussion topics and audience questions—without turning conversation into a quality score.</p></div>""", unsafe_allow_html=True)

if comments.empty:
    st.warning("No YouTube comments are stored yet. Run **Tamil cinema YouTube monitor** once from GitHub Actions.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
cutoff = now - pd.Timedelta(hours=int(window))
filtered = comments[
    comments["film"].isin(selected_films)
    & comments["channel"].isin(selected_channels)
    & comments["content_format"].isin(selected_formats)
    & comments["created_at"].ge(cutoff)
    & comments["likes"].ge(minimum_likes)
].copy()
if not include_noise:
    filtered = filtered[~filtered["low_information"]].copy()
if filtered.empty:
    st.info("No analyzed comments match the current filters.")
    st.stop()

monitor_videos = videos.copy() if not videos.empty else videos
video_view = videos[videos["film"].isin(selected_films)].copy() if not videos.empty else videos
latest_videos = (
    video_view.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    if not video_view.empty else video_view
)
current_scan_time = videos["scanned_at"].max() if not videos.empty else pd.NaT
current_scan_videos = (
    videos[videos["scanned_at"].eq(current_scan_time)].copy()
    if not videos.empty and pd.notna(current_scan_time) else pd.DataFrame()
)
radar_films = list(dict.fromkeys(meta.get("films", [])))
all_analyzed_films = sorted(
    set(meta.get("all_films_analyzed", []))
    | set(comments["film"].dropna().astype(str).unique())
)
last_scan = pd.to_datetime(meta.get("last_scan"), errors="coerce", utc=True)
last_24 = filtered[filtered["created_at"].ge(now - pd.Timedelta(hours=24))]

actively_fetched_films = set(current_scan_videos["film"].dropna().astype(str)) if not current_scan_videos.empty else set()
metrics = st.columns(8)
standard_count = int(current_scan_videos["content_format"].eq("Video").sum()) if not current_scan_videos.empty else 0
shorts_count = int(current_scan_videos["content_format"].eq("Short").sum()) if not current_scan_videos.empty else 0
metrics[0].metric("Films analyzed ever", len(all_analyzed_films))
metrics[1].metric("Films scheduled now", len(radar_films))
metrics[2].metric("Films fetched latest", len(actively_fetched_films))
metrics[3].metric("Current videos", standard_count)
metrics[4].metric("Current Shorts", shorts_count)
metrics[5].metric("Comments collected ever", f"{len(comments):,}", help="Unique comment records stored by the radar; this is not YouTube's public total.")
metrics[6].metric("New comments · 24 h", f"{len(last_24):,}")
metrics[7].metric("Last monitor", last_scan.strftime("%d %b · %H:%M UTC") if pd.notna(last_scan) else "Pending")

catalog = {item.get("title"): item for item in meta.get("movie_catalog", []) if isinstance(item, dict)}
st.subheader("Currently on the radar")
st.markdown('<div class="section-note">These films are scheduled for a check every 30 minutes. Actual collection timing is audited below; new-film discovery and selection refresh once per day.</div>', unsafe_allow_html=True)
wall = [film for film in radar_films if film in selected_films][:10] or radar_films[:10]
for start in range(0, len(wall), 5):
    cols = st.columns(5)
    for col, film in zip(cols, wall[start:start + 5]):
        item = catalog.get(film, {})
        poster = item.get("poster_url")
        film_comments = filtered[filtered["film"].eq(film)]
        film_videos = latest_videos[latest_videos["film"].eq(film)] if not latest_videos.empty else pd.DataFrame()
        recent = film_comments["created_at"].ge(now - pd.Timedelta(hours=24)).sum()
        image = (
            f'<img src="{poster}" alt="{film} poster">' if isinstance(poster, str) and poster.startswith("https://")
            else '<div style="aspect-ratio:2/3;background:#e9dfd1"></div>'
        )
        with col:
            film_url = f"?movie={quote(film)}"
            st.markdown(
                f'<a href="{film_url}" style="color:inherit;text-decoration:none">'
                f'<div class="poster-card">{image}<div class="poster-copy">'
                f'<div class="poster-title">{html.escape(film)}</div>'
                f'<div class="poster-meta">{item.get("release_date") or "Release date unavailable"}<br>'
                f'{len(film_comments):,} analyzed · {recent:,} new/24 h · {len(film_videos)} videos</div>'
                f'<div style="margin-top:8px;font-size:11px;font-weight:850;color:#d53c1c">OPEN FILM PAGE →</div>'
                f'</div></div></a>',
                unsafe_allow_html=True,
            )

st.subheader("All films analyzed till now")
st.markdown('<div class="section-note">The permanent analysis history is kept separately from the smaller current radar.</div>', unsafe_allow_html=True)
all_film_summary = (
    comments.groupby("film", as_index=False)
    .agg(
        collected_comments=("source_id", "nunique"),
        channels=("channel", "nunique"),
        first_comment=("created_at", "min"),
        latest_comment=("created_at", "max"),
    )
)
missing_history = sorted(set(all_analyzed_films) - set(all_film_summary.get("film", [])))
if missing_history:
    all_film_summary = pd.concat([
        all_film_summary,
        pd.DataFrame({"film": missing_history, "collected_comments": 0, "channels": 0})
    ], ignore_index=True)
all_film_summary["Status"] = all_film_summary["film"].map(
    lambda film: (
        "Actively fetched" if film in actively_fetched_films
        else "Scheduled—awaiting video" if film in radar_films
        else "Historical"
    )
)
all_film_summary["Release date"] = all_film_summary["film"].map(
    lambda film: catalog.get(film, {}).get("release_date") or "Unavailable"
)
st.dataframe(
    all_film_summary[["film", "Status", "Release date", "collected_comments", "channels", "latest_comment"]]
    .sort_values(["Status", "collected_comments"], ascending=[False, False]),
    width="stretch", hide_index=True,
    column_config={
        "film": "Film", "collected_comments": "Comments collected", "channels": "Channels",
        "latest_comment": st.column_config.DatetimeColumn("Latest published comment", format="DD MMM YYYY"),
    },
)

tab_overview, tab_lifetime, tab_films, tab_comments, tab_data = st.tabs([
    "30-minute live", "Lifetime analysis", "Film deep dive", "Comment explorer", "Data archive"
])

with tab_overview:
    st.subheader("Live collection and 30-minute trend")
    st.markdown('<div class="section-note">Every selected video and Short is included. Exact counter changes are stored for every completed run—even when GitHub starts late. Rates are normalized to 30 minutes so unequal intervals can be compared fairly. Times are UTC.</div>', unsafe_allow_html=True)

    monitor_activity = pd.DataFrame()
    monitored = pd.DataFrame()
    raw_monitored = pd.DataFrame()
    if not monitor_videos.empty:
        raw_monitored = monitor_videos.sort_values(["video_id", "scanned_at"]).copy()
        monitored = raw_monitored.copy()
        monitored["previous_comments"] = monitored.groupby("video_id")["comments"].shift(1)
        monitored["previous_views"] = monitored.groupby("video_id")["views"].shift(1)
        monitored["previous_scan"] = monitored.groupby("video_id")["scanned_at"].shift(1)
        monitored["elapsed_minutes"] = (
            (monitored["scanned_at"] - monitored["previous_scan"])
            .dt.total_seconds().div(60)
        )
        monitored["comments_gained"] = (
            monitored["comments"] - monitored["previous_comments"]
        ).clip(lower=0)
        monitored["views_gained"] = (
            monitored["views"] - monitored["previous_views"]
        ).clip(lower=0)
        valid_elapsed = monitored["elapsed_minutes"].where(monitored["elapsed_minutes"].gt(0))
        monitored["views_per_30m"] = monitored["views_gained"] * 30 / valid_elapsed
        monitored["comments_per_30m"] = monitored["comments_gained"] * 30 / valid_elapsed
        monitor_cutoff = now - pd.Timedelta(hours=24)
        candidate_pairs = monitored[
            monitored["previous_comments"].notna()
            & monitored["scanned_at"].ge(monitor_cutoff)
        ].copy()
        paired = candidate_pairs[candidate_pairs["elapsed_minutes"].gt(0)].copy()
        paired["period"] = paired["scanned_at"]
        paired["views_per_30m"] = paired["views_gained"] * 30 / paired["elapsed_minutes"]
        paired["comments_per_30m"] = paired["comments_gained"] * 30 / paired["elapsed_minutes"]
        deltas = (
            paired.groupby(["period", "film", "content_format"], as_index=False)
            .agg(
                views_gained=("views_gained", "sum"),
                comments_gained=("comments_gained", "sum"),
                views_per_30m=("views_per_30m", "sum"),
                comments_per_30m=("comments_per_30m", "sum"),
                elapsed_minutes=("elapsed_minutes", "median"),
            )
        )
        recent_raw = raw_monitored[raw_monitored["scanned_at"].ge(monitor_cutoff)].copy()
        recent_raw["period"] = recent_raw["scanned_at"]
        fetched = (
            recent_raw.groupby(["period", "film", "content_format"], as_index=False)
            .agg(videos_fetched=("video_id", "nunique"))
        )
        monitor_activity = fetched.merge(
            deltas, on=["period", "film", "content_format"], how="left"
        )
        rate_columns = ["views_gained", "comments_gained", "views_per_30m", "comments_per_30m", "elapsed_minutes"]
        monitor_activity[rate_columns] = (
            monitor_activity[rate_columns].fillna(0)
        )

    if monitor_activity.empty:
        st.warning("No half-hour snapshot rows exist in the last 24 hours. The scanner may have run without persisting its counter archive.")
    else:
        scan_history = (
            monitor_activity.groupby("period", as_index=False)
            .agg(
                videos_fetched=("videos_fetched", "sum"),
                views_gained=("views_gained", "sum"),
                comments_gained=("comments_gained", "sum"),
                views_per_30m=("views_per_30m", "sum"),
                comments_per_30m=("comments_per_30m", "sum"),
                elapsed_minutes=("elapsed_minutes", "median"),
            )
            .sort_values("period", ascending=False)
        )
        newest = scan_history.iloc[0]
        stored_intervals = int(recent_raw["scanned_at"].nunique())
        snapshot_lag_minutes = (
            (last_scan - current_scan_time).total_seconds() / 60
            if pd.notna(last_scan) and pd.notna(current_scan_time) else float("nan")
        )
        unique_scan_times = sorted(recent_raw["scanned_at"].dropna().unique())
        cadence = pd.Series(unique_scan_times).diff().dt.total_seconds().div(60).dropna()
        median_cadence = cadence.median() if not cadence.empty else float("nan")
        on_time_share = cadence.between(20, 70).mean() if not cadence.empty else float("nan")
        scan_metrics = st.columns(6)
        scan_metrics[0].metric("Latest videos fetched", f"{int(newest['videos_fetched']):,}")
        scan_metrics[1].metric("Exact views since prior run", f"{int(newest['views_gained']):,}")
        scan_metrics[2].metric("Exact comments since prior run", f"{int(newest['comments_gained']):,}")
        scan_metrics[3].metric("Stored runs · 24 h", f"{stored_intervals:,}")
        scan_metrics[4].metric("Median cadence", f"{median_cadence:.0f} min" if pd.notna(median_cadence) else "Pending")
        scan_metrics[5].metric(
            "Archive freshness",
            "Current" if pd.notna(current_scan_time) and abs(snapshot_lag_minutes) <= 45 else f"{snapshot_lag_minutes:.0f} min behind",
        )
        if pd.notna(snapshot_lag_minutes) and snapshot_lag_minutes > 45:
            st.error(
                f"Counter archive is stale: scanner metadata reached {last_scan.strftime('%H:%M UTC')}, "
                f"but the newest stored snapshot is {current_scan_time.strftime('%H:%M UTC')}. "
                "The repaired scanner will back-check all selected videos on its next run; growth begins from that new snapshot."
            )
        if pd.notna(on_time_share):
            st.info(
                f"Collection reliability: {on_time_share:.0%} of recent run gaps were 20–70 minutes. "
                "Delayed GitHub runs are retained; their exact gains are divided by elapsed time to produce the comparable 30-minute rates below."
            )

        coverage_tab, views_tab, comments_tab, cadence_tab = st.tabs(["Fetch coverage", "View trend / 30 min", "Comment trend / 30 min", "Scan timing"])

        def live_chart(value: str, label: str, hover: str):
            figure = px.bar(
                monitor_activity, x="period", y=value, color="film",
                facet_row="content_format", color_discrete_sequence=PALETTE,
                labels={"period": "Monitor time · UTC", value: label,
                        "film": "Film", "content_format": "Format"},
            )
            figure.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
            figure.update_layout(
                height=590, hovermode="x unified", barmode="stack", legend_title=None,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
            )
            figure.update_traces(hovertemplate=hover)
            return figure

        with coverage_tab:
            st.caption("This remains visible even for the first snapshot, before growth can be calculated.")
            st.plotly_chart(
                live_chart("videos_fetched", "Videos and Shorts fetched", "%{y:.0f} items fetched<extra></extra>"),
                width="stretch",
            )
        with views_tab:
            st.plotly_chart(
                live_chart("views_per_30m", "Views per 30 minutes", "%{y:.0f} normalized views / 30 min<extra></extra>"),
                width="stretch",
            )
        with comments_tab:
            st.plotly_chart(
                live_chart("comments_per_30m", "Comments per 30 minutes", "%{y:.1f} normalized comments / 30 min<extra></extra>"),
                width="stretch",
            )
        with cadence_tab:
            cadence_frame = scan_history.sort_values("period")
            cadence_fig = px.line(
                cadence_frame, x="period", y="elapsed_minutes", markers=True,
                labels={"period": "Completed run · UTC", "elapsed_minutes": "Minutes since prior run"},
                color_discrete_sequence=["#8338ec"],
            )
            cadence_fig.add_hline(y=30, line_dash="dash", line_color="#ff4b2b", annotation_text="30-minute target")
            cadence_fig.update_layout(height=430, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(cadence_fig, width="stretch")
        with st.expander("See exactly what every monitor fetched", expanded=False):
            latest_monitor_time = raw_monitored["scanned_at"].max()
            latest_items = raw_monitored[raw_monitored["scanned_at"].eq(latest_monitor_time)].copy()
            latest_deltas = monitored[
                monitored["scanned_at"].eq(latest_monitor_time)
            ][["video_id", "views_gained", "comments_gained", "elapsed_minutes", "views_per_30m", "comments_per_30m"]]
            latest_items = latest_items.merge(latest_deltas, on="video_id", how="left")
            st.markdown("**Items fetched in the latest completed monitor**")
            st.dataframe(
                latest_items[["film", "content_format", "channel", "title", "views", "comments", "views_gained", "comments_gained", "elapsed_minutes", "views_per_30m"]]
                .sort_values("views_per_30m", ascending=False),
                width="stretch", hide_index=True,
                column_config={
                    "film": "Film", "content_format": "Format", "channel": "Channel", "title": "Video",
                    "views": st.column_config.NumberColumn("Public views", format="%d"),
                    "comments": st.column_config.NumberColumn("Public comments", format="%d"),
                    "views_gained": st.column_config.NumberColumn("Exact new views", format="%d"),
                    "comments_gained": st.column_config.NumberColumn("Exact new comments", format="%d"),
                    "elapsed_minutes": st.column_config.NumberColumn("Elapsed min", format="%.0f"),
                    "views_per_30m": st.column_config.NumberColumn("Views / 30 min", format="%.0f"),
                },
            )
            st.markdown("**Monitor history · last 24 hours**")
            st.dataframe(
                scan_history,
                width="stretch", hide_index=True,
                column_config={
                    "period": st.column_config.DatetimeColumn("Monitor · UTC", format="DD MMM HH:mm"),
                    "videos_fetched": st.column_config.NumberColumn("Videos + Shorts", format="%d"),
                    "views_gained": st.column_config.NumberColumn("New views", format="%d"),
                    "comments_gained": st.column_config.NumberColumn("New comments", format="%d"),
                    "views_per_30m": st.column_config.NumberColumn("Views / 30 min", format="%.0f"),
                    "comments_per_30m": st.column_config.NumberColumn("Comments / 30 min", format="%.1f"),
                    "elapsed_minutes": st.column_config.NumberColumn("Elapsed min", format="%.0f"),
                },
            )

    current_start = now - pd.Timedelta(hours=24)
    previous_start = now - pd.Timedelta(hours=48)
    current = filtered[filtered["created_at"].ge(current_start)].groupby("film").size()
    previous = filtered[
        filtered["created_at"].ge(previous_start) & filtered["created_at"].lt(current_start)
    ].groupby("film").size()
    momentum = pd.DataFrame({"Last 24 h": current, "Previous 24 h": previous}).fillna(0)
    momentum["Change"] = momentum["Last 24 h"] - momentum["Previous 24 h"]
    momentum["Direction"] = momentum["Change"].map(lambda value: "Rising" if value > 0 else "Falling" if value < 0 else "Steady")
    momentum = momentum.reset_index().sort_values(["Last 24 h", "Change"], ascending=False)

    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.subheader("24-hour film momentum")
        momentum_long = momentum.melt(
            id_vars=["film"], value_vars=["Last 24 h", "Previous 24 h"],
            var_name="Window", value_name="Comments",
        )
        momentum_fig = px.bar(
            momentum_long, x="film", y="Comments", color="Window", barmode="group",
            color_discrete_map={"Last 24 h": "#ff4b2b", "Previous 24 h": "#ffb703"},
        )
        momentum_fig.update_layout(height=390, legend_title=None, xaxis_title=None,
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(momentum_fig, width="stretch")
    with right:
        st.subheader("Language mix")
        language = filtered["language"].value_counts().rename_axis("Language").reset_index(name="Comments")
        language_fig = px.pie(
            language, names="Language", values="Comments", hole=.58,
            color_discrete_sequence=["#ff4b2b", "#3a86ff", "#2ec4b6", "#8338ec"],
        )
        language_fig.update_layout(height=390, legend_title=None, margin=dict(l=0, r=0, t=10, b=0),
                                   paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(language_fig, width="stretch")

    st.subheader("Which videos are gaining attention now?")
    st.markdown('<div class="section-note">The ranking uses the latest two stored counters. Because GitHub may run late, gains are normalized to a 30-minute rate; the exact elapsed time is shown alongside it. Lifetime totals are excluded.</div>', unsafe_allow_html=True)

    growth = pd.DataFrame()
    if not monitor_videos.empty and monitor_videos.groupby("video_id").size().max() >= 2:
        ordered = monitor_videos.sort_values(["video_id", "scanned_at"])
        latest = ordered.groupby("video_id").tail(1)
        previous_rows = ordered.groupby("video_id").nth(-2).reset_index()
        previous_rows = previous_rows[["video_id", "scanned_at", "views", "comments"]].rename(
            columns={"scanned_at": "previous_scan", "views": "previous_views", "comments": "previous_comments"}
        )
        growth = latest.merge(previous_rows, on="video_id", how="inner")
        growth["Elapsed minutes"] = (
            growth["scanned_at"] - growth["previous_scan"]
        ).dt.total_seconds().div(60)
        growth["Exact views gained"] = (
            growth["views"] - growth["previous_views"]
        ).clip(lower=0)
        growth["Exact comments gained"] = (
            growth["comments"] - growth["previous_comments"]
        )
        growth["Exact comments gained"] = growth["Exact comments gained"].clip(lower=0)
        growth = growth[growth["Elapsed minutes"].gt(0)].copy()
        growth["Views / 30 min"] = growth["Exact views gained"] * 30 / growth["Elapsed minutes"]
        growth["Comments / 30 min"] = growth["Exact comments gained"] * 30 / growth["Elapsed minutes"]
        growth["Label"] = growth.apply(
            lambda row: f'{row["channel"]} · {str(row["title"])[:58]}', axis=1
        )

    def render_format_gain(format_name: str) -> None:
        if growth.empty:
            st.info(f"Waiting for two snapshots of {format_name.lower()}s. No lifetime-view chart is shown.")
            return
        ranked = growth[growth["content_format"].eq(format_name)].sort_values(
            "Views / 30 min", ascending=False
        ).head(15)
        if ranked.empty:
            st.info(f"No {format_name.lower()} snapshot pair is available yet.")
            return
        gain_fig = px.bar(
            ranked.sort_values("Views / 30 min"),
            x="Views / 30 min", y="Label", color="film", orientation="h",
            text="Views / 30 min", color_discrete_sequence=PALETTE,
            hover_data=["Elapsed minutes", "Exact views gained", "Exact comments gained", "Comments / 30 min"],
        )
        gain_fig.update_traces(texttemplate="+%{text:,.0f}", textposition="outside")
        gain_fig.update_layout(
            height=max(400, len(ranked) * 44), legend_title=None,
            xaxis_title="New views in 30 minutes", yaxis_title=None,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
        )
        st.plotly_chart(gain_fig, width="stretch")
        st.dataframe(
            ranked[["film", "channel", "title", "Elapsed minutes", "Exact views gained", "Exact comments gained", "Views / 30 min", "Comments / 30 min"]],
            width="stretch", hide_index=True,
            column_config={
                "Elapsed minutes": st.column_config.NumberColumn("Actual gap", format="%.0f min"),
                "Exact views gained": st.column_config.NumberColumn("Exact new views", format="%.0f"),
                "Exact comments gained": st.column_config.NumberColumn("Exact new comments", format="%.0f"),
                "Views / 30 min": st.column_config.NumberColumn("Views / 30 min", format="%.0f"),
                "Comments / 30 min": st.column_config.NumberColumn("Comments / 30 min", format="%.1f"),
            },
        )

    video_gain_tab, shorts_gain_tab = st.tabs(["Standard videos", "Shorts"])
    with video_gain_tab:
        render_format_gain("Video")
    with shorts_gain_tab:
        render_format_gain("Short")

    st.subheader("Conversation intelligence")
    st.markdown('<div class="section-note">Generic reactions are separated from comments that mention a specific part of the film. Percentages make films and formats comparable even when their comment volumes differ.</div>', unsafe_allow_html=True)
    specific = filtered[~filtered["topic"].eq("General reaction")]
    substantive = filtered["comment_kind"].isin(["Detailed discussion", "Question"])
    signal_cards = st.columns(4)
    signal_cards[0].metric("Topic-specific comments", f"{len(specific) / len(filtered):.0%}")
    signal_cards[1].metric("Detailed or questions", f"{substantive.mean():.0%}")
    signal_cards[2].metric("Audience questions", f"{filtered['is_question'].sum():,}")
    signal_cards[3].metric("Useful comments shown", f"{len(filtered):,}")

    topic_col, kind_col = st.columns([1.15, 1], gap="large")
    with topic_col:
        st.markdown("#### Which film aspects lead each conversation?")
        if specific.empty:
            st.info("No aspect-specific comments match these filters yet.")
        else:
            topic_counts = specific.groupby(["topic", "film"]).size().unstack(fill_value=0)
            topic_share = topic_counts.div(topic_counts.sum(axis=0).replace(0, 1), axis=1).mul(100)
            topic_share = topic_share.loc[topic_share.sum(axis=1).sort_values(ascending=False).index]
            topic_fig = go.Figure(go.Heatmap(
                z=topic_share.values, x=topic_share.columns, y=topic_share.index,
                colorscale=[[0, "#fff4e8"], [.5, "#ff9f1c"], [1, "#d53c1c"]],
                colorbar=dict(title="Share %"),
                hovertemplate="%{x}<br>%{y}: %{z:.1f}%<extra></extra>",
            ))
            topic_fig.update_layout(
                height=430, xaxis_title=None, yaxis_title=None,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
                margin=dict(l=10, r=10, t=20, b=70),
            )
            st.plotly_chart(topic_fig, width="stretch")
    with kind_col:
        st.markdown("#### Do Shorts and videos produce different responses?")
        kinds = (
            filtered.groupby(["content_format", "comment_kind"], as_index=False).size()
            .rename(columns={"content_format": "Format", "comment_kind": "Response", "size": "Comments"})
        )
        kinds["Share"] = kinds["Comments"] / kinds.groupby("Format")["Comments"].transform("sum") * 100
        kind_fig = px.bar(
            kinds, x="Format", y="Share", color="Response", barmode="stack",
            custom_data=["Comments"],
            color_discrete_map={
                "Detailed discussion": "#8338ec", "Question": "#3a86ff",
                "Short opinion": "#2ec4b6", "Quick reaction": "#ff9f1c",
            },
        )
        kind_fig.update_traces(hovertemplate="%{fullData.name}: %{y:.1f}% (%{customdata[0]} comments)<extra></extra>")
        kind_fig.update_layout(
            height=430, legend_title=None, xaxis_title=None, yaxis_title="Share of comments (%)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
        )
        st.plotly_chart(kind_fig, width="stretch")

    st.markdown("#### Distinctive words by film")
    st.markdown('<div class="section-note">Tamil, Tanglish and English terms after links, promotion language and common filler words are removed. Darker cells mean the term appears more often for that film.</div>', unsafe_allow_html=True)
    term_frames = []
    for film, film_frame in filtered.groupby("film"):
        film_terms = top_terms(film_frame["text"], 12)
        if not film_terms.empty:
            film_terms["film"] = film
            term_frames.append(film_terms)
    if term_frames:
        term_data = pd.concat(term_frames, ignore_index=True)
        leading_terms = (
            term_data.groupby("term")["mentions"].sum().nlargest(16).index
        )
        term_matrix = (
            term_data[term_data["term"].isin(leading_terms)]
            .pivot_table(index="term", columns="film", values="mentions", aggfunc="sum", fill_value=0)
        )
        term_matrix = term_matrix.loc[term_matrix.sum(axis=1).sort_values(ascending=False).index]
        term_fig = go.Figure(go.Heatmap(
            z=term_matrix.values, x=term_matrix.columns, y=term_matrix.index,
            colorscale=[[0, "#eef8ff"], [.45, "#55b9f3"], [1, "#480ca8"]],
            colorbar=dict(title="Mentions"),
            hovertemplate="%{x}<br>%{y}: %{z:.0f} mentions<extra></extra>",
        ))
        term_fig.update_layout(
            height=520, xaxis_title=None, yaxis_title=None,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
            margin=dict(l=10, r=10, t=20, b=80),
        )
        st.plotly_chart(term_fig, width="stretch")
    else:
        st.info("Not enough meaningful discussion terms match these filters yet.")

with tab_lifetime:
    st.subheader("Lifetime public totals and observed growth")
    st.markdown('<div class="section-note">Public totals are the latest lifetime counters reported by YouTube. Growth is measured only from the first snapshot stored by this radar; no earlier history is estimated.</div>', unsafe_allow_html=True)

    lifetime_latest = (
        monitor_videos.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
        if not monitor_videos.empty else pd.DataFrame()
    )
    lifetime_pairs = pd.DataFrame()
    interval_history = pd.DataFrame()
    if not monitor_videos.empty:
        lifetime_pairs = monitor_videos.sort_values(["video_id", "scanned_at"]).copy()
        lifetime_pairs["previous_scan"] = lifetime_pairs.groupby("video_id")["scanned_at"].shift(1)
        lifetime_pairs["previous_views"] = lifetime_pairs.groupby("video_id")["views"].shift(1)
        lifetime_pairs["previous_comments"] = lifetime_pairs.groupby("video_id")["comments"].shift(1)
        lifetime_pairs["new_views"] = (lifetime_pairs["views"] - lifetime_pairs["previous_views"]).clip(lower=0)
        lifetime_pairs["new_comments"] = (lifetime_pairs["comments"] - lifetime_pairs["previous_comments"]).clip(lower=0)
        lifetime_pairs = lifetime_pairs[lifetime_pairs["previous_scan"].notna()].copy()
        lifetime_pairs["elapsed_minutes"] = (
            (lifetime_pairs["scanned_at"] - lifetime_pairs["previous_scan"]).dt.total_seconds() / 60
        )
        lifetime_pairs["period"] = lifetime_pairs["scanned_at"].dt.floor("30min")
        interval_history = (
            lifetime_pairs.groupby("period", as_index=False)
            .agg(
                views_gained=("new_views", "sum"),
                comments_gained=("new_comments", "sum"),
                videos_reporting=("video_id", "nunique"),
                elapsed_minutes=("elapsed_minutes", "median"),
            )
            .sort_values("period")
        )
        interval_history["cumulative_views"] = interval_history["views_gained"].cumsum()
        interval_history["cumulative_comments"] = interval_history["comments_gained"].cumsum()

    first_snapshot = monitor_videos["scanned_at"].min() if not monitor_videos.empty else pd.NaT
    last_snapshot = monitor_videos["scanned_at"].max() if not monitor_videos.empty else pd.NaT
    public_comment_total = float(lifetime_latest["comments"].sum()) if not lifetime_latest.empty else 0
    collection_coverage = len(comments) / public_comment_total if public_comment_total else 0
    lifetime_metrics = st.columns(7)
    lifetime_metrics[0].metric("Current public views", f"{lifetime_latest['views'].sum():,.0f}" if not lifetime_latest.empty else "0")
    lifetime_metrics[1].metric("Current public comments", f"{public_comment_total:,.0f}")
    lifetime_metrics[2].metric("Unique comments collected", f"{len(comments):,}", delta=f"{collection_coverage:.1%} of public counter")
    lifetime_metrics[3].metric("Videos + Shorts", f"{lifetime_latest['video_id'].nunique():,}" if not lifetime_latest.empty else "0")
    lifetime_metrics[4].metric("Snapshot rows", f"{len(monitor_videos):,}")
    lifetime_metrics[5].metric("Distinct monitor runs", f"{monitor_videos['scanned_at'].nunique():,}" if not monitor_videos.empty else "0")
    lifetime_metrics[6].metric(
        "Monitoring span",
        f"{max(1, (last_snapshot - first_snapshot).days + 1)} days" if pd.notna(first_snapshot) and pd.notna(last_snapshot) else "Pending",
    )
    st.info(
        "Why the two comment numbers differ: **Current public comments** is YouTube’s counter across every tracked video. "
        "**Unique comments collected** contains individual recent top-level comments actually returned by the API/downloader, "
        "after deduplication. It does not include every older comment, every reply, deleted/held comments, or comments from videos "
        "where retrieval is restricted. Live scans fetch the newest 50 per video; the daily backfill requests up to 500 per video."
    )

    if interval_history.empty:
        st.info("Lifetime growth appears after at least two stored monitor snapshots.")
    else:
        st.markdown("#### Growth observed by the radar")
        cumulative_fig = go.Figure()
        cumulative_fig.add_trace(go.Scatter(
            x=interval_history["period"], y=interval_history["cumulative_views"],
            name="Observed view growth", mode="lines", fill="tozeroy",
            line=dict(color="#ff4b2b", width=3),
        ))
        cumulative_fig.add_trace(go.Scatter(
            x=interval_history["period"], y=interval_history["cumulative_comments"],
            name="Observed comment growth", mode="lines", yaxis="y2",
            line=dict(color="#3a86ff", width=3),
        ))
        cumulative_fig.update_layout(
            height=430, hovermode="x unified", legend=dict(orientation="h", y=1.12),
            xaxis=dict(title="Stored monitor time · UTC"),
            yaxis=dict(title="Views gained since monitoring began"),
            yaxis2=dict(title="Comments gained", overlaying="y", side="right", showgrid=False),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
        )
        st.plotly_chart(cumulative_fig, width="stretch")

        interval_col, daily_col = st.columns(2, gap="large")
        with interval_col:
            st.markdown("#### Every stored half-hour interval")
            regular_intervals = interval_history[interval_history["elapsed_minutes"].between(20, 70)].tail(96)
            if regular_intervals.empty:
                st.info("Waiting for the first two normally spaced repaired scans.")
            else:
                interval_fig = px.bar(
                    regular_intervals, x="period", y="views_gained",
                    color="views_gained", color_continuous_scale=["#ffd8ce", "#ff4b2b", "#8f1d08"],
                    hover_data=["comments_gained", "videos_reporting", "elapsed_minutes"],
                    labels={"period": "UTC", "views_gained": "New views"},
                )
                interval_fig.update_layout(
                    height=400, coloraxis_showscale=False,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
                )
                st.plotly_chart(interval_fig, width="stretch")
        with daily_col:
            st.markdown("#### Daily attention by film")
            film_daily = lifetime_pairs.copy()
            film_daily["day"] = film_daily["scanned_at"].dt.floor("D")
            film_daily = film_daily.groupby(["day", "film"], as_index=False)["new_views"].sum()
            daily_fig = px.area(
                film_daily, x="day", y="new_views", color="film",
                color_discrete_sequence=PALETTE,
                labels={"day": "UTC day", "new_views": "Observed view growth", "film": "Film"},
            )
            daily_fig.update_layout(
                height=400, hovermode="x unified", legend_title=None,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
            )
            st.plotly_chart(daily_fig, width="stretch")

    if not lifetime_latest.empty:
        st.markdown("#### Lifetime reach by film")
        film_lifetime = (
            lifetime_latest.groupby("film", as_index=False)
            .agg(
                public_views=("views", "sum"),
                public_comments=("comments", "sum"),
                videos=("video_id", "nunique"),
            )
        )
        film_lifetime["Comments per 1K views"] = (
            film_lifetime["public_comments"] / film_lifetime["public_views"].replace(0, pd.NA) * 1000
        ).fillna(0)
        reach_fig = px.scatter(
            film_lifetime, x="public_views", y="public_comments", size="videos", color="film",
            text="film", color_discrete_sequence=PALETTE,
            hover_data=["Comments per 1K views"],
            labels={"public_views": "Current lifetime views", "public_comments": "Current lifetime comments"},
        )
        reach_fig.update_traces(textposition="top center")
        reach_fig.update_layout(
            height=480, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
        )
        st.plotly_chart(reach_fig, width="stretch")

        channel_col, format_col = st.columns([1.3, 1], gap="large")
        with channel_col:
            st.markdown("#### Channel contribution")
            channel_summary = (
                lifetime_latest.groupby("channel", as_index=False)
                .agg(public_views=("views", "sum"), public_comments=("comments", "sum"), videos=("video_id", "nunique"))
                .nlargest(15, "public_views")
            )
            channel_fig = px.bar(
                channel_summary.sort_values("public_views"), x="public_views", y="channel",
                orientation="h", color="public_comments",
                color_continuous_scale=["#90e0ef", "#3a86ff", "#480ca8"],
                hover_data=["videos"], labels={"public_views": "Lifetime views", "channel": "Channel"},
            )
            channel_fig.update_layout(
                height=470, coloraxis_colorbar=dict(title="Comments"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
            )
            st.plotly_chart(channel_fig, width="stretch")
        with format_col:
            st.markdown("#### Video versus Short")
            format_summary = (
                lifetime_latest.groupby("content_format", as_index=False)
                .agg(videos=("video_id", "nunique"), median_views=("views", "median"), median_comments=("comments", "median"))
                .rename(columns={"content_format": "Format"})
            )
            format_fig = px.bar(
                format_summary, x="Format", y=["median_views", "median_comments"],
                barmode="group", color_discrete_sequence=["#ff4b2b", "#3a86ff"],
                labels={"value": "Median public count", "variable": "Measure"},
            )
            format_fig.update_layout(
                height=470, legend_title=None,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
            )
            st.plotly_chart(format_fig, width="stretch")

    st.markdown("#### Lifetime comment publication history")
    lifetime_comment_daily = (
        comments.assign(day=comments["created_at"].dt.floor("D"))
        .groupby(["day", "film"], as_index=False).size().rename(columns={"size": "Comments"})
    )
    comment_history_fig = px.area(
        lifetime_comment_daily, x="day", y="Comments", color="film",
        color_discrete_sequence=PALETTE,
        labels={"day": "Comment publication date", "film": "Film"},
    )
    comment_history_fig.update_layout(
        height=450, hovermode="x unified", legend_title=None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)",
    )
    st.plotly_chart(comment_history_fig, width="stretch")

with tab_films:
    film = st.selectbox("Choose a film", selected_films)
    film_comments = filtered[filtered["film"].eq(film)].copy()
    item = catalog.get(film, {})
    poster_col, info_col = st.columns([1, 3], gap="large")
    with poster_col:
        poster = item.get("poster_url")
        if isinstance(poster, str):
            st.markdown(f'<img src="{poster}" style="width:100%;border-radius:14px">', unsafe_allow_html=True)
    with info_col:
        st.title(film)
        st.caption(f"Release date: {item.get('release_date') or 'Unavailable'}")
        detail_metrics = st.columns(4)
        detail_metrics[0].metric("Analyzed", f"{len(film_comments):,}")
        detail_metrics[1].metric("Last 24 h", f"{film_comments['created_at'].ge(now - pd.Timedelta(hours=24)).sum():,}")
        detail_metrics[2].metric("Questions", f"{film_comments['is_question'].sum():,}")
        detail_metrics[3].metric("Detailed comments", f"{film_comments['comment_kind'].eq('Detailed discussion').sum():,}")

    film_frequency = "30min" if window <= 72 else "h" if window <= 168 else "D"
    film_time_label = "30 minutes" if film_frequency == "30min" else "hour" if film_frequency == "h" else "day"
    film_timeline = (
        film_comments.assign(period=film_comments["created_at"].dt.floor(film_frequency))
        .groupby("period", as_index=False).size().rename(columns={"size": "comments"})
    )
    line = px.line(film_timeline, x="period", y="comments", markers=True,
                   color_discrete_sequence=["#ff4b2b"])
    line.update_traces(fill="tozeroy")
    line.update_layout(height=360, xaxis_title="Published time", yaxis_title=f"Comments per {film_time_label}",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
    st.plotly_chart(line, width="stretch")

    film_video_table = latest_videos[latest_videos["film"].eq(film)].copy() if not latest_videos.empty else pd.DataFrame()
    if not film_video_table.empty:
        film_video_table["url"] = "https://youtube.com/watch?v=" + film_video_table["video_id"].astype(str)
        st.subheader("Videos and Shorts being monitored")
        st.dataframe(
            film_video_table[["content_format", "channel", "title", "published_at", "views", "likes", "comments", "url"]]
            .sort_values("views", ascending=False),
            width="stretch", hide_index=True,
            column_config={"url": st.column_config.LinkColumn("Watch"),
                           "views": st.column_config.NumberColumn("Views", format="%d"),
                           "published_at": st.column_config.DatetimeColumn("Published", format="DD MMM YYYY")},
        )

with tab_comments:
    included = int((~comments["low_information"]).sum())
    filtered_out = int(comments["low_information"].sum())
    quality_cols = st.columns(4)
    quality_cols[0].metric("Included comments", f"{included:,}")
    quality_cols[1].metric("Low-information filtered", f"{filtered_out:,}")
    quality_cols[2].metric("Questions detected", f"{filtered['is_question'].sum():,}")
    quality_cols[3].metric("Median words", f"{filtered['word_count'].median():.0f}")

    search = st.text_input("Search comment text")
    explorer = filtered.copy()
    if search:
        explorer = explorer[explorer["text"].str.contains(search, case=False, na=False, regex=False)]
    columns = ["film", "content_format", "channel", "video_title", "language", "topic", "comment_kind",
               "text", "likes", "reply_count", "created_at", "url"]
    st.dataframe(
        explorer[columns].sort_values(["likes", "created_at"], ascending=[False, False]),
        width="stretch", hide_index=True,
        column_config={"url": st.column_config.LinkColumn("Open on YouTube"),
                       "created_at": st.column_config.DatetimeColumn("Published", format="DD MMM YYYY, HH:mm")},
    )
    st.download_button(
        "Download analyzed YouTube comments",
        explorer[columns].to_csv(index=False),
        "tamil-cinema-youtube-comments.csv", "text/csv",
    )

with tab_data:
    st.subheader("Complete data archive")
    st.markdown('<div class="section-note">Download the unfiltered stored counters, the derived half-hour changes, or the complete comment archive. Snapshot rows are the source of truth for monitoring trends.</div>', unsafe_allow_html=True)
    archive_metrics = st.columns(4)
    archive_metrics[0].metric("Snapshot rows", f"{len(videos):,}")
    archive_metrics[1].metric("Half-hour intervals", f"{len(interval_history):,}")
    archive_metrics[2].metric("Comment rows", f"{len(comments):,}")
    archive_metrics[3].metric("Retention", f"{meta.get('keep_history_days', 730)} days")

    download_cols = st.columns(4)
    download_cols[0].download_button(
        "Download raw snapshots",
        videos.to_csv(index=False),
        "cinema-wall-video-snapshots.csv", "text/csv", width="stretch",
    )
    download_cols[1].download_button(
        "Download 30-min series",
        interval_history.to_csv(index=False),
        "cinema-wall-30-minute-timeseries.csv", "text/csv", width="stretch",
        disabled=interval_history.empty,
    )
    download_cols[2].download_button(
        "Download all comments",
        comments.to_csv(index=False),
        "cinema-wall-all-comments.csv", "text/csv", width="stretch",
    )
    download_cols[3].download_button(
        "Download scan metadata",
        json.dumps(meta, indent=2, ensure_ascii=False),
        "cinema-wall-scan-metadata.json", "application/json", width="stretch",
    )

    dataset = st.radio(
        "Preview dataset", ["30-minute time series", "Raw video snapshots", "Collected comments"],
        horizontal=True,
    )
    if dataset == "30-minute time series":
        preview = interval_history.sort_values("period", ascending=False)
    elif dataset == "Raw video snapshots":
        preview = videos.sort_values("scanned_at", ascending=False)
    else:
        preview = comments.sort_values("created_at", ascending=False)
    st.dataframe(preview.head(2000), width="stretch", hide_index=True)
    if len(preview) > 2000:
        st.caption(f"Previewing the newest 2,000 of {len(preview):,} rows. The download contains every stored row.")

with st.expander("Monitor health and methodology"):
    st.write(f"Status: **{meta.get('status', 'unknown')}**")
    st.write(f"Schedule: every **{meta.get('scan_interval_minutes', 30)} minutes**")
    st.write(f"New-video discovery: every **{meta.get('video_discovery_hours', 6)} hours**")
    st.write("Collectors: " + ", ".join(meta.get("collectors", ["YouTube Data API"])))
    st.write("Noise filtering removes extremely short, link-promotional and non-text reactions from analytical charts; raw stored comments remain available.")
    errors = meta.get("errors", [])
    if errors:
        st.warning(f"{len(errors)} source warnings occurred in the latest monitor run.")
        st.code("\n".join(errors), language=None)

st.caption("Tamil Cinema YouTube Radar · Public YouTube data · Activity signals are not audience size, film quality or box-office estimates.")
