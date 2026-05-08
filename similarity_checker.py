"""
similarity_checker.py
納品記事のフレーズと検索結果スニペットの類似度を判定する。
rapidfuzz（高速ファジーマッチ）と difflib（連続一致）を組み合わせて使用する。
"""

import difflib
from dataclasses import dataclass, field
from typing import List, Optional

from rapidfuzz import fuzz

from config import (
    HIGH_SIMILARITY_THRESHOLD,
    WARNING_SIMILARITY_THRESHOLD,
    MID_SIMILARITY_THRESHOLD,
    DANGER_CONTINUOUS_MATCH_LENGTH,
    WARNING_CONTINUOUS_MATCH_LENGTH,
    CAUTION_CONTINUOUS_MATCH_LENGTH,
    MIN_TEXT_LENGTH,
)
from search_client import SearchResult


@dataclass
class SimilarityMatch:
    """1フレーズの類似判定結果"""
    phrase: str                      # 対象フレーズ
    similarity: float                # 類似度スコア（0〜100）
    matched_snippet: str             # 最も類似したスニペット
    url: str                         # 類似元URL
    title: str                       # 類似元タイトル
    continuous_match_length: int     # 最長連続一致文字数
    is_exact_match: bool             # ほぼ完全一致かどうか（95以上）
    risk_level: str                  # 問題なし / 高リスク / 要確認 / 危険
    reason: str                      # 判定理由
    editor_comment: str              # 編集者向けコメント


class SimilarityChecker:

    def check_phrase(
        self, phrase: str, search_results: List[SearchResult]
    ) -> Optional[SimilarityMatch]:
        """
        1フレーズを検索結果スニペット群と比較し、最も類似度が高いものを返す。
        すべてのスニペットとの類似度が低い場合は None を返す。
        """
        if len(phrase) < MIN_TEXT_LENGTH:
            return None

        best_score = 0.0
        best_result: Optional[SearchResult] = None

        for result in search_results:
            score = self._compute_similarity(phrase, result.snippet)
            if score > best_score:
                best_score = score
                best_result = result

        # 類似度が低すぎる場合は無視
        if best_score < 40 or best_result is None:
            return None

        continuous_len = self._continuous_match_length(phrase, best_result.snippet)
        risk_level, reason = self._determine_risk(best_score, continuous_len)

        # 問題なしはNoneで返すことでレポートをすっきりさせる
        if risk_level == "問題なし":
            return None

        return SimilarityMatch(
            phrase=phrase,
            similarity=round(best_score, 1),
            matched_snippet=best_result.snippet,
            url=best_result.url,
            title=best_result.title,
            continuous_match_length=continuous_len,
            is_exact_match=(best_score >= 95),
            risk_level=risk_level,
            reason=reason,
            editor_comment=self._generate_editor_comment(risk_level, best_score, continuous_len),
        )

    def _compute_similarity(self, phrase: str, snippet: str) -> float:
        """
        複数の類似度スコアの最大値を返す。
        - partial_ratio: 部分一致に強い
        - token_set_ratio: 語順が違っても一致する
        """
        scores = [
            fuzz.partial_ratio(phrase, snippet),
            fuzz.token_set_ratio(phrase, snippet),
        ]
        return max(scores)

    def _continuous_match_length(self, text1: str, text2: str) -> int:
        """difflib で最長連続一致部分の文字数を返す。"""
        matcher = difflib.SequenceMatcher(None, text1, text2, autojunk=False)
        blocks = matcher.get_matching_blocks()
        # autojunk=False にしてすべての一致ブロックを確認
        return max((block.size for block in blocks), default=0)

    def _determine_risk(self, similarity: float, continuous_len: int) -> tuple:
        """
        類似度スコアと連続一致文字数からリスクレベルと理由を返す。

        優先度: 危険 > 要確認 > 高リスク > 問題なし
        """
        reasons = []

        if similarity >= HIGH_SIMILARITY_THRESHOLD:
            reasons.append(f"類似度{similarity:.0f}%（危険ライン{HIGH_SIMILARITY_THRESHOLD}%以上）")
        elif similarity >= WARNING_SIMILARITY_THRESHOLD:
            reasons.append(f"類似度{similarity:.0f}%（要確認ライン{WARNING_SIMILARITY_THRESHOLD}%以上）")
        elif similarity >= MID_SIMILARITY_THRESHOLD:
            reasons.append(f"類似度{similarity:.0f}%")

        if continuous_len >= DANGER_CONTINUOUS_MATCH_LENGTH:
            reasons.append(f"連続{continuous_len}文字一致（危険ライン{DANGER_CONTINUOUS_MATCH_LENGTH}文字以上）")
        elif continuous_len >= WARNING_CONTINUOUS_MATCH_LENGTH:
            reasons.append(f"連続{continuous_len}文字一致（要確認ライン{WARNING_CONTINUOUS_MATCH_LENGTH}文字以上）")
        elif continuous_len >= CAUTION_CONTINUOUS_MATCH_LENGTH:
            reasons.append(f"連続{continuous_len}文字一致")

        # 最終リスクレベルの決定
        if (similarity >= HIGH_SIMILARITY_THRESHOLD
                or continuous_len >= DANGER_CONTINUOUS_MATCH_LENGTH):
            level = "危険"
        elif (similarity >= WARNING_SIMILARITY_THRESHOLD
              or continuous_len >= WARNING_CONTINUOUS_MATCH_LENGTH):
            level = "要確認"
        elif (similarity >= MID_SIMILARITY_THRESHOLD
              or continuous_len >= CAUTION_CONTINUOUS_MATCH_LENGTH):
            level = "高リスク"
        else:
            level = "問題なし"

        reason = "、".join(reasons) if reasons else "低類似度"
        return level, reason

    def _generate_editor_comment(
        self, risk_level: str, similarity: float, continuous_len: int
    ) -> str:
        """編集者向けの確認コメントを生成する。"""
        if risk_level == "危険":
            return (
                "このフレーズは既存Web記事との高い一致が検出されました。"
                "出典・引用の表記があるか確認してください。"
                "引用でない場合はライターへ確認・修正を依頼することを推奨します。"
            )
        elif risk_level == "要確認":
            return (
                "類似度が高い表現が検出されました。"
                "一般的な業界用語・定型表現の可能性もあるため、文脈と出典を確認してください。"
            )
        elif risk_level == "高リスク":
            return (
                "部分的な一致が検出されました。"
                "よく使われる表現の可能性がありますが、念のため類似元URLを確認してください。"
            )
        return "問題ありません。"
