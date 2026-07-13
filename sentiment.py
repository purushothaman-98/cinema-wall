"""Transparent Tamil/Tanglish/English sentiment baseline."""
from __future__ import annotations

import math
import re

POSITIVE = {
    "masterpiece": 3.0, "vera level": 2.8, "வேற லெவல்": 2.8,
    "sema": 2.2, "செம": 2.2, "mass": 1.8, "மாஸ்": 1.8,
    "super": 1.8, "சூப்பர்": 1.8, "excellent": 2.5, "amazing": 2.3,
    "good": 1.4, "நல்ல": 1.4, "worth": 1.5, "goosebumps": 2.2,
    "emotional": 1.5, "engaging": 1.8, "blockbuster": 2.2,
    "fire": 1.8, "banger": 1.8, "love": 1.7, "பிடிச்சிருக்கு": 1.8,
    "sambavam": 2.5, "சம்பவம்": 2.5, "comeback": 1.6,
}

NEGATIVE = {
    "worst": -3.0, "waste": -2.5, "மோசம்": -2.6, "mokke": -2.3,
    "மொக்க": -2.3, "boring": -2.1, "போர்": -2.0, "cringe": -2.4,
    "lag": -1.8, "drag": -1.8, "slow": -1.2, "disappointed": -2.0,
    "weak": -1.6, "headache": -2.3, "torture": -2.8, "logicless": -1.8,
    "outdated": -1.7, "flop": -2.1, "bad": -1.7, "பிடிக்கல": -2.0,
}

NEGATIONS = ("not ", "no ", "never ", "illa ", "இல்ல ", "இல்லை ")


def score_text(text: str) -> tuple[float, str]:
    clean = re.sub(r"\s+", " ", str(text).lower()).strip()
    raw = 0.0
    hits = 0
    for phrase, weight in {**POSITIVE, **NEGATIVE}.items():
        if phrase not in clean:
            continue
        position = clean.find(phrase)
        context = clean[max(0, position - 12):position]
        if any(context.endswith(neg.strip()) or neg in context for neg in NEGATIONS):
            weight *= -0.75
        raw += weight
        hits += 1
    raw += min(clean.count("🔥") + clean.count("❤️") + clean.count("👏"), 3) * 0.7
    raw -= min(clean.count("🤮") + clean.count("👎") + clean.count("😴"), 3) * 0.8
    if hits == 0 and raw == 0:
        return 50.0, "Neutral"
    score = 50 + 50 * math.tanh(raw / 4.5)
    label = "Positive" if score >= 60 else "Negative" if score <= 40 else "Neutral"
    return round(score, 1), label


def add_sentiment(frame):
    result = frame.copy()
    scored = result["text"].fillna("").map(score_text)
    result["sentiment_score"] = scored.map(lambda item: item[0])
    result["sentiment"] = scored.map(lambda item: item[1])
    return result
