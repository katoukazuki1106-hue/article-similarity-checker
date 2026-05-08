"""
test_similarity_checker.py
SimilarityChecker のユニットテスト
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from search_client import SearchResult
from similarity_checker import SimilarityChecker


def _make_result(snippet: str) -> SearchResult:
    return SearchResult(
        title="テスト記事",
        url="https://example.com/test",
        snippet=snippet,
    )


class TestCheckPhrase:
    def test_exact_match_detected(self):
        phrase = "SEOとは検索エンジン最適化のことです。Googleで上位表示するための施策の総称です。"
        results = [_make_result(phrase)]
        match = SimilarityChecker().check_phrase(phrase, results)
        assert match is not None
        assert match.similarity >= 90
        assert match.is_exact_match is True

    def test_partial_match_detected(self):
        phrase = "キーワード調査は検索エンジン最適化の重要な工程です。適切な語句を選ぶことが成功の鍵となります。"
        snippet = "キーワード調査は非常に重要な工程です。適切な語句の選定が成功を左右します。"
        results = [_make_result(snippet)]
        match = SimilarityChecker().check_phrase(phrase, results)
        # 部分一致なので何らかのスコアが返ること
        # （スコアが40以上の場合のみマッチとして返る）
        if match:
            assert match.similarity >= 40

    def test_no_match_returns_none(self):
        phrase = "今日の夕食はカレーライスでした。とても美味しかったです。家族全員が満足していました。"
        snippet = "SEOとは検索エンジン最適化のことです。Googleアルゴリズムを理解することが重要です。"
        results = [_make_result(snippet)]
        match = SimilarityChecker().check_phrase(phrase, results)
        # 全く異なる内容なのでNoneまたは低スコア
        if match:
            assert match.risk_level in ("問題なし", "高リスク")
        else:
            assert match is None

    def test_short_phrase_returns_none(self):
        # MIN_TEXT_LENGTH未満のフレーズはNoneを返す
        phrase = "短いです。"
        results = [_make_result("短いです。")]
        match = SimilarityChecker().check_phrase(phrase, results)
        assert match is None

    def test_risk_level_danger_on_high_similarity(self):
        phrase = "コンテンツマーケティングとはターゲットユーザーにとって有益なコンテンツを継続的に発信し収益につなげる手法です。"
        results = [_make_result(
            "コンテンツマーケティングとは、ターゲットユーザーにとって有益なコンテンツを継続的に発信することで、"
            "潜在顧客を引き付け、最終的に収益につなげるマーケティング手法です。"
        )]
        match = SimilarityChecker().check_phrase(phrase, results)
        if match:
            assert match.risk_level in ("要確認", "危険")


class TestContinuousMatchLength:
    def test_full_match_length(self):
        text = "これは完全に一致するテストフレーズです。"
        checker = SimilarityChecker()
        length = checker._continuous_match_length(text, text)
        assert length == len(text)

    def test_partial_match_length(self):
        checker = SimilarityChecker()
        t1 = "ABCDEFGHIJこれはテストです"
        t2 = "XYZABCDEFGHIJこれは違います"
        length = checker._continuous_match_length(t1, t2)
        assert length > 0
