"""Phase 12 - deterministic TF-IDF embedding module (pure functions)."""

from infrastructure.knowledge.embeddings import (
    STOPWORDS,
    build_idf,
    cosine_similarity,
    embed,
    term_frequencies,
    tokenize,
)


def test_tokenize_is_deterministic_and_lowercase() -> None:
    assert tokenize("Shared Device Accounts") == tokenize("shared device accounts")
    assert tokenize("Shared Device Accounts") == tokenize("SHARED DEVICE ACCOUNTS")


def test_tokenize_removes_stopwords_and_short_tokens() -> None:
    tokens = tokenize("The account must report a suspicious of")
    assert "the" not in tokens
    assert "a" not in tokens
    assert "of" not in tokens
    assert "account" in tokens
    assert "report" in tokens
    assert "suspicious" in tokens


def test_tokenize_keeps_aml_meaningful_terms() -> None:
    # Domain stopwords keep negation and obligation words.
    assert "must" not in STOPWORDS
    assert "not" not in STOPWORDS
    assert "no" not in STOPWORDS


def test_term_frequencies_is_l1_normalized() -> None:
    tf = term_frequencies("mule account mule account pass through funds")
    total = sum(tf.values())
    assert abs(total - 1.0) < 1e-9
    assert tf["mule"] == tf["account"]


def test_term_frequencies_empty_for_empty_text() -> None:
    assert term_frequencies("") == {}
    assert term_frequencies("the a of to") == {}


def test_build_idf_rarer_terms_weight_more() -> None:
    corpus = [
        "shared device fraud ring indicator",
        "shared device between accounts",
        "unique smurfing pattern",
    ]
    idf = build_idf(corpus)
    # "shared" appears in 2/3 docs; "smurfing" in 1/3.
    assert idf["smurfing"] > idf["shared"]


def test_embed_same_content_same_vector() -> None:
    idf = build_idf(["mule accounts receive funds", "layering hides proceeds"])
    assert embed("mule accounts receive funds", idf) == embed("mule accounts receive funds", idf)


def test_embed_different_content_different_vector() -> None:
    idf = build_idf(["mule accounts receive funds", "layering hides proceeds"])
    assert embed("mule accounts receive funds", idf) != embed("layering hides proceeds", idf)


def test_cosine_similarity_identical_and_orthogonal() -> None:
    idf = build_idf(["shared device ring", "clean transfer only", "third doc here"])
    v1 = embed("shared device ring", idf)
    assert abs(cosine_similarity(v1, v1) - 1.0) < 1e-9
    v2 = embed("clean transfer only", idf)
    assert cosine_similarity(v1, v2) == 0.0  # no shared terms -> orthogonal


def test_cosine_similarity_empty_vectors_are_zero() -> None:
    assert cosine_similarity({}, {"a": 1.0}) == 0.0
    assert cosine_similarity({"a": 1.0}, {}) == 0.0


def test_unseen_terms_outweigh_seen_terms_at_equal_frequency() -> None:
    corpus = ["one doc here", "second doc now", "third doc also"]
    idf = build_idf(corpus)
    seen = embed("one doc", idf)
    unseen = embed("zzzqqq qqq", idf)  # two unseen tokens, same token count
    # An unseen term carries at least the weight of ANY seen term with the
    # same term frequency: novel vocabulary is never silently ignored.
    assert min(unseen.values()) >= max(seen.values()) > 0


def test_repeated_calls_identical() -> None:
    text = "deterministic ranking for the same query"
    idf = build_idf([text, "another document"])
    assert embed(text, idf) == embed(text, idf)
    assert build_idf([text, "another document"]) == build_idf([text, "another document"])
