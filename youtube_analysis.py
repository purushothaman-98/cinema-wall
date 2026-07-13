"""Transparent YouTube comment processing for Tamil cinema."""
from __future__ import annotations

from collections import Counter
import re
import pandas as pd

TANGLISH = {
    "padam", "padathula", "kadhai", "sema", "semma", "nalla", "romba", "mass",
    "mokka", "pudichu", "pudichiruku", "pudikala", "vera", "level", "sambavam",
    "nadippu", "paattu", "bgm", "thalaiva", "bro", "anna", "superu", "vaazhthukkal",
}
STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "was", "are", "this", "that", "it", "to",
    "of", "in", "on", "for", "with", "movie", "film", "video", "review", "tamil",
    "very", "so", "too", "i", "we", "you", "he", "she", "they", "my", "our", "your",
    "bro", "anna", "sir", "please", "from", "at", "be", "have", "has", "had", "but",
    "good", "love", "super", "time", "feel", "scene", "watch", "waiting", "half", "than",
    "like", "really", "also", "just", "only", "all", "get", "got", "will", "can", "could",
    "ஒரு", "இந்த", "அந்த", "என்று", "மற்றும்", "படம்", "நல்ல", "ரொம்ப",
}
TOPICS = {
    "Story & screenplay": ["story", "plot", "screenplay", "writing", "kadhai", "கதை", "திரைக்கதை"],
    "Acting & characters": ["acting", "performance", "actor", "hero", "heroine", "character", "nadippu", "நடிப்பு"],
    "Direction & making": ["direction", "director", "making", "iyakkam", "இயக்கம்"],
    "Music & sound": ["music", "bgm", "song", "songs", "paattu", "isai", "இசை", "பாட்டு"],
    "Visuals & craft": ["visual", "cinematography", "camera", "vfx", "editing", "colour", "ஒளிப்பதிவு"],
    "Pacing & runtime": ["pace", "pacing", "lag", "drag", "slow", "length", "runtime", "second half", "first half"],
    "Comedy": ["comedy", "funny", "humour", "humor", "sirippu", "காமெடி", "சிரிப்பு"],
    "Emotion": ["emotion", "emotional", "feel", "heart", "sentiment", "கண்ணீர்", "உணர்வு"],
    "Release & theatre": ["release", "theatre", "theater", "ott", "ticket", "show", "collection", "box office"],
}
APPRECIATION = {
    "good", "great", "excellent", "amazing", "awesome", "best", "super", "mass",
    "sema", "semma", "nalla", "vera level", "worth", "loved", "love", "beautiful",
    "engaging", "blockbuster", "sambavam", "arுமை", "அருமை", "நல்ல", "சூப்பர்", "செம",
}
CRITICISM = {
    "bad", "worst", "boring", "bore", "mokka", "mokke", "waste", "cringe", "lag",
    "drag", "slow", "weak", "disappointed", "flop", "average", "overrated",
    "மோசம்", "மொக்க", "போர்", "சுமார்", "பிடிக்கல",
}
PROMO_PATTERNS = [
    r"https?://", r"subscribe", r"my channel", r"follow me", r"full movie link",
    r"telegram", r"whatsapp", r"earn money", r"giveaway",
]

def normalize_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"(.)\1{4,}", r"\1\1", text)
    return re.sub(r"\s+", " ", text).strip()

def detect_language(text: str) -> str:
    tamil_chars = len(re.findall(r"[\u0B80-\u0BFF]", text))
    latin_words = set(re.findall(r"[a-z]+", text))
    if tamil_chars and latin_words:
        return "Tamil + English"
    if tamil_chars:
        return "Tamil"
    if latin_words & TANGLISH:
        return "Tanglish"
    return "English / other"

def detect_topic(text: str) -> str:
    scores = {
        topic: sum(1 for term in terms if term in text)
        for topic, terms in TOPICS.items()
    }
    topic, score = max(scores.items(), key=lambda item: item[1])
    return topic if score else "General reaction"

def reaction_signal(text: str) -> str:
    positive = sum(1 for term in APPRECIATION if term in text)
    negative = sum(1 for term in CRITICISM if term in text)
    if positive > negative:
        return "Appreciative"
    if negative > positive:
        return "Critical"
    return "Mixed / unclear"

def comment_kind(text: str, word_count: int) -> str:
    if "?" in text or re.search(r"\b(why|what|when|where|who|how|enna|eppo|yen|என்ன|ஏன்|எப்போது)\b", text):
        return "Question"
    if word_count >= 18:
        return "Detailed discussion"
    if word_count >= 6:
        return "Short opinion"
    return "Quick reaction"

def enrich_comments(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["text"] = result["text"].fillna("").astype(str)
    clean = result["text"].map(normalize_text)
    result["word_count"] = clean.map(lambda value: len(re.findall(r"[\w\u0B80-\u0BFF'-]+", value)))
    result["language"] = clean.map(detect_language)
    result["topic"] = clean.map(detect_topic)
    result["reaction_signal"] = clean.map(reaction_signal)
    result["comment_kind"] = [
        comment_kind(text, int(words)) for text, words in zip(clean, result["word_count"])
    ]
    result["is_question"] = result["comment_kind"].eq("Question")
    promo = clean.map(lambda value: any(re.search(pattern, value) for pattern in PROMO_PATTERNS))
    repeated = clean.str.replace(r"[^\w\u0B80-\u0BFF]", "", regex=True).str.len().lt(3)
    result["low_information"] = result["word_count"].lt(3) | repeated | promo
    result["analysis_status"] = result["low_information"].map(
        {True: "Filtered as low-information", False: "Included in analysis"}
    )
    return result

def top_terms(texts: pd.Series, limit: int = 18) -> pd.DataFrame:
    counter = Counter()
    for value in texts.fillna("").map(normalize_text):
        words = re.findall(r"[a-z]{3,}|[\u0B80-\u0BFF]{2,}", value)
        counter.update(word for word in words if word not in STOPWORDS)
    return pd.DataFrame(counter.most_common(limit), columns=["term", "mentions"])
