from __future__ import annotations

import html
import json
import re
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_live, load_metadata, load_video_snapshots
from youtube_analysis import normalize_text, top_terms

PALETTE = ["#ff4b2b", "#ff9f1c", "#2ec4b6", "#3a86ff", "#8338ec", "#ff006e", "#8ac926", "#6c757d", "#e76f51", "#00b4d8"]
PROMO_RE = re.compile(r"https?://|subscribe|my channel|follow me|telegram|whatsapp|giveaway", re.I)
HISTORY_TERMS = ["old movie", "older film", "previous film", "remake", "original film", "copy of", "inspired by", "better than", "worse than", "compared to", "80s", "90s", "palaya padam", "munnadi padam", "பழைய படம்", "முந்தைய படம்", "ஒப்பிட", "ரீமேக்"]
CURRENT_TERMS = ["election", "politics", "government", "social media", "meme", "troll", "reels", "viral", "arasiyal", "இன்றைய", "இப்போதைய", "அரசியல்", "தேர்தல்", "சமூக வலை", "மீம்"]
SARCASM_TERMS = ["/s", "yeah right", "what a masterpiece", "oscar kudukanum", "award kudukanum", "enna koduma", "enna da idhu", "vera level logic", "என்ன கொடுமை", "என்னடா இது", "விருது கொடுக்கணும்", "ஆஸ்கார்", "அடேங்கப்பா", "போதும்டா", "யாருடா"]

