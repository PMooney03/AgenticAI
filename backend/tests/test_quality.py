from app.eval.quality import content_tokens, is_refusal, score_quality


def test_refusal_detection_is_case_insensitive() -> None:
    assert is_refusal("The uploaded documents do not contain enough information to answer this.")
    assert not is_refusal("Employees receive twenty five days [Source 1].")


def test_content_tokens_drop_stopwords_and_citations() -> None:
    tokens = content_tokens("The employees receive twenty five days [Source 1].")
    assert "the" not in tokens
    assert "source" not in tokens
    assert "employees" in tokens
    assert "twenty" in tokens
    assert "days" in tokens


def test_groundedness_is_one_on_refusal() -> None:
    score = score_quality(
        answer="The uploaded documents do not contain enough information to answer this.",
        retrieved_chunks=2,
        cited_labels=[],
        evidence_texts=["Employees receive twenty five days of annual leave."],
    )
    assert score.refused is True
    assert score.groundedness == 1.0
    assert score.citation_rate is None


def test_citation_rate_and_lexical_overlap() -> None:
    score = score_quality(
        answer="Employees receive twenty five days of annual leave [Source 1].",
        retrieved_chunks=2,
        cited_labels=[1],
        evidence_texts=["Employees receive twenty five days of paid annual leave per year."],
    )
    assert score.refused is False
    assert score.citation_rate == 0.5
    assert score.groundedness is not None and score.groundedness >= 0.8


def test_ungrounded_answer_scores_low() -> None:
    score = score_quality(
        answer="The CFO is Dana Whitfield and revenue tripled overnight.",
        retrieved_chunks=1,
        cited_labels=[],
        evidence_texts=["Employees receive twenty five days of annual leave."],
    )
    assert score.citation_rate == 0.0
    assert score.groundedness is not None and score.groundedness < 0.2


def test_no_evidence_means_groundedness_not_applicable() -> None:
    score = score_quality(
        answer="Hello from the second brain.",
        retrieved_chunks=0,
        cited_labels=[],
        evidence_texts=[],
    )
    assert score.groundedness is None
    assert score.citation_rate is None
