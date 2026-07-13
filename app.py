from __future__ import annotations

import html
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

comments, videos, meta = get_data("youtube-radar-v2")
if not comments.empty:
    if "channel" not in comments:
        comments["channel"] = comments.get("source", "Unknown")
    if "video_id" not in comments:
        comments["video_id"] = comments.get("parent_id", "")
    if "video_title" not in comments:
        comments["video_title"] = ""
    comments["channel"] = comments["channel"].fillna(comments.get("source", "Unknown"))
    comments["likes"] = pd.to_numeric(comments.get("likes", 0), errors="coerce").fillna(0)

catalog = {item.get("title"): item for item in meta.get("movie_catalog", []) if isinstance(item, dict)}

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
        fact_cols[2].metric("Review videos", len(film_videos))
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
                    st.caption(f"{channel} · {int(row.get('views', 0)):,} views · {int(row.get('comments', 0)):,} public comments")
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
    st.caption("YouTube monitoring every 30 minutes")
    if not comments.empty:
        all_films = sorted(comments["film"].dropna().unique())
        selected_films = st.multiselect("Films", all_films, default=all_films)
        all_channels = sorted(comments["channel"].dropna().unique())
        selected_channels = st.multiselect("Channels", all_channels, default=all_channels)
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
    st.caption("Known review videos, public statistics and recent comments refresh at :10 and :40 UTC. New video discovery runs every six hours to protect YouTube quota.")
    if st.button("Refresh dashboard data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown("""<div class="hero"><span class="kicker">TAMIL CINEMA · YOUTUBE INTELLIGENCE</span>
<h1>Reviews move fast.<br>The radar moves faster.</h1>
<p>A 30-minute tracker for recent Tamil films: comment velocity, video reach, channel contribution,
language mix, discussion topics and audience questions—without turning conversation into a quality score.</p></div>""", unsafe_allow_html=True)

if comments.empty:
    st.warning("No YouTube comments are stored yet. Run **Tamil cinema YouTube monitor** once from GitHub Actions.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
cutoff = now - pd.Timedelta(hours=int(window))
filtered = comments[
    comments["film"].isin(selected_films)
    & comments["channel"].isin(selected_channels)
    & comments["created_at"].ge(cutoff)
    & comments["likes"].ge(minimum_likes)
].copy()
if not include_noise:
    filtered = filtered[~filtered["low_information"]].copy()
if filtered.empty:
    st.info("No analyzed comments match the current filters.")
    st.stop()

video_view = videos[videos["film"].isin(selected_films)].copy() if not videos.empty else videos
latest_videos = (
    video_view.sort_values("scanned_at").drop_duplicates("video_id", keep="last")
    if not video_view.empty else video_view
)
last_scan = pd.to_datetime(meta.get("last_scan"), errors="coerce", utc=True)
last_24 = filtered[filtered["created_at"].ge(now - pd.Timedelta(hours=24))]

metrics = st.columns(5)
metrics[0].metric("Films on radar", filtered["film"].nunique())
metrics[1].metric("Videos monitored", latest_videos["video_id"].nunique() if not latest_videos.empty else 0)
metrics[2].metric("Comments analyzed", f"{len(filtered):,}")
metrics[3].metric("New comments · 24 h", f"{len(last_24):,}")
metrics[4].metric("Last monitor", last_scan.strftime("%d %b · %H:%M UTC") if pd.notna(last_scan) else "Pending")

catalog = {item.get("title"): item for item in meta.get("movie_catalog", []) if isinstance(item, dict)}
st.subheader("Films on the radar")
st.markdown('<div class="section-note">Release context, collected comments and active review videos.</div>', unsafe_allow_html=True)
wall = [film for film in selected_films if film in catalog][:10] or selected_films[:10]
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

tab_overview, tab_films, tab_comments = st.tabs(["Attention overview", "Film deep dive", "Comment explorer"])

with tab_overview:
    st.subheader("Comment arrival over time")
    st.markdown('<div class="section-note">Published comments, grouped by film. This measures conversation activity—not unique viewers.</div>', unsafe_allow_html=True)
    frequency = "h" if window <= 168 else "D"
    time_label = "hour" if frequency == "h" else "day"
    activity = (
        filtered.assign(period=filtered["created_at"].dt.floor(frequency))
        .groupby(["period", "film"], as_index=False)
        .size().rename(columns={"size": "comments"})
    )
    area = px.area(
        activity, x="period", y="comments", color="film",
        color_discrete_sequence=PALETTE,
        labels={"period": "Published time", "comments": f"Comments per {time_label}", "film": "Film"},
    )
    area.update_layout(height=460, hovermode="x unified", legend_title=None,
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
    st.plotly_chart(area, width="stretch")

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

    st.subheader("Which review videos are gaining attention?")
    st.markdown('<div class="section-note">A simple ranking: how many public views each video gained per hour since the previous monitor. Higher means attention is growing faster.</div>', unsafe_allow_html=True)
    if not video_view.empty and video_view.groupby("video_id").size().max() >= 2:
        ordered = video_view.sort_values(["video_id", "scanned_at"])
        latest = ordered.groupby("video_id").tail(1)
        previous_rows = ordered.groupby("video_id").nth(-2).reset_index()
        previous_rows = previous_rows[["video_id", "scanned_at", "views", "comments"]].rename(
            columns={"scanned_at": "previous_scan", "views": "previous_views", "comments": "previous_comments"}
        )
        growth = latest.merge(previous_rows, on="video_id", how="inner")
        elapsed = (growth["scanned_at"] - growth["previous_scan"]).dt.total_seconds().div(3600).clip(lower=.05)
        growth["Views gained"] = (growth["views"] - growth["previous_views"]).clip(lower=0)
        growth["New public comments"] = (growth["comments"] - growth["previous_comments"]).clip(lower=0)
        growth["Views gained / hour"] = growth["Views gained"] / elapsed
        growth["Label"] = growth.apply(
            lambda row: f'{row["channel"]} · {str(row["title"])[:58]}', axis=1
        )
        ranked = growth.sort_values("Views gained / hour", ascending=False).head(15)
        gain_fig = px.bar(
            ranked.sort_values("Views gained / hour"),
            x="Views gained / hour", y="Label", color="film", orientation="h",
            text="Views gained", color_discrete_sequence=PALETTE,
            hover_data=["views", "comments", "New public comments"],
        )
        gain_fig.update_traces(texttemplate="+%{text:,.0f} views", textposition="outside")
        gain_fig.update_layout(height=max(420, len(ranked) * 42), legend_title=None,
                               xaxis_title="Views gained per hour", yaxis_title=None,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(gain_fig, width="stretch")
        st.dataframe(
            ranked[["film", "channel", "title", "views", "Views gained", "Views gained / hour", "New public comments"]],
            width="stretch", hide_index=True,
            column_config={"Views gained / hour": st.column_config.NumberColumn("Views/hour", format="%.0f"),
                           "views": st.column_config.NumberColumn("Current views", format="%d")},
        )
    elif not latest_videos.empty:
        st.info("One snapshot exists. After the next 30-minute monitor, this section will show exactly how many views each video gained.")
        current = latest_videos.sort_values("views", ascending=False).head(15).copy()
        current["Label"] = current.apply(lambda row: f'{row["channel"]} · {str(row["title"])[:58]}', axis=1)
        reach = px.bar(
            current.sort_values("views"), x="views", y="Label", orientation="h",
            color="views", text="views", color_continuous_scale=["#ffd7cc", "#ff4b2b", "#721600"],
        )
        reach.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        reach.update_layout(height=max(420, len(current) * 42), xaxis_title="Current public views",
                            yaxis_title=None, coloraxis_showscale=False,
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(reach, width="stretch")

    topic_col, kind_col = st.columns(2, gap="large")
    with topic_col:
        st.subheader("What viewers discuss")
        topic = filtered["topic"].value_counts().rename_axis("Topic").reset_index(name="Comments")
        topic_fig = px.bar(
            topic.sort_values("Comments"), x="Comments", y="Topic", orientation="h",
            color="Comments", color_continuous_scale=["#ffd6cc", "#ff4b2b", "#7a1700"],
        )
        topic_fig.update_layout(height=430, coloraxis_showscale=False, yaxis_title=None,
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(topic_fig, width="stretch")
    with kind_col:
        st.subheader("Depth of participation")
        kinds = filtered["comment_kind"].value_counts().rename_axis("Type").reset_index(name="Comments")
        kind_fig = px.bar(
            kinds, x="Type", y="Comments", color="Type",
            color_discrete_map={
                "Detailed discussion": "#8338ec", "Question": "#3a86ff",
                "Short opinion": "#2ec4b6", "Quick reaction": "#ff9f1c",
            },
        )
        kind_fig.update_layout(height=430, showlegend=False, xaxis_title=None,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(kind_fig, width="stretch")

    term_data = top_terms(filtered["text"], 20)
    if not term_data.empty:
        st.subheader("Frequently used discussion terms")
        term_fig = px.bar(
            term_data.sort_values("mentions"), x="mentions", y="term", orientation="h",
            color="mentions", color_continuous_scale=["#90e0ef", "#3a86ff", "#480ca8"],
        )
        term_fig.update_layout(height=520, coloraxis_showscale=False, xaxis_title="Mentions",
                               yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(term_fig, width="stretch")

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

    film_timeline = (
        film_comments.assign(period=film_comments["created_at"].dt.floor(frequency))
        .groupby("period", as_index=False).size().rename(columns={"size": "comments"})
    )
    line = px.line(film_timeline, x="period", y="comments", markers=True,
                   color_discrete_sequence=["#ff4b2b"])
    line.update_traces(fill="tozeroy")
    line.update_layout(height=360, xaxis_title="Published time", yaxis_title=f"Comments per {time_label}",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
    st.plotly_chart(line, width="stretch")

    film_video_table = latest_videos[latest_videos["film"].eq(film)].copy() if not latest_videos.empty else pd.DataFrame()
    if not film_video_table.empty:
        film_video_table["url"] = "https://youtube.com/watch?v=" + film_video_table["video_id"].astype(str)
        st.subheader("Videos being monitored")
        st.dataframe(
            film_video_table[["channel", "title", "published_at", "views", "likes", "comments", "url"]]
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
    columns = ["film", "channel", "video_title", "language", "topic", "comment_kind",
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