st.set_page_config(page_title="Tamil Cinema YouTube Radar", page_icon="▶️", layout="wide")
st.markdown("""
<style>
.stApp{background:#f7f3ea}.block-container{max-width:1480px;padding-top:1.2rem}
.hero{background:linear-gradient(115deg,#141414 0%,#3a1710 54%,#ff4b2b 140%);color:white;padding:42px 46px;border-radius:18px;margin:0 0 24px;box-shadow:0 18px 45px rgba(55,27,18,.16)}
.kicker{font-size:11px;font-weight:900;letter-spacing:.19em;color:#ffb39f}.hero h1{font-size:56px;line-height:.96;margin:10px 0 15px}.hero p{font-size:17px;color:#eaded8;max-width:860px;margin:0}
[data-testid="stMetric"]{background:#fffdf8;border:1px solid #ddd3c3;padding:16px;border-radius:12px;box-shadow:0 5px 16px rgba(46,36,24,.04)}
.poster-card{background:#fffdf8;border:1px solid #ddd3c3;border-radius:12px;overflow:hidden;margin-bottom:12px}.poster-card img{width:100%;aspect-ratio:2/3;object-fit:cover;display:block}.poster-copy{padding:10px 11px 12px}.poster-title{font-size:17px;font-weight:850;line-height:1.05}.poster-meta{font-size:11px;color:#766d61;margin-top:5px;line-height:1.45}
.film-row{display:grid;grid-template-columns:82px minmax(220px,1.8fr) repeat(5,minmax(86px,1fr)) 108px;gap:14px;align-items:center;background:#fffdf8;border:1px solid #ddd3c3;border-radius:16px;padding:10px 12px;margin:9px 0;box-shadow:0 5px 16px rgba(46,36,24,.035)}
.film-row img{width:72px;height:108px;object-fit:cover;border-radius:10px;background:#e9dfd1}.film-main{min-width:0}.film-name{font-size:19px;font-weight:900;line-height:1.05;color:#17130f}.film-sub{font-size:12px;color:#756d62;margin-top:5px;line-height:1.35}.film-pill{display:inline-block;background:#f4eadb;border:1px solid #dfd1be;border-radius:999px;padding:3px 8px;font-size:10px;font-weight:850;color:#6b4e2f;margin-top:7px}.film-cell{font-size:12px;color:#756d62}.film-cell b{display:block;font-size:18px;color:#17130f;line-height:1.15}.film-open{font-size:11px;font-weight:900;color:#d53c1c;text-align:right}
@media(max-width:900px){.film-row{grid-template-columns:72px 1fr;gap:10px}.film-cell,.film-open{grid-column:2;text-align:left}.film-row img{width:62px;height:93px}.film-name{font-size:17px}}
.section-note{color:#756d62;font-size:13px;margin-top:-8px;margin-bottom:12px}.badge{display:inline-block;background:#ffe6df;color:#a22d16;border-radius:20px;padding:5px 9px;font-size:10px;font-weight:800;letter-spacing:.05em}.insight-card{background:#fffdf8;border:1px solid #ddd3c3;border-radius:12px;padding:15px 16px;margin-bottom:12px;min-height:120px}.insight-card .label{font-size:11px;font-weight:850;letter-spacing:.08em;color:#8d8173;text-transform:uppercase}.insight-card .value{font-size:24px;font-weight:900;line-height:1.05;margin-top:8px;color:#15130f}.insight-card .note{font-size:12px;color:#70675d;margin-top:7px;line-height:1.35}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_data(schema: str):
    return load_live(), load_video_snapshots(), load_metadata()


def valid_text(value: object) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip().lower() not in {"", "nan", "none", "null"}


def compact(value: object, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def classify_context(text: str) -> list[str]:
    lowered = text.lower()
    labels = []
    if any(term in lowered for term in HISTORY_TERMS):
        labels.append("Older-film / historical comparison")
    if any(term in lowered for term in CURRENT_TERMS):
        labels.append("Contemporary social reference")
    return labels


def sarcasm_cues(text: str) -> list[str]:
    lowered = text.lower()
    cues = []
    if any(term in lowered for term in SARCASM_TERMS):
        cues.append("Tamil/Tanglish rhetorical phrase")
    laughter = bool(re.search(r"😂|🤣|😏|🙃|😅|\b(lol|lmao|haha+)\b", lowered))
    criticism = bool(re.search(r"\b(bad|worst|boring|mokka|waste|cringe|lag|flop|average)\b|மோசம்|மொக்க|போர்|சுமார்", lowered))
    praise = bool(re.search(r"\b(good|great|amazing|super|mass|sema|nalla|worth|love)\b|அருமை|நல்ல|சூப்பர்|செம", lowered))
    if laughter and criticism:
        cues.append("laughter paired with criticism")
    if praise and criticism:
        cues.append("contrasting praise and criticism")
    if re.search(r"[!?]{2,}", text) and (laughter or criticism):
        cues.append("rhetorical punctuation")
    return cues


def card(label: str, value: object, note: str) -> None:
    st.markdown(
        f'<div class="insight-card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(str(value))}</div><div class="note">{html.escape(note)}</div></div>',
        unsafe_allow_html=True,
    )


def fmt_int(value: object) -> str:
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "0"


def poster_for(movie: str, catalog: dict[str, dict], latest: pd.DataFrame) -> tuple[str | None, str]:
    item = catalog.get(movie, {})
    poster = item.get("poster_url")
    if isinstance(poster, str) and poster.startswith("http"):
        return poster, "TMDB poster"
    film_videos = latest[latest["film"].eq(movie)] if not latest.empty and "film" in latest else pd.DataFrame()
    if not film_videos.empty:
        thumbs = film_videos["thumbnail_url"].dropna().astype(str)
        thumbs = thumbs[thumbs.str.startswith("http")]
        if not thumbs.empty:
            return thumbs.iloc[0], "YouTube thumbnail fallback"
    return None, "Poster unavailable"


def render_film_list(rows: pd.DataFrame, title: str, note: str, limit: int | None = None) -> None:
    st.subheader(title)
    st.markdown(f'<div class="section-note">{html.escape(note)}</div>', unsafe_allow_html=True)
    if rows.empty:
        st.info("No films match the current filters.")
        return
    display = rows.head(limit) if limit else rows
    for _, row in display.iterrows():
        poster = row.get("poster_url")
        image = (
            f'<img src="{html.escape(str(poster))}" alt="{html.escape(str(row["film"]))} poster">'
            if isinstance(poster, str) and poster.startswith("http")
            else '<div style="width:72px;height:108px;border-radius:10px;background:#e9dfd1"></div>'
        )
        release = row.get("release_date") or "Release date unavailable"
        poster_source = row.get("poster_source") or "Poster source unavailable"
        st.markdown(
            f'''<a href="?movie={quote(str(row["film"]))}" style="color:inherit;text-decoration:none">
<div class="film-row">
  <div>{image}</div>
  <div class="film-main">
    <div class="film-name">{html.escape(str(row["film"]))}</div>
    <div class="film-sub">{html.escape(str(release))} · {html.escape(str(row.get("status", "Historical")))}</div>
    <span class="film-pill">{html.escape(str(poster_source))}</span>
  </div>
  <div class="film-cell"><b>{fmt_int(row.get("collected_comments", 0))}</b>stored comments</div>
  <div class="film-cell"><b>{fmt_int(row.get("public_comments", 0))}</b>public comments</div>
  <div class="film-cell"><b>{fmt_int(row.get("public_views", 0))}</b>public views</div>
  <div class="film-cell"><b>{fmt_int(row.get("videos", 0))}+{fmt_int(row.get("shorts", 0))}</b>videos + Shorts</div>
  <div class="film-cell"><b>+{fmt_int(row.get("views_per_30m", 0))}</b>views / 30 min</div>
  <div class="film-open">OPEN →</div>
</div></a>''',
            unsafe_allow_html=True,
        )


def prep_comments(frame: pd.DataFrame, video_frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    comments = frame.copy()
    for column, default in {
        "film": "Unknown", "channel": "Unknown", "video_id": "", "video_title": "",
        "content_format": "Unknown", "text": "", "language": "Unknown", "topic": "General reaction",
        "reaction_signal": "Mixed / unclear", "comment_kind": "Quick reaction", "url": "",
    }.items():
        if column not in comments:
            comments[column] = default
    comments["channel"] = comments["channel"].fillna(comments.get("source", "Unknown"))
    comments["likes"] = pd.to_numeric(comments.get("likes", 0), errors="coerce").fillna(0)
    comments["reply_count"] = pd.to_numeric(comments.get("reply_count", 0), errors="coerce").fillna(0)
    comments["created_at"] = pd.to_datetime(comments.get("created_at"), errors="coerce", utc=True)
    comments["word_count"] = pd.to_numeric(comments.get("word_count", comments["text"].astype(str).str.split().str.len()), errors="coerce").fillna(0)
    comments["low_information"] = comments.get("low_information", False).fillna(False).astype(bool)
    comments["is_question"] = comments.get("is_question", comments["text"].astype(str).str.contains("?", regex=False)).fillna(False).astype(bool)
    if not video_frame.empty and "content_format" in video_frame:
        format_map = video_frame.sort_values("scanned_at").drop_duplicates("video_id", keep="last").set_index("video_id")["content_format"]
        inferred = comments["video_id"].astype(str).map(format_map)
        comments["content_format"] = comments["content_format"].where(comments["content_format"].isin(["Video", "Short"]), inferred).fillna("Video")
    else:
        comments["content_format"] = comments["content_format"].replace("Unknown", "Video").fillna("Video")
    return comments


def prep_videos(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    videos = frame.copy()
    for column, default in {"film": "Unknown", "channel": "Unknown", "title": "", "content_format": "Video", "video_id": "", "thumbnail_url": ""}.items():
        if column not in videos:
            videos[column] = default
    videos["scanned_at"] = pd.to_datetime(videos.get("scanned_at"), errors="coerce", utc=True)
    videos["published_at"] = pd.to_datetime(videos.get("published_at"), errors="coerce", utc=True)
    for column in ["views", "likes", "comments"]:
        videos[column] = pd.to_numeric(videos.get(column, 0), errors="coerce").fillna(0)
    videos["content_format"] = videos["content_format"].where(videos["content_format"].isin(["Video", "Short"]), "Video")
    return videos


def latest_video_rows(video_frame: pd.DataFrame) -> pd.DataFrame:
    if video_frame.empty:
        return pd.DataFrame()
    return video_frame.sort_values("scanned_at").drop_duplicates("video_id", keep="last")


def video_growth(video_frame: pd.DataFrame) -> pd.DataFrame:
    if video_frame.empty or not {"video_id", "scanned_at", "views", "comments"}.issubset(video_frame.columns):
        return pd.DataFrame()
    ordered = video_frame.dropna(subset=["video_id", "scanned_at"]).sort_values(["video_id", "scanned_at"]).copy()
    ordered = ordered[ordered.groupby("video_id")["video_id"].transform("size").ge(2)].copy()
    if ordered.empty:
        return ordered
    latest = ordered.groupby("video_id").tail(1).copy()
    previous = ordered.groupby("video_id").nth(-2).reset_index()[["video_id", "scanned_at", "views", "comments"]]
    previous = previous.rename(columns={"scanned_at": "previous_scan", "views": "previous_views", "comments": "previous_comments"})
    growth = latest.merge(previous, on="video_id", how="inner")
    growth["elapsed_minutes"] = (growth["scanned_at"] - growth["previous_scan"]).dt.total_seconds().div(60)
    growth = growth[growth["elapsed_minutes"].gt(0)].copy()
    if growth.empty:
        return growth
    growth["views_gained"] = (growth["views"] - growth["previous_views"]).clip(lower=0)
    growth["comments_gained"] = (growth["comments"] - growth["previous_comments"]).clip(lower=0)
    growth["views_per_30m"] = growth["views_gained"] * 30 / growth["elapsed_minutes"]
    growth["comments_per_30m"] = growth["comments_gained"] * 30 / growth["elapsed_minutes"]
    return growth


def audience_summary(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Not enough comments collected yet."
    useful = frame[~frame["low_information"]].copy()
    if useful.empty:
        return "Mostly short reactions so far; not enough useful audience text yet."
    signalled = useful[useful["reaction_signal"].ne("Mixed / unclear")]
    mood = "mixed or still developing"
    if len(signalled) >= 3:
        leader = signalled["reaction_signal"].value_counts().index[0]
        mood = "mostly appreciative" if leader == "Appreciative" else "mostly critical" if leader == "Critical" else "mixed"
    topic = useful["topic"].value_counts().index[0]
    return f"Audience response is {mood}; discussion is led by {topic.lower()} ({len(useful):,} useful comments)."


def render_movie_page(movie: str, comments: pd.DataFrame, videos: pd.DataFrame, meta: dict, catalog: dict[str, dict]) -> None:
    item = catalog.get(movie, {})
    film_comments = comments[comments["film"].eq(movie)].copy()
    film_videos = latest_video_rows(videos[videos["film"].eq(movie)])
    st.markdown('<a href="./" style="text-decoration:none;font-weight:800;color:#d53c1c">← Back to all films</a>', unsafe_allow_html=True)
    backdrop = item.get("backdrop_url")
    if isinstance(backdrop, str) and backdrop.startswith("http"):
        st.markdown(f'<div style="height:260px;border-radius:18px;background:linear-gradient(90deg,rgba(10,10,10,.82),rgba(10,10,10,.18)),url({backdrop}) center/cover;margin:16px 0"></div>', unsafe_allow_html=True)
    poster_col, detail_col = st.columns([1, 3], gap="large")
    with poster_col:
        poster = item.get("poster_url")
        if isinstance(poster, str) and poster.startswith("http"):
            st.image(poster, width="stretch")
    with detail_col:
        st.markdown('<span class="badge">FILM PAGE</span>', unsafe_allow_html=True)
        st.title(movie)
        fact_cols = st.columns(4)
        fact_cols[0].metric("Release date", item.get("release_date") or "Unavailable")
        fact_cols[1].metric("Runtime", f'{item.get("runtime")} min' if item.get("runtime") else "Unavailable")
        fact_cols[2].metric("Videos", int(film_videos["content_format"].eq("Video").sum()) if not film_videos.empty else 0)
        fact_cols[3].metric("Shorts", int(film_videos["content_format"].eq("Short").sum()) if not film_videos.empty else 0)
        if item.get("overview"):
            st.write(item["overview"])
        facts = []
        if item.get("director"):
            facts.append(f"**Director:** {item['director']}")
        if item.get("genres"):
            facts.append("**Genres:** " + ", ".join(item["genres"]))
        if item.get("cast"):
            facts.append("**Main cast:** " + ", ".join(item["cast"][:8]))
        if facts:
            st.markdown("  \n".join(facts))
        tmdb_id = item.get("tmdb_id")
        source = f"https://www.themoviedb.org/movie/{tmdb_id}" if tmdb_id else "https://www.themoviedb.org/"
        st.caption(f"Facts cross-checked from [TMDB]({source}). Audience readings use only collected YouTube comments.")

    st.subheader("Audience report")
    if film_comments.empty:
        st.info("No comments collected for this film yet. If matching videos exist, the next monitor will build the report.")
    else:
        film_comments["normalized_text"] = film_comments["text"].map(normalize_text)
        film_comments["promotional"] = film_comments["normalized_text"].str.contains(PROMO_RE, na=False)
        useful = film_comments[~film_comments["low_information"]].copy()
        analytical = useful[useful["is_question"] | useful["word_count"].ge(8) | ~useful["topic"].eq("General reaction")].copy()
        cols = st.columns(5)
        cols[0].metric("Collected", f"{len(film_comments):,}")
        cols[1].metric("Useful text", f"{len(useful) / len(film_comments):.0%}")
        cols[2].metric("Analytical/questions", f"{len(analytical):,}")
        cols[3].metric("Low-info", f"{film_comments['low_information'].mean():.0%}")
        cols[4].metric("Promo/link", f"{film_comments['promotional'].mean():.0%}")
        left, right = st.columns([1, 1.35], gap="large")
        with left:
            st.markdown("#### Praise and criticism topics")
            topic_frames = []
            for reaction, label in [("Appreciative", "Appreciative wording"), ("Critical", "Critical wording")]:
                data = useful[useful["reaction_signal"].eq(reaction) & ~useful["topic"].eq("General reaction")]
                if not data.empty:
                    table = data["topic"].value_counts().head(5).rename_axis("Topic").reset_index(name="Comments")
                    table["Signal"] = label
                    topic_frames.append(table)
            if topic_frames:
                st.dataframe(pd.concat(topic_frames)[["Signal", "Topic", "Comments"]], hide_index=True, width="stretch")
            else:
                st.caption("Aspect-level praise/criticism is still thin.")
        with right:
            st.markdown("#### Useful audience points")
            examples = analytical.sort_values(["likes", "word_count"], ascending=False).head(10).copy()
            if examples.empty:
                st.caption("Not enough detailed comments yet.")
            else:
                examples["Why useful"] = examples.apply(lambda r: "Question" if r["is_question"] else str(r["topic"]) if r["topic"] != "General reaction" else "Detailed opinion", axis=1)
                examples["Comment"] = examples["text"].astype(str).str.slice(0, 260)
                st.dataframe(examples[["channel", "Why useful", "reaction_signal", "Comment", "likes", "url"]], hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("Open")})

    st.subheader("Reviewer videos and audience response")
    if film_videos.empty:
        st.info("Reviewer details will appear after the next monitor scan.")
    else:
        for _, row in film_videos.sort_values(["views", "comments"], ascending=False).iterrows():
            vid = str(row.get("video_id", ""))
            audience = film_comments[film_comments["video_id"].astype(str).eq(vid)]
            with st.container(border=True):
                thumb_col, text_col = st.columns([1, 3], gap="large")
                with thumb_col:
                    thumb = row.get("thumbnail_url")
                    if not valid_text(thumb) or not str(thumb).startswith("http"):
                        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    st.image(str(thumb), width="stretch")
                with text_col:
                    url = f"https://youtube.com/watch?v={vid}"
                    st.markdown(f"### [{html.escape(str(row.get('title', 'Review video')))}]({url})")
                    st.caption(f"{row.get('content_format', 'Video')} · {row.get('channel', 'Unknown')} · {int(row.get('views', 0)):,} views · {int(row.get('comments', 0)):,} public comments")
                    description = compact(row.get("description", ""), 220) if valid_text(row.get("description", "")) else f'The public review is titled “{row.get("title", "Tamil film review")}”.'
                    st.markdown(f"**How the reviewer frames it:** {description}")
                    st.markdown(f"**How this video’s audience responds:** {audience_summary(audience)}")

    if not film_comments.empty:
        chart_col, reaction_col = st.columns([1.4, 1], gap="large")
        with chart_col:
            timeline = film_comments.assign(day=film_comments["created_at"].dt.floor("D")).groupby("day", as_index=False).size().rename(columns={"size": "Comments"})
            fig = px.area(timeline, x="day", y="Comments", color_discrete_sequence=["#ff4b2b"])
            fig.update_layout(height=350, xaxis_title="Published date", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(fig, width="stretch")
        with reaction_col:
            reactions = film_comments["reaction_signal"].value_counts().rename_axis("Reaction").reset_index(name="Comments")
            fig = px.pie(reactions, names="Reaction", values="Comments", hole=.58, color_discrete_sequence=PALETTE)
            fig.update_layout(height=350, legend_title=None, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")

comments, videos, meta = get_data("youtube-radar-v4")
videos = prep_videos(videos)
comments = prep_comments(comments, videos)
catalog_items = meta.get("movie_catalog_history") or meta.get("movie_catalog", [])
catalog = {item.get("title"): item for item in catalog_items if isinstance(item, dict)}

movie_param = st.query_params.get("movie")
if movie_param:
    render_movie_page(str(movie_param), comments, videos, meta, catalog)
    st.stop()

with st.sidebar:
    st.title("▶ Tamil Cinema Radar")
    st.caption("Scheduled every 30 minutes · actual timing is measured")
    if not comments.empty:
        all_films = sorted(set(comments["film"].dropna().astype(str)) | set(str(f) for f in meta.get("films", []) if f) | set(str(f) for f in meta.get("all_films_analyzed", []) if f))
        selected_films = st.multiselect("Films", all_films, default=all_films)
        selected_channels = st.multiselect("Channels", sorted(comments["channel"].dropna().unique()), default=sorted(comments["channel"].dropna().unique()))
        formats = [v for v in ["Video", "Short"] if v in set(comments["content_format"].dropna())]
        selected_formats = st.multiselect("Formats", formats, default=formats)
        window = st.select_slider("Analysis window", options=[6, 12, 24, 72, 168, 720, 2160], value=168, format_func=lambda h: f"{h} hours" if h < 24 else f"{h // 24} days" if h < 720 else f"{h // 720} months")
        min_likes = st.number_input("Minimum comment likes", min_value=0, value=0)
        include_noise = st.toggle("Include low-information reactions", value=False)
    st.divider()
    st.markdown("**Collection rhythm**")
    st.caption("Counters are scheduled every 30 minutes. New video discovery is daily. GitHub runner delays are measured and normalized.")
    if st.button("Refresh dashboard data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

st.markdown("""<div class="hero"><span class="kicker">TAMIL CINEMA · YOUTUBE INTELLIGENCE</span>
<h1>Reviews move fast.<br>The radar moves faster.</h1>
<p>A public-data dashboard for recent Tamil films: half-hour velocity, lifetime reach, reviewer coverage, language mix, discussion quality and audience questions without turning comments into a fake rating score.</p></div>""", unsafe_allow_html=True)

if comments.empty:
    st.warning("No YouTube comments are stored yet. Run the YouTube monitor once from GitHub Actions.")
    st.stop()

now = pd.Timestamp.now(tz="UTC")
cutoff = now - pd.Timedelta(hours=int(window))
filtered = comments[comments["film"].isin(selected_films) & comments["channel"].isin(selected_channels) & comments["content_format"].isin(selected_formats) & comments["created_at"].ge(cutoff) & comments["likes"].ge(min_likes)].copy()
if not include_noise:
    filtered = filtered[~filtered["low_information"]].copy()
if filtered.empty:
    st.info("No analyzed comments match the current filters.")
    st.stop()

latest_videos = latest_video_rows(videos[videos["film"].isin(selected_films)])
current_scan_time = videos["scanned_at"].max() if not videos.empty else pd.NaT
current_scan_videos = videos[videos["scanned_at"].eq(current_scan_time)].copy() if pd.notna(current_scan_time) else pd.DataFrame()
latest_growth = video_growth(videos[videos["film"].isin(selected_films)])
if not latest_growth.empty and pd.notna(current_scan_time):
    latest_growth = latest_growth[latest_growth["scanned_at"].eq(current_scan_time)].copy()
radar_films = list(dict.fromkeys(meta.get("films", [])))
all_analyzed_films = sorted(set(meta.get("all_films_analyzed", [])) | set(comments["film"].dropna().astype(str).unique()))
last_scan = pd.to_datetime(meta.get("last_scan"), errors="coerce", utc=True)
last_24 = filtered[filtered["created_at"].ge(now - pd.Timedelta(hours=24))]
actively_fetched_films = set(current_scan_videos["film"].dropna().astype(str)) if not current_scan_videos.empty else set()
latest_by_film = latest_videos.groupby("film", as_index=False).agg(
    public_views=("views", "sum"),
    public_comments=("comments", "sum"),
    videos=("video_id", lambda values: latest_videos.loc[values.index, "content_format"].eq("Video").sum()),
    shorts=("video_id", lambda values: latest_videos.loc[values.index, "content_format"].eq("Short").sum()),
) if not latest_videos.empty else pd.DataFrame(columns=["film", "public_views", "public_comments", "videos", "shorts"])
comment_summary = comments.groupby("film", as_index=False).agg(
    collected_comments=("source_id", "nunique"),
    channels=("channel", "nunique"),
    latest_comment=("created_at", "max"),
)
missing_films = sorted(set(all_analyzed_films) - set(comment_summary["film"]))
if missing_films:
    comment_summary = pd.concat(
        [comment_summary, pd.DataFrame({"film": missing_films, "collected_comments": 0, "channels": 0})],
        ignore_index=True,
    )
film_list = comment_summary.merge(latest_by_film, on="film", how="outer").fillna(
    {"collected_comments": 0, "channels": 0, "public_views": 0, "public_comments": 0, "videos": 0, "shorts": 0}
)
if not latest_growth.empty:
    film_velocity = latest_growth.groupby("film", as_index=False).agg(
        views_per_30m=("views_per_30m", "sum"),
        comments_per_30m=("comments_per_30m", "sum"),
        views_gained=("views_gained", "sum"),
        comments_gained=("comments_gained", "sum"),
    )
    film_list = film_list.merge(film_velocity, on="film", how="left")
else:
    for column in ["views_per_30m", "comments_per_30m", "views_gained", "comments_gained"]:
        film_list[column] = 0
for column in ["public_views", "public_comments", "videos", "shorts", "views_per_30m", "comments_per_30m", "views_gained", "comments_gained"]:
    film_list[column] = pd.to_numeric(film_list.get(column, 0), errors="coerce").fillna(0)
film_list["status"] = film_list["film"].map(
    lambda f: "Fetched in latest monitor"
    if f in actively_fetched_films else
    "Scheduled, awaiting matched videos"
    if f in radar_films else
    "Historical archive"
)
film_list["release_date"] = film_list["film"].map(lambda f: catalog.get(f, {}).get("release_date") or "Unavailable")
poster_rows = []
latest_for_poster = latest_video_rows(videos)
for film in film_list["film"].dropna().astype(str):
    poster, source = poster_for(film, catalog, latest_for_poster)
    poster_rows.append((film, poster, source))
poster_frame = pd.DataFrame(poster_rows, columns=["film", "poster_url", "poster_source"])
film_list = film_list.merge(poster_frame, on="film", how="left")
rank = {"Fetched in latest monitor": 0, "Scheduled, awaiting matched videos": 1, "Historical archive": 2}
film_list["_rank"] = film_list["status"].map(rank).fillna(3)
film_list = film_list.sort_values(["_rank", "views_per_30m", "public_views", "collected_comments"], ascending=[True, False, False, False])

metrics = st.columns(8)
metrics[0].metric("Films analyzed ever", len(all_analyzed_films))
metrics[1].metric("Films scheduled now", len(radar_films))
metrics[2].metric("Films fetched latest", len(actively_fetched_films))
metrics[3].metric("Current videos", int(current_scan_videos["content_format"].eq("Video").sum()) if not current_scan_videos.empty else 0)
metrics[4].metric("Current Shorts", int(current_scan_videos["content_format"].eq("Short").sum()) if not current_scan_videos.empty else 0)
metrics[5].metric("Comments collected ever", f"{len(comments):,}", help="Unique comment rows stored by the radar, not YouTube's public total.")
metrics[6].metric("New comments · 24 h", f"{len(last_24):,}")
metrics[7].metric("Last monitor", last_scan.strftime("%d %b · %H:%M UTC") if pd.notna(last_scan) else "Pending")

scan_times = pd.Series(sorted(videos["scanned_at"].dropna().unique())) if not videos.empty else pd.Series(dtype="datetime64[ns, UTC]")
last_gap = scan_times.diff().dt.total_seconds().div(60).dropna().iloc[-1] if len(scan_times) >= 2 else float("nan")
last_age = (now - current_scan_time).total_seconds() / 60 if pd.notna(current_scan_time) else float("nan")
health = "Current" if pd.notna(current_scan_time) and last_age <= 75 else "Delayed" if pd.notna(current_scan_time) else "Waiting"
health_note = f"Last snapshot {last_age:.0f} min old; previous gap {last_gap:.0f} min." if pd.notna(current_scan_time) and pd.notna(last_gap) else "Waiting for at least two snapshots."

st.subheader("What changed in the latest monitor?")
st.markdown('<div class="section-note">Exact gains are calculated against the previous successful scan. Rates are normalized to 30 minutes so delayed GitHub runs remain comparable.</div>', unsafe_allow_html=True)
change_cols = st.columns(6)
with change_cols[0]:
    card("Scan health", health, health_note)
if latest_growth.empty:
    for col, label in zip(change_cols[1:], ["Views", "Comments", "Channel", "Video", "Short"]):
        with col:
            card(label, "Pending", "Needs two stored snapshots for the same video.")
else:
    film_growth = latest_growth.groupby("film", as_index=False).agg(views_gained=("views_gained", "sum"), comments_gained=("comments_gained", "sum"), views_per_30m=("views_per_30m", "sum"), comments_per_30m=("comments_per_30m", "sum"))
    top_view = film_growth.sort_values("views_per_30m", ascending=False).iloc[0]
    top_comment = film_growth.sort_values("comments_per_30m", ascending=False).iloc[0]
    channel_growth = latest_growth.groupby("channel", as_index=False).agg(comments_gained=("comments_gained", "sum"), views_gained=("views_gained", "sum")).sort_values(["comments_gained", "views_gained"], ascending=False)
    with change_cols[1]:
        card("Fastest film by views", top_view["film"], f"+{top_view['views_gained']:,.0f} exact views; {top_view['views_per_30m']:,.0f} / 30 min.")
    with change_cols[2]:
        card("Fastest film by comments", top_comment["film"], f"+{top_comment['comments_gained']:,.0f} exact comments; {top_comment['comments_per_30m']:,.1f} / 30 min.")
    with change_cols[3]:
        row = channel_growth.iloc[0]
        card("Most active channel", compact(row.get("channel"), 42), f"+{row.get('comments_gained', 0):,.0f} comments and +{row.get('views_gained', 0):,.0f} views.")
    for col, fmt, label in [(change_cols[4], "Video", "Top standard video"), (change_cols[5], "Short", "Top Short")]:
        with col:
            ranked = latest_growth[latest_growth["content_format"].eq(fmt)].sort_values("views_per_30m", ascending=False)
            if ranked.empty:
                card(label, "Pending", f"No {fmt.lower()} pair in latest archive.")
            else:
                row = ranked.iloc[0]
                card(label, compact(row.get("film"), 36), f"{compact(row.get('title'), 58)} · +{row['views_gained']:,.0f} views.")

radar_list = film_list[film_list["film"].isin(radar_films)]
archive_list = film_list[~film_list["film"].isin(radar_films)]
list_tab, archive_tab, table_tab = st.tabs(["Poster list · current radar", "Poster list · full archive", "Raw film table"])
with list_tab:
    render_film_list(
        radar_list,
        "Movies currently monitored",
        "Every row opens a film page. Posters are from TMDB when available; YouTube thumbnails are used only as fallback.",
    )
with archive_tab:
    render_film_list(
        film_list,
        "All movies analyzed and stored",
        "This includes active films and historical archive films kept in Git CSV data.",
    )
with table_tab:
    table = film_list.rename(columns={
        "film": "Film",
        "status": "Status",
        "release_date": "Release date",
        "collected_comments": "Stored comments",
        "public_comments": "Public comments",
        "public_views": "Public views",
        "views_per_30m": "Views / 30 min",
        "comments_per_30m": "Comments / 30 min",
        "poster_source": "Poster source",
    })
    st.dataframe(
        table[["Film", "Status", "Release date", "Stored comments", "Public comments", "Public views", "videos", "shorts", "Views / 30 min", "Comments / 30 min", "Poster source", "latest_comment"]],
        hide_index=True,
        width="stretch",
        column_config={"latest_comment": st.column_config.DatetimeColumn("Latest published comment", format="DD MMM YYYY")},
    )

tab_live, tab_lifetime, tab_film, tab_comments, tab_data = st.tabs(["30-minute live", "Lifetime analysis", "Film deep dive", "Comment explorer", "Data archive"])

with tab_live:
    st.subheader("Live collection and 30-minute trend")
    monitored = pd.DataFrame()
    activity = pd.DataFrame()
    if not videos.empty:
        raw = videos.sort_values(["video_id", "scanned_at"]).copy()
        monitored = raw.copy()
        monitored["previous_scan"] = monitored.groupby("video_id")["scanned_at"].shift(1)
        monitored["previous_views"] = monitored.groupby("video_id")["views"].shift(1)
        monitored["previous_comments"] = monitored.groupby("video_id")["comments"].shift(1)
        monitored["elapsed_minutes"] = (monitored["scanned_at"] - monitored["previous_scan"]).dt.total_seconds().div(60)
        monitored["views_gained"] = (monitored["views"] - monitored["previous_views"]).clip(lower=0)
        monitored["comments_gained"] = (monitored["comments"] - monitored["previous_comments"]).clip(lower=0)
        valid_elapsed = monitored["elapsed_minutes"].where(monitored["elapsed_minutes"].gt(0))
        monitored["views_per_30m"] = monitored["views_gained"] * 30 / valid_elapsed
        monitored["comments_per_30m"] = monitored["comments_gained"] * 30 / valid_elapsed
        recent_raw = raw[raw["scanned_at"].ge(now - pd.Timedelta(hours=24))].copy()
        fetched = recent_raw.groupby(["scanned_at", "film", "content_format"], as_index=False).agg(videos_fetched=("video_id", "nunique"))
        deltas = monitored[monitored["previous_scan"].notna() & monitored["scanned_at"].ge(now - pd.Timedelta(hours=24))].groupby(["scanned_at", "film", "content_format"], as_index=False).agg(views_gained=("views_gained", "sum"), comments_gained=("comments_gained", "sum"), views_per_30m=("views_per_30m", "sum"), comments_per_30m=("comments_per_30m", "sum"), elapsed_minutes=("elapsed_minutes", "median"))
        activity = fetched.merge(deltas, on=["scanned_at", "film", "content_format"], how="left").fillna(0).rename(columns={"scanned_at": "period"})
    if activity.empty:
        st.warning("No snapshot rows exist in the last 24 hours. The scanner may have run without persisting counters.")
    else:
        scan_history = activity.groupby("period", as_index=False).agg(videos_fetched=("videos_fetched", "sum"), views_gained=("views_gained", "sum"), comments_gained=("comments_gained", "sum"), views_per_30m=("views_per_30m", "sum"), comments_per_30m=("comments_per_30m", "sum"), elapsed_minutes=("elapsed_minutes", "median")).sort_values("period", ascending=False)
        newest = scan_history.iloc[0]
        cadence = pd.Series(sorted(activity["period"].dropna().unique())).diff().dt.total_seconds().div(60).dropna()
        cols = st.columns(6)
        cols[0].metric("Latest videos fetched", f"{int(newest['videos_fetched']):,}")
        cols[1].metric("Exact views since prior", f"{int(newest['views_gained']):,}")
        cols[2].metric("Exact comments since prior", f"{int(newest['comments_gained']):,}")
        cols[3].metric("Stored runs · 24 h", f"{activity['period'].nunique():,}")
        cols[4].metric("Median cadence", f"{cadence.median():.0f} min" if not cadence.empty else "Pending")
        cols[5].metric("Archive freshness", "Current" if pd.notna(current_scan_time) and last_age <= 75 else f"{last_age:.0f} min old")
        st.info("The dashboard keeps exact delayed-run gains and also shows normalized 30-minute rates. This avoids pretending GitHub Actions always starts exactly on time.")
        coverage_tab, views_tab, comments_tab, timing_tab = st.tabs(["Fetch coverage", "View trend / 30 min", "Comment trend / 30 min", "Scan timing"])
        def live_chart(value: str, label: str):
            fig = px.bar(activity, x="period", y=value, color="film", facet_row="content_format", color_discrete_sequence=PALETTE, labels={"period": "Monitor time · UTC", value: label})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            fig.update_layout(height=590, barmode="stack", hovermode="x unified", legend_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            return fig
        with coverage_tab:
            st.plotly_chart(live_chart("videos_fetched", "Videos and Shorts fetched"), width="stretch")
        with views_tab:
            st.plotly_chart(live_chart("views_per_30m", "Views per 30 minutes"), width="stretch")
        with comments_tab:
            st.plotly_chart(live_chart("comments_per_30m", "Comments per 30 minutes"), width="stretch")
        with timing_tab:
            fig = px.line(scan_history.sort_values("period"), x="period", y="elapsed_minutes", markers=True, labels={"period": "Completed run · UTC", "elapsed_minutes": "Minutes since prior run"}, color_discrete_sequence=["#8338ec"])
            fig.add_hline(y=30, line_dash="dash", line_color="#ff4b2b", annotation_text="30-minute target")
            fig.update_layout(height=430, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(fig, width="stretch")
        with st.expander("Exactly what the latest monitor fetched"):
            latest_time = videos["scanned_at"].max()
            latest_items = videos[videos["scanned_at"].eq(latest_time)].merge(monitored[monitored["scanned_at"].eq(latest_time)][["video_id", "views_gained", "comments_gained", "elapsed_minutes", "views_per_30m"]], on="video_id", how="left")
            st.dataframe(latest_items[["film", "content_format", "channel", "title", "views", "comments", "views_gained", "comments_gained", "elapsed_minutes", "views_per_30m"]].sort_values("views_per_30m", ascending=False), hide_index=True, width="stretch")

    st.subheader("Which videos are gaining attention now?")
    growth = video_growth(videos)
    def gain_chart(format_name: str):
        ranked = growth[growth["content_format"].eq(format_name)].sort_values("views_per_30m", ascending=False).head(15) if not growth.empty else pd.DataFrame()
        if ranked.empty:
            st.info(f"Waiting for two snapshots of {format_name.lower()}s.")
            return
        ranked["Label"] = ranked.apply(lambda r: f"{r['channel']} · {compact(r['title'], 58)}", axis=1)
        fig = px.bar(ranked.sort_values("views_per_30m"), x="views_per_30m", y="Label", color="film", orientation="h", text="views_per_30m", color_discrete_sequence=PALETTE, hover_data=["elapsed_minutes", "views_gained", "comments_gained"])
        fig.update_traces(texttemplate="+%{text:,.0f}", textposition="outside")
        fig.update_layout(height=max(400, len(ranked) * 44), legend_title=None, xaxis_title="Normalized new views / 30 min", yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")
    video_tab, short_tab = st.tabs(["Standard videos", "Shorts"])
    with video_tab:
        gain_chart("Video")
    with short_tab:
        gain_chart("Short")

    st.subheader("Inside Tamil YouTube comments")
    ecosystem = comments.copy()
    ecosystem["normalized_text"] = ecosystem["text"].map(normalize_text)
    repetitions = ecosystem.loc[ecosystem["normalized_text"].str.len().ge(12), "normalized_text"].value_counts()
    repeated = set(repetitions[repetitions.ge(3)].index)
    ecosystem["exact_repeat"] = ecosystem["normalized_text"].isin(repeated)
    ecosystem["promotional"] = ecosystem["normalized_text"].str.contains(PROMO_RE, na=False)
    ecosystem["emoji_only"] = ecosystem["normalized_text"].map(lambda t: not bool(re.search(r"[a-z0-9\u0B80-\u0BFF]", t)))
    ecosystem["one_word"] = ecosystem["word_count"].le(1) & ~ecosystem["emoji_only"]
    ecosystem["context_signals"] = ecosystem["normalized_text"].map(classify_context)
    ecosystem["sarcasm_signals"] = ecosystem["normalized_text"].map(sarcasm_cues)
    ecosystem["possible_sarcasm"] = ecosystem["sarcasm_signals"].map(bool)
    ecosystem["gives_reason"] = ecosystem["normalized_text"].str.contains(r"because|therefore|however|although|reason|ஆனால்|ஆனா|ஏனெனில்|காரணம்|அதனால்|karanam", regex=True, na=False)
    ecosystem["specific_aspect"] = ~ecosystem["topic"].eq("General reaction")
    ecosystem["Value class"] = "General opinion"
    ecosystem.loc[ecosystem["is_question"], "Value class"] = "Useful question"
    ecosystem.loc[ecosystem["word_count"].ge(8) & (ecosystem["specific_aspect"] | ecosystem["gives_reason"]), "Value class"] = "Reasoned film opinion"
    ecosystem.loc[ecosystem["word_count"].ge(15) & (ecosystem["specific_aspect"] | ecosystem["gives_reason"]), "Value class"] = "Deep critical analysis"
    ecosystem.loc[ecosystem["context_signals"].map(bool) & ecosystem["word_count"].ge(6), "Value class"] = "Cultural / historical connection"
    ecosystem.loc[ecosystem["word_count"].between(2, 5), "Value class"] = "Brief reaction"
    ecosystem.loc[ecosystem["one_word"], "Value class"] = "One-word reaction"
    ecosystem.loc[ecosystem["emoji_only"], "Value class"] = "Emoji-only"
    ecosystem.loc[ecosystem["promotional"], "Value class"] = "Promotional / link spam"
    ecosystem.loc[ecosystem["exact_repeat"], "Value class"] = "Repeated / copied text"
    value_classes = ["Useful question", "Reasoned film opinion", "Deep critical analysis", "Cultural / historical connection"]
    value_adding = ecosystem["Value class"].isin(value_classes)
    meaningful = ~ecosystem["Value class"].isin(["Emoji-only", "One-word reaction", "Promotional / link spam", "Repeated / copied text"])
    cols = st.columns(7)
    cols[0].metric("Comments studied", f"{len(ecosystem):,}")
    cols[1].metric("Adds analytical value", f"{value_adding.mean():.1%}")
    cols[2].metric("Deep analysis", f"{ecosystem['Value class'].eq('Deep critical analysis').mean():.1%}")
    cols[3].metric("Useful questions", f"{ecosystem['Value class'].eq('Useful question').mean():.1%}")
    cols[4].metric("Cultural context", f"{ecosystem['context_signals'].map(bool).mean():.1%}")
    cols[5].metric("Possible sarcasm", f"{ecosystem['possible_sarcasm'].mean():.1%}")
    cols[6].metric("Filtered/noise", f"{(~meaningful).mean():.1%}")
    st.info(f"{value_adding.mean():.1%} of collected comments add identifiable analytical value through a reason, film-specific aspect, substantive question or cultural comparison. Possible sarcasm is cue-based and should be read as a candidate, not a fact about intent.")
    left, right = st.columns(2, gap="large")
    with left:
        participation = ecosystem["Value class"].value_counts().rename_axis("Participation").reset_index(name="Comments")
        participation["Share"] = participation["Comments"] / len(ecosystem) * 100
        fig = px.bar(participation.sort_values("Share"), x="Share", y="Participation", orientation="h", text="Comments", color="Participation", color_discrete_sequence=PALETTE)
        fig.update_traces(texttemplate="%{x:.1f}% · %{text:,}", textposition="outside")
        fig.update_layout(height=430, showlegend=False, xaxis_title="Share of all collected comments (%)", yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")
    with right:
        language = ecosystem.groupby(["language", "Value class"], as_index=False).size().rename(columns={"Value class": "Participation", "size": "Comments"})
        language["Share"] = language["Comments"] / language.groupby("language")["Comments"].transform("sum") * 100
        fig = px.bar(language, x="language", y="Share", color="Participation", barmode="stack", custom_data=["Comments"], color_discrete_sequence=PALETTE)
        fig.update_layout(height=430, legend_title=None, xaxis_title=None, yaxis_title="Within-language share (%)", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")
    st.markdown("#### Comments that add analytical value")
    examples = ecosystem[value_adding].copy()
    examples["Why highlighted"] = examples.apply(lambda r: "question" if r["is_question"] else "; ".join(r["context_signals"]) or str(r["topic"]), axis=1)
    examples["Comment"] = examples["text"].astype(str).str.slice(0, 320)
    st.dataframe(examples.sort_values(["likes", "word_count"], ascending=False).head(15)[["film", "channel", "Value class", "reaction_signal", "Why highlighted", "Comment", "likes", "url"]], hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("Open")})
    context_tab, sarcasm_tab = st.tabs(["Historical/contemporary connections", "Possible sarcasm/comedy cues"])
    with context_tab:
        context_examples = ecosystem[ecosystem["context_signals"].map(bool) & meaningful].copy()
        context_examples["Connection"] = context_examples["context_signals"].map(lambda v: ", ".join(v))
        context_examples["Comment"] = context_examples["text"].astype(str).str.slice(0, 320)
        st.dataframe(context_examples.sort_values(["likes", "word_count"], ascending=False).head(15)[["film", "Connection", "topic", "Comment", "likes", "url"]], hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("Open")})
    with sarcasm_tab:
        sarcasm_examples = ecosystem[ecosystem["possible_sarcasm"] & meaningful & ecosystem["word_count"].ge(3)].copy()
        sarcasm_examples["Observed cues"] = sarcasm_examples["sarcasm_signals"].map(lambda v: ", ".join(v))
        sarcasm_examples["Comment"] = sarcasm_examples["text"].astype(str).str.slice(0, 320)
        st.warning("These are candidates for human reading. Tamil/Tanglish sarcasm cannot be proven from text cues alone.")
        st.dataframe(sarcasm_examples.sort_values(["likes", "word_count"], ascending=False).head(15)[["film", "Observed cues", "reaction_signal", "Comment", "likes", "url"]], hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("Open")})
    terms = top_terms(ecosystem.loc[meaningful, "text"], 20)
    if not terms.empty:
        fig = px.bar(terms.sort_values("mentions"), x="mentions", y="term", orientation="h", color="mentions", color_continuous_scale=["#9bdaf5", "#480ca8"])
        fig.update_layout(height=500, coloraxis_showscale=False, xaxis_title="Mentions across corpus", yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")
    with st.expander("Definitions and research basis"):
        st.markdown("Tamil YouTube comments mix Tamil script, romanized Tamil, English, emoji and spelling variants. This dashboard uses transparent rules and corpus statistics rather than claiming a perfect classifier. Useful references: [DravidianCodeMix](https://github.com/bharathichezhiyan/DravidianCodeMix-Dataset), [Tamil-English corpus](https://arxiv.org/abs/2006.00206), [AI4Bharat Indic NLP](https://github.com/AI4Bharat/indicnlp_catalog), and [Tamil-English sarcasm research](https://arxiv.org/abs/2411.05039).")

with tab_lifetime:
    st.subheader("Lifetime public totals and observed growth")
    latest = latest_video_rows(videos)
    pairs = video_growth(videos)
    public_comments = float(latest["comments"].sum()) if not latest.empty else 0
    coverage = len(comments) / public_comments if public_comments else 0
    cols = st.columns(7)
    cols[0].metric("Current public views", f"{latest['views'].sum():,.0f}" if not latest.empty else "0")
    cols[1].metric("Current public comments", f"{public_comments:,.0f}")
    cols[2].metric("Unique comments collected", f"{len(comments):,}", delta=f"{coverage:.1%} of public counter")
    cols[3].metric("Videos + Shorts", f"{latest['video_id'].nunique():,}" if not latest.empty else "0")
    cols[4].metric("Snapshot rows", f"{len(videos):,}")
    cols[5].metric("Distinct monitor runs", f"{videos['scanned_at'].nunique():,}" if not videos.empty else "0")
    span = videos["scanned_at"].max() - videos["scanned_at"].min() if not videos.empty else pd.NaT
    cols[6].metric("Monitoring span", f"{max(1, span.days + 1)} days" if pd.notna(span) else "Pending")
    st.info("Public comments are YouTube's lifetime counters. Collected comments are individual recent top-level comments actually returned and deduplicated by the scanner.")
    if not pairs.empty:
        pairs["period"] = pairs["scanned_at"].dt.floor("30min")
        history = pairs.groupby("period", as_index=False).agg(views_gained=("views_gained", "sum"), comments_gained=("comments_gained", "sum"), elapsed_minutes=("elapsed_minutes", "median"))
        history["cumulative_views"] = history["views_gained"].cumsum()
        history["cumulative_comments"] = history["comments_gained"].cumsum()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history["period"], y=history["cumulative_views"], name="Observed view growth", mode="lines", fill="tozeroy", line=dict(color="#ff4b2b", width=3)))
        fig.add_trace(go.Scatter(x=history["period"], y=history["cumulative_comments"], name="Observed comment growth", mode="lines", yaxis="y2", line=dict(color="#3a86ff", width=3)))
        fig.update_layout(height=430, hovermode="x unified", legend=dict(orientation="h", y=1.12), yaxis=dict(title="Views gained since monitoring began"), yaxis2=dict(title="Comments gained", overlaying="y", side="right", showgrid=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")
        left, right = st.columns(2, gap="large")
        with left:
            recent = history[history["elapsed_minutes"].between(20, 70)].tail(96)
            fig = px.bar(recent, x="period", y="views_gained", color="views_gained", color_continuous_scale=["#ffd8ce", "#ff4b2b", "#8f1d08"])
            fig.update_layout(height=400, coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(fig, width="stretch")
        with right:
            daily = pairs.assign(day=pairs["scanned_at"].dt.floor("D")).groupby(["day", "film"], as_index=False)["views_gained"].sum()
            fig = px.area(daily, x="day", y="views_gained", color="film", color_discrete_sequence=PALETTE)
            fig.update_layout(height=400, hovermode="x unified", legend_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
            st.plotly_chart(fig, width="stretch")
    if not latest.empty:
        reach = latest.groupby("film", as_index=False).agg(public_views=("views", "sum"), public_comments=("comments", "sum"), videos=("video_id", "nunique"))
        fig = px.scatter(reach, x="public_views", y="public_comments", size="videos", color="film", text="film", color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="top center")
        fig.update_layout(height=470, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,.45)")
        st.plotly_chart(fig, width="stretch")

with tab_film:
    film = st.selectbox("Choose a film", selected_films)
    render_movie_page(film, filtered, videos, meta, catalog)

with tab_comments:
    st.subheader("Comment explorer")
    cols = st.columns(4)
    cols[0].metric("Included comments", f"{(~comments['low_information']).sum():,}")
    cols[1].metric("Low-information filtered", f"{comments['low_information'].sum():,}")
    cols[2].metric("Questions detected", f"{filtered['is_question'].sum():,}")
    cols[3].metric("Median words", f"{filtered['word_count'].median():.0f}")
    search = st.text_input("Search comment text")
    explorer = filtered.copy()
    if search:
        explorer = explorer[explorer["text"].str.contains(search, case=False, na=False, regex=False)]
    columns = ["film", "content_format", "channel", "video_title", "language", "topic", "comment_kind", "text", "likes", "reply_count", "created_at", "url"]
    st.dataframe(explorer[columns].sort_values(["likes", "created_at"], ascending=[False, False]), hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("Open on YouTube"), "created_at": st.column_config.DatetimeColumn("Published", format="DD MMM YYYY, HH:mm")})
    st.download_button("Download analyzed YouTube comments", explorer[columns].to_csv(index=False), "tamil-cinema-youtube-comments.csv", "text/csv")

with tab_data:
    st.subheader("Complete data archive")
    pairs = video_growth(videos)
    if not pairs.empty:
        pairs["period"] = pairs["scanned_at"].dt.floor("30min")
        interval_history = pairs.groupby("period", as_index=False).agg(views_gained=("views_gained", "sum"), comments_gained=("comments_gained", "sum"), videos_reporting=("video_id", "nunique"), elapsed_minutes=("elapsed_minutes", "median"))
    else:
        interval_history = pd.DataFrame()
    cols = st.columns(4)
    cols[0].metric("Snapshot rows", f"{len(videos):,}")
    cols[1].metric("Half-hour intervals", f"{len(interval_history):,}")
    cols[2].metric("Comment rows", f"{len(comments):,}")
    cols[3].metric("Retention", f"{meta.get('keep_history_days', 730)} days")
    dl = st.columns(4)
    dl[0].download_button("Download raw snapshots", videos.to_csv(index=False), "cinema-wall-video-snapshots.csv", "text/csv", width="stretch")
    dl[1].download_button("Download 30-min series", interval_history.to_csv(index=False), "cinema-wall-30-minute-timeseries.csv", "text/csv", width="stretch", disabled=interval_history.empty)
    dl[2].download_button("Download all comments", comments.to_csv(index=False), "cinema-wall-all-comments.csv", "text/csv", width="stretch")
    dl[3].download_button("Download scan metadata", json.dumps(meta, indent=2, ensure_ascii=False), "cinema-wall-scan-metadata.json", "application/json", width="stretch")
    dataset = st.radio("Preview dataset", ["30-minute time series", "Raw video snapshots", "Collected comments"], horizontal=True)
    preview = interval_history.sort_values("period", ascending=False) if dataset == "30-minute time series" else videos.sort_values("scanned_at", ascending=False) if dataset == "Raw video snapshots" else comments.sort_values("created_at", ascending=False)
    st.dataframe(preview.head(2000), hide_index=True, width="stretch")

with st.expander("Monitor health and methodology"):
    st.write(f"Status: **{meta.get('status', 'unknown')}**")
    st.write(f"Schedule: every **{meta.get('scan_interval_minutes', 30)} minutes**")
    st.write(f"New-video discovery: every **{meta.get('video_discovery_hours', 24)} hours**")
    st.write("Collectors: " + ", ".join(meta.get("collectors", ["YouTube Data API"])))
    errors = meta.get("errors", [])
    if errors:
        st.warning(f"{len(errors)} source warnings occurred in the latest monitor run.")
        st.code("\n".join(errors), language=None)

st.caption("Tamil Cinema YouTube Radar · Public YouTube data · Activity signals are not audience size, film quality or box-office estimates.")
