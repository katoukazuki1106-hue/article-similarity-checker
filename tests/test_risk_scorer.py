"""
test_risk_scorer.py
RiskScorer のユニットテスト
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from similarity_checker import SimilarityMatch
from risk_scorer import RiskScorer


def _make_match(risk_level: str, similarity: float = 85.0) -> SimilarityMatch:
    return SimilarityMatch(
        phrase="テスト用フレーズです。チェックのために使用します。",
        similarity=similarity,
        matched_snippet="類似スニペットです。",
        url="https://example.com",
        title="テスト記事",
        continuous_match_length=20,
        is_exact_match=False,
        risk_level=risk_level,
        reason="テスト理由",
        editor_comment="テストコメント",
    )


class TestScoreToRisk:
    def test_score_0_is_safe(self):
        assert RiskScorer()._score_to_risk(0) == "問題なし"

    def test_score_19_is_safe(self):
        assert RiskScorer()._score_to_risk(19) == "問題なし"

    def test_score_20_is_warning(self):
        assert RiskScorer()._score_to_risk(20) == "要確認"

    def test_score_49_is_warning(self):
        assert RiskScorer()._score_to_risk(49) == "要確認"

    def test_score_50_is_high_risk(self):
        assert RiskScorer()._score_to_risk(50) == "高リスク"

    def test_score_79_is_high_risk(self):
        assert RiskScorer()._score_to_risk(79) == "高リスク"

    def test_score_80_is_danger(self):
        assert RiskScorer()._score_to_risk(80) == "危険"

    def test_score_100_is_danger(self):
        assert RiskScorer()._score_to_risk(100) == "危険"


class TestCalculate:
    def test_no_matches_returns_safe(self):
        result = RiskScorer().calculate([], 10)
        assert result.final_risk == "問題なし"
        assert result.overall_score == 0.0

    def test_single_danger_match(self):
        matches = [_make_match("危険", similarity=95.0)]
        result = RiskScorer().calculate(matches, 10)
        assert result.danger_count == 1
        assert result.overall_score >= 20

    def test_multiple_danger_matches_increase_score(self):
        matches = [_make_match("危険") for _ in range(4)]
        result = RiskScorer().calculate(matches, 10)
        assert result.overall_score >= 50

    def test_high_match_rate_elevates_score(self):
        # 10フレーズ中5件（50%）が類似 → OVERALL_DANGER_RATE(40%)超えで危険
        matches = [_make_match("高リスク", similarity=65.0) for _ in range(5)]
        result = RiskScorer().calculate(matches, 10)
        assert result.match_rate == 50.0
        assert result.overall_score >= 80  # 全体率による下限スコア

    def test_counters_correct(self):
        matches = [
            _make_match("危険"),
            _make_match("要確認"),
            _make_match("高リスク"),
            _make_match("要確認"),
        ]
        result = RiskScorer().calculate(matches, 20)
        assert result.danger_count == 1
        assert result.warning_count == 2
        assert result.high_risk_count == 1
        assert result.matched_count == 4

    def test_zero_phrases_safe(self):
        result = RiskScorer().calculate([], 0)
        assert result.final_risk == "問題なし"
        assert result.total_phrases == 0
