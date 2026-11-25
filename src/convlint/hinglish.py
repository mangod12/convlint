"""Phrase banks for English + Hindi/Hinglish (romanized and Devanagari).

These power deterministic matching. They are intentionally conservative:
a phrase must be a recognizable pattern, not a single common word, unless
the word is unambiguous in context (e.g. 'alvida').
"""
from __future__ import annotations

import re
from typing import List


def _rx(phrase: str) -> re.Pattern:
    # word-ish boundaries that work for latin; plain search for Devanagari
    if re.search(r"[ऀ-ॿ]", phrase):
        return re.compile(re.escape(phrase))
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def bank(phrases: List[str]) -> List[re.Pattern]:
    return [_rx(p) for p in phrases]


def any_match(patterns: List[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


# Agent wrapping up / ending the call.
FAREWELL = bank([
    "goodbye", "good bye", "bye bye", "bye for now",
    "have a great day", "have a nice day", "take care",
    "see you next time", "see you tomorrow", "talk to you tomorrow",
    "talk to you later", "that's all for today", "thats all for today",
    "that is all for today", "that's it for today", "thats it for today",
    "we are done for today", "we're done for today", "let's end the call",
    "i'll let you go", "i will let you go", "end this session",
    "alvida", "phir milte hain", "phir milenge", "milte hain kal",
    "aaj ke liye bas", "aaj ke liye itna hi", "chalo bye", "theek hai bye",
    "अलविदा", "फिर मिलते हैं", "फिर मिलेंगे", "आज के लिए बस", "चलो बाय",
])

# Agent asking whether to stop / wrap up.
ENOUGH_CHECK = bank([
    "is that enough", "is it enough", "was that enough",
    "shall we stop", "should we stop", "should we end", "shall we end",
    "shall we wrap up", "should we wrap up", "want to stop", "want to end",
    "enough for today", "done for today?", "end the call",
    "itna kaafi", "itna kaafi hai", "kaafi hai aaj ke liye",
    "bas karein", "bas kare", "band karein", "band kare",
    "khatam karein", "khatam kare", "call end karein",
    "इतना काफी", "बस करें", "बंद करें", "खत्म करें",
])

# User saying time is left / objecting to ending.
TIME_LEFT_OBJECTION = bank([
    "minutes left", "time left", "still have time", "have time left",
    "why stop", "why are we stopping", "why end", "why are you ending",
    "so early", "already over", "already done", "already finished",
    "abhi time hai", "abhi toh time hai", "time bacha hai", "time bacha",
    "abhi toh", "itni jaldi", "kyu stop", "kyun stop", "kyu band",
    "kyun band", "itna jaldi khatam", "abhi khatam",
    "अभी टाइम है", "टाइम बचा है", "इतनी जल्दी", "क्यों बंद", "अभी तो",
])

# Agent claiming memory of something the user said before.
MEMORY_CLAIM = bank([
    "last time you", "last week you", "last call you",
    "you told me last time", "you mentioned last time",
    "you mentioned earlier", "you said earlier", "you told me before",
    "as you told me", "as you mentioned", "as we discussed",
    "i remember you said", "i remember you told",
    "pichli baar aapne", "pichli call me", "pichle call me",
    "aapne pehle bataya", "jaisa aapne bataya tha", "aapne kaha tha",
    "aapne pichli baar", "पिछली बार", "पिछली कॉल", "आपने पहले बताया", "आपने कहा था",
])

# User correcting the agent / saying it repeated itself.
CORRECTION = bank([
    "i already said", "i already told", "i told you already",
    "i just said", "i just told", "like i said", "as i said", "not what you said", "you just said",
    "aapne toh kaha", "aapne abhi kaha", "tune toh kaha", "तुमने तो कहा",
    "that's not what i said", "that is not what i said", "not what i said",
    "maine toh bataya", "maine toh kaha", "maine pehle bataya",
    "maine bola na", "maine kaha na", "arre maine bola",
    "nahi nahi", "मैंने तो बताया", "मैंने तो कहा", "मैंने पहले बताया",
])

# Farewell-sounding praise mid-call.
PRAISE_FAREWELL = bank([
    "today you did great", "you did great today", "great job today",
    "well done today", "you did really well today", "amazing session today",
    "you were great today", "proud of you today",
    "aaj aapne bahut achha kiya", "aaj bahut acche", "aaj bahut acha kiya",
    "bahut badhiya aaj", "आज आपने बहुत अच्छा किया", "आज बहुत अच्छे",
])

# Scripted imagination drill: "now imagine X ... say/tell/repeat Y".
IMAGINE_CHAIN = re.compile(
    r"\b(now[,.]? )?(imagine|sochiye|socho|soch ke bolo|kalpna kijiye|kalpana)\b"
    r".{0,120}?\b(say|tell|repeat|bolo|boliye|batao|bataiye)\b",
    re.IGNORECASE,
)

# User signals this is their first call ever.
FIRST_CALL = bank([
    "first call", "first time calling", "my first time",
    "pehli call", "pehli baar call", "pehla call",
    "new here", "naya hoon", "naya hun", "nayi hoon",
    "पहली कॉल", "पहली बार", "नया हूँ",
])

# Very short, low-content user answers.
PASSIVE_ANSWERS = {
    "haan", "ha", "han", "haanji", "hanji", "ji", "yes", "yeah", "yep", "ok",
    "okay", "kk", "hmm", "hm", "umm", "pata nahi", "pata nahi ji", "nahi pata",
    "don't know", "dont know", "do not know", "idk", "no idea", "nahi", "no",
    "nope", "theek hai", "thik hai", "accha", "achha", "acha", "shayad",
    "maybe", "samajh nahi aaya", "samajh nahi", "हाँ", "हां", "नहीं", "ठीक है",
    "पता नहीं", "अच्छा", "शायद", "समझ नहीं आया",
}


def is_passive_answer(text: str) -> bool:
    t = text.strip().lower().strip(" .!?,")
    if t in PASSIVE_ANSWERS:
        return True
    words = t.split()
    return len(words) <= 2 and all(
        w.strip(" .!?,") in PASSIVE_ANSWERS for w in words
    )


def is_question(text: str) -> bool:
    t = text.strip()
    if t.endswith("?"):
        return True
    # common question openers without '?'
    return bool(re.match(
        r"^(what|why|how|when|where|which|who|whom|whose|can you|could you|"
        r"do you|did you|are you|is it|shall we|should we|kya|kaise|kyu|"
        r"kyun|kab|kahan|kaun|क्या|कैसे|क्यों|कब|कहां|कौन)\b",
        t.lower()))
