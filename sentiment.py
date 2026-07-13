"""Tamil/Tanglish/English cinema sentiment and aspect analysis."""
from __future__ import annotations
import math, re

POSITIVE={
 "masterpiece":3.2,"vera level":2.8,"vera lvl":2.7,"வேற லெவல்":2.8,"sema":2.2,"semma":2.2,"செம":2.2,
 "mass":1.8,"மாஸ்":1.8,"super":1.8,"சூப்பர்":1.8,"excellent":2.5,"amazing":2.3,"awesome":2.2,
 "good":1.4,"nalla":1.5,"நல்ல":1.5,"worth":1.6,"goosebumps":2.3,"emotional":1.5,"engaging":1.9,
 "blockbuster":2.3,"fire":1.8,"banger":1.8,"love":1.7,"loved":1.8,"பிடிச்சிருக்கு":1.9,"pudichiruku":1.9,
 "pudichuthu":1.8,"sambavam":2.5,"சம்பவம்":2.5,"comeback":1.7,"tharam":1.8,"தரம்":1.8,
 "pakka":1.7,"பக்கா":1.7,"kalakkal":2.0,"கலக்கல்":2.0,"arputham":2.2,"அருமை":2.2,"best":2.0,
 "fantastic":2.4,"brilliant":2.4,"beautiful":1.7,"fun":1.4,"enjoyed":1.7,"hit":1.5,"watchable":1.0,
}
NEGATIVE={
 "worst":-3.2,"waste":-2.6,"wasteu":-2.6,"மோசம்":-2.7,"mosam":-2.7,"mokke":-2.4,"mokka":-2.4,
 "மொக்க":-2.4,"boring":-2.2,"bore":-2.0,"போர்":-2.0,"cringe":-2.5,"lag":-1.9,"drag":-1.9,
 "slow":-1.2,"disappointed":-2.1,"disappointing":-2.1,"weak":-1.7,"headache":-2.4,"torture":-2.9,
 "logicless":-1.9,"outdated":-1.8,"flop":-2.2,"bad":-1.8,"பிடிக்கல":-2.1,"pudikala":-2.1,
 "pidikala":-2.1,"sumaar":-1.1,"sumaara":-1.1,"சுமார்":-1.1,"kevalam":-2.6,"கேவலம்":-2.6,
 "kodumai":-2.5,"கொடுமை":-2.5,"blade":-1.9,"overrated":-1.8,"average":-0.8,"dull":-1.6,
 "confusing":-1.3,"predictable":-1.0,"lengthy":-1.4,"irritating":-2.0,"avoid":-2.0,
}
NEGATIONS={"not","no","never","illa","illai","இல்ல","இல்லை","kedaiyathu","கிடையாது"}
BOOSTERS={"very":1.35,"romba":1.45,"ரொம்ப":1.45,"really":1.3,"too":1.2,"ultimate":1.4,"ultimate-ah":1.4}
DIMINISHERS={"little":.75,"konjam":.7,"கொஞ்சம்":.7,"somewhat":.7,"bit":.8}
TANGLISH_HINTS={"sema","semma","romba","nalla","illa","illai","mokka","mokke","pudichiruku","pudikala","sumaar","vera","sambavam","tharam","kalakkal","kevalam","kodumai","padam","kadhai"}
ASPECTS={
 "Story":["story","plot","kadhai","கதை","writing","screenplay","திரைக்கதை"],
 "Acting":["acting","performance","nadippu","நடிப்பு","actor","hero","heroine"],
 "Direction":["direction","director","making","இயக்கம்","iyakkam"],
 "Music":["music","bgm","songs","song","isai","இசை","paattu","பாட்டு"],
 "Visuals":["visual","cinematography","camera","vfx","graphics","ஒளிப்பதிவு"],
 "Pacing":["pace","pacing","lag","drag","slow","lengthy","second half","first half"],
 "Comedy":["comedy","funny","humour","humor","காமெடி","sirippu","சிரிப்பு"],
 "Emotion":["emotion","emotional","heart","feel","sentiment","கண்ணீர்","உணர்வு"],
}

def normalize(text):
 text=re.sub(r"https?://\S+|www\.\S+"," ",str(text).lower())
 text=re.sub(r"(.)\1{3,}",r"\1\1",text)
 return re.sub(r"\s+"," ",text).strip()

def language(text):
 tamil=len(re.findall(r"[\u0B80-\u0BFF]",text)); words=set(re.findall(r"[a-z]+",text.lower()))
 tanglish=len(words&TANGLISH_HINTS)
 if tamil and words: return "Tamil + English"
 if tamil: return "Tamil"
 if tanglish: return "Tanglish"
 return "English/Other"

def analyze_text(text):
 clean=normalize(text); tokens=re.findall(r"[\w\u0B80-\u0BFF'-]+",clean); raw=0.; hits=0
 lexicon={**POSITIVE,**NEGATIVE}
 for phrase,base in lexicon.items():
  for match in re.finditer(r"(?<!\w)"+re.escape(phrase)+r"(?!\w)",clean):
   before=tokens[max(0,len(re.findall(r"[\w\u0B80-\u0BFF'-]+",clean[:match.start()]))-3):]
   weight=base
   if any(x in NEGATIONS for x in before): weight*=-.8
   if before and before[-1] in BOOSTERS: weight*=BOOSTERS[before[-1]]
   if before and before[-1] in DIMINISHERS: weight*=DIMINISHERS[before[-1]]
   raw+=weight; hits+=1
 raw+=min(sum(clean.count(x) for x in ("🔥","❤️","❤","👏","😍","💥")),3)*.7
 raw-=min(sum(clean.count(x) for x in ("🤮","👎","😴","💩")),3)*.85
 low_info=len(tokens)<3 or bool(re.fullmatch(r"[\W_]+",clean))
 score=50. if not hits and abs(raw)<.01 else 50+50*math.tanh(raw/4.8)
 label="Positive" if score>=60 else "Negative" if score<=40 else "Neutral"
 confidence=min(.98,.28+hits*.16+min(abs(raw),4)*.08)
 if low_info: confidence=min(confidence,.2)
 aspects={}
 for name,terms in ASPECTS.items():
  if any(term in clean for term in terms): aspects[name]=round(score,1)
 return {"sentiment_score":round(score,1),"sentiment":label,"confidence":round(confidence,2),
         "language":language(clean),"low_information":low_info,"aspect_scores":aspects}

def score_text(text):
 result=analyze_text(text); return result["sentiment_score"],result["sentiment"]

def add_sentiment(frame):
 result=frame.copy(); analysed=result["text"].fillna("").map(analyze_text)
 for column in ("sentiment_score","sentiment","confidence","language","low_information","aspect_scores"):
  result[column]=analysed.map(lambda item:item[column])
 likes=result.get("likes",0)
 result["analysis_weight"]=(result.confidence*(1+likes.clip(lower=0,upper=100).map(lambda x:math.log1p(x))/4)).clip(.05,2.5)
 return result
