"""Local evaluation: the same quality scores used online, plus a golden-set harness."""

from app.eval.quality import QualityScore, score_quality

__all__ = ["QualityScore", "score_quality"]
