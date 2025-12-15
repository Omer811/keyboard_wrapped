#!/usr/bin/env python3
"""
Lightweight English word validation.

Optional dependency: `wordfreq`. If not installed, a built-in fallback
dictionary covers the most common words.
"""

from typing import Iterable, Optional, Set

try:
    from wordfreq import zipf_frequency
except ImportError:  # pragma: no cover
    zipf_frequency = None  # type: ignore


DEFAULT_WORD_SET = frozenset(
    [
        "the",
        "be",
        "to",
        "of",
        "and",
        "a",
        "in",
        "that",
        "have",
        "i",
        "it",
        "for",
        "not",
        "on",
        "with",
        "he",
        "as",
        "you",
        "do",
        "at",
        "this",
        "but",
        "his",
        "by",
        "from",
        "they",
        "we",
        "say",
        "her",
        "she",
        "or",
        "an",
        "will",
        "my",
        "one",
        "all",
        "would",
        "there",
        "their",
        "what",
        "so",
        "up",
        "out",
        "if",
        "about",
        "who",
        "get",
        "which",
        "go",
        "me",
        "when",
        "make",
        "can",
        "like",
        "time",
        "no",
        "just",
        "him",
        "know",
        "take",
        "people",
        "into",
        "year",
        "your",
        "good",
        "some",
        "could",
        "them",
        "see",
        "other",
        "than",
        "then",
        "now",
        "look",
        "only",
        "come",
        "its",
        "over",
        "think",
        "also",
        "back",
        "after",
        "use",
        "two",
        "how",
        "our",
        "work",
        "first",
        "well",
        "way",
        "even",
        "new",
        "want",
        "because",
        "any",
        "these",
        "give",
        "day",
        "most",
        "us",
        "keyboard",
        "accuracy",
        "typing",
        "word",
        "score",
        "progress",
        "monitor",
        "python",
        "insight",
        "log",
        "health",
        "craft",
        "apple",
        "logger",
        "balance",
        "rhythm",
        "tempo",
        "story",
        "error",
        "track",
        "flow",
        "keys",
    ]
)

HEBREW_FALLBACK = frozenset(
    [
        "אני",
        "אתה",
        "את",
        "אנחנו",
        "הוא",
        "היא",
        "מה",
        "גם",
        "לא",
        "כן",
        "כאן",
        "שם",
        "בוקר",
        "לילה",
        "עבודה",
        "מקלדת",
        "תכנית",
        "מילה",
        "זרם",
        "אור",
        "דרך",
        "טקסט",
        "עוגה",
        "אהבה",
        "שיר",
        "בוא",
        "לך",
        "היום",
        "מחר",
        "גיע",
        "כתיבה",
        "קשר",
        "איפה",
        "מי",
        "למה",
        "עם",
        "עין",
    ]
)

LANGUAGE_FALLBACK_WORDS = {
    "en": DEFAULT_WORD_SET,
    "he": HEBREW_FALLBACK,
}


class WordChecker:
    def __init__(
        self,
        threshold: float = 2.5,
        min_length: int = 1,
        extra_words: Optional[Iterable[str]] = None,
        fallback_words: Optional[Set[str]] = None,
        languages: Optional[Iterable[str]] = None,
    ):
        self.threshold = threshold
        self.min_length = min_length
        self.extra_words = {word.lower() for word in extra_words or []}
        self.languages = [lang.lower() for lang in (languages or ["en"])]
        fallback_sources = [fallback_words or set()]
        fallback_sources.append(self.extra_words)
        fallback_sources.extend(
            LANGUAGE_FALLBACK_WORDS.get(lang, frozenset()) for lang in self.languages
        )
        self.fallback = frozenset().union(*fallback_sources)

    def is_correct(self, word: str) -> bool:
        normalized = word.lower().strip()
        if len(normalized) < self.min_length:
            return False
        if normalized in self.fallback:
            return True
        for lang in self.languages:
            freq = self._zipf_frequency(normalized, lang)
            if freq is not None and freq >= self.threshold:
                return True
        return normalized in self.fallback

    def _zipf_frequency(self, word: str, lang: str) -> Optional[float]:
        if zipf_frequency is None:
            return None
        try:
            return zipf_frequency(word, lang)
        except ValueError:
            return None
