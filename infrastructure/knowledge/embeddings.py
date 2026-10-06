"""Deterministic lexical embeddings for the Knowledge MCP (Phase 12).

A dependency-free TF-IDF-style retrieval index: documents are tokenized into
lowercased word tokens (stopwords removed) and represented as sparse
term -> term-frequency vectors. The retriever combines these with corpus-level
inverse document frequencies to score relevance. Everything is a pure function
of the stored corpus and the query, so the same query always returns the same
ranking - no model call, no network, no nondeterminism.

This is an *embedding representation* of text for retrieval. It is not an ML
model, it does not understand language, and it never generates content.
"""

import math
import re
from collections import Counter

# Domain-aware English stopword set (keeps AML-relevant terms like "no",
# "not", "must", "report" which carry meaning in policy text).
STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "as",
        "into",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "their",
        "they",
        "we",
        "you",
        "your",
        "shall",
        "should",
        "can",
        "may",
        "will",
        "would",
        "could",
        "any",
        "all",
        "each",
        "such",
        "other",
        "than",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "what",
        "how",
        "why",
    }
)

MIN_TOKEN_LENGTH = 2


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens of length >= 2 with stopwords removed.

    Deterministic and locale-free: only ASCII word characters are kept, so
    the same text always yields the same tokens on every platform.
    """
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in raw if len(t) >= MIN_TOKEN_LENGTH and t not in STOPWORDS]


def term_frequencies(text: str) -> dict[str, float]:
    """Normalized term-frequency vector for one text (L1-normalized)."""
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = float(sum(counts.values()))
    return {term: count / total for term, count in counts.items()}


def build_idf(documents: list[str]) -> dict[str, float]:
    """Inverse document frequency over the corpus (smoothed, log-scaled).

    ``idf(term) = log((1 + N) / (1 + df)) + 1`` - terms in every document
    still carry a small positive weight; unseen terms get the maximum idf.
    """
    doc_count = len(documents)
    if doc_count == 0:
        return {}
    doc_freq: Counter[str] = Counter()
    for document in documents:
        doc_freq.update(set(tokenize(document)))
    return {term: math.log((1 + doc_count) / (1 + df)) + 1.0 for term, df in doc_freq.items()}


def embed(text: str, idf: dict[str, float]) -> dict[str, float]:
    """TF-IDF embedding of one text under the given idf weights.

    Terms unseen in the corpus get the *maximum observed idf* (they are
    treated as maximally rare, never silently ignored); with an empty idf
    the embedding degrades to a plain term-frequency vector.
    """
    tf = term_frequencies(text)
    if not tf:
        return {}
    ceiling = max(idf.values()) if idf else 1.0
    return {term: weight * idf.get(term, ceiling) for term, weight in tf.items()}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors (0.0 for empty inputs)."""
    if not a or not b:
        return 0.0
    if len(b) < len(a):
        a, b = b, a
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    norm_a = math.sqrt(sum(weight * weight for weight in a.values()))
    norm_b = math.sqrt(sum(weight * weight for weight in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
