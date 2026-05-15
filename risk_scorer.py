"""
risk_scorer.py
記事全体の危険度をスコア化し、最終判定を出す。
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from config import OVERALL_DANGER_RATE, OVERALL_WARNING_RATE
from similarity_checker import SimilarityMatch


@dataclass
class UrlMatchSummary:
    """同一URLからの一致集計"""
    url: str
    title: str
    match_count: int        # 一致フレーズ数
    max_similarity: float   # 最高類似度
    risk_level: str         # 最も高いリスクレベル


@dataclass
class RiskSummary:
    """記事全体のリスク評価サマリー"""
    overall_score: float        # 0〜100
    final_risk: str             # 問題なし / 要確認 / 高リスク / 危険
    total_phrases: int          # チェックしたフレーズ数
    matched_count: int          # 何らかの類似が検出されたフレーズ数
    danger_count: int           # 「危険」判定フレーズ数
    high_risk_count: int        # 「高リスク」判定フレーズ数
    warning_count: int          # 「要確認」判定フレーズ数
    match_rate: float           # 類似フレーズ率（%）
    summary_reason: str         # 最終判定の理由
    url_summaries: List[UrlMatchSummary] = field(default_factory=list)  # URL別集計


# リスクレベルごとの加算ポイント
_SCORE_MAP = {
    "危険": 25,
    "要確認": 12,
    "高リスク": 6,
}


class RiskScorer:

    def calculate(
        self, matches: List[SimilarityMatch], total_phrases: int
    ) -> RiskSummary:
        """
        全マッチ結果から記事全体のリスクスコアを算出する。

        スコア計算:
          - 各マッチのリスクレベルに応じてポイントを加算
          - 全体の類似フレーズ率が高い場合は下限スコアを設定
        """
        if total_phrases == 0:
            return RiskSummary(
                overall_score=0.0,
                final_risk="問題なし",
                total_phrases=0,
                matched_count=0,
                danger_count=0,
                high_risk_count=0,
                warning_count=0,
                match_rate=0.0,
                summary_reason="チェック対象フレーズがありませんでした。",
            )

        danger_count = sum(1 for m in matches if m.risk_level == "危険")
        warning_count = sum(1 for m in matches if m.risk_level == "要確認")
        high_risk_count = sum(1 for m in matches if m.risk_level == "高リスク")
        matched_count = len(matches)

        # ポイント加算方式でスコアを算出
        raw_score = sum(_SCORE_MAP.get(m.risk_level, 0) for m in matches)
        score = min(100.0, float(raw_score))

        # 全体の類似フレーズ率による下限スコア設定
        match_rate = (matched_count / total_phrases) * 100
        if match_rate >= OVERALL_DANGER_RATE:
            score = max(score, 80.0)
        elif match_rate >= OVERALL_WARNING_RATE:
            score = max(score, 50.0)

        # URL別集計（同一URLから3件以上一致でスコア加算）
        url_summaries = self._build_url_summaries(matches)
        for us in url_summaries:
            if us.match_count >= 3:
                score = min(100.0, score + 20.0)
            elif us.match_count >= 2:
                score = min(100.0, score + 10.0)

        final_risk = self._score_to_risk(score)
        reason = self._build_reason(
            score, danger_count, warning_count, high_risk_count, match_rate, url_summaries
        )

        return RiskSummary(
            overall_score=round(score, 1),
            final_risk=final_risk,
            total_phrases=total_phrases,
            matched_count=matched_count,
            danger_count=danger_count,
            high_risk_count=high_risk_count,
            warning_count=warning_count,
            match_rate=round(match_rate, 1),
            summary_reason=reason,
            url_summaries=url_summaries,
        )

    def _score_to_risk(self, score: float) -> str:
        """スコア値を最終判定ラベルに変換する。"""
        if score < 20:
            return "問題なし"
        elif score < 50:
            return "要確認"
        elif score < 80:
            return "高リスク"
        else:
            return "危険"

    def _build_url_summaries(self, matches: List[SimilarityMatch]) -> List[UrlMatchSummary]:
        """URL別の一致集計を生成する。一致数の多い順で返す。"""
        url_data: Dict[str, dict] = {}
        risk_order = {"危険": 3, "要確認": 2, "高リスク": 1, "問題なし": 0}

        for m in matches:
            if m.url not in url_data:
                url_data[m.url] = {
                    "title": m.title,
                    "count": 0,
                    "max_similarity": 0.0,
                    "risk_level": "問題なし",
                }
            url_data[m.url]["count"] += 1
            url_data[m.url]["max_similarity"] = max(url_data[m.url]["max_similarity"], m.similarity)
            if risk_order.get(m.risk_level, 0) > risk_order.get(url_data[m.url]["risk_level"], 0):
                url_data[m.url]["risk_level"] = m.risk_level

        return sorted(
            [UrlMatchSummary(url=url, title=d["title"], match_count=d["count"],
                             max_similarity=d["max_similarity"], risk_level=d["risk_level"])
             for url, d in url_data.items()],
            key=lambda x: x.match_count,
            reverse=True,
        )

    def _build_reason(
        self,
        score: float,
        danger_count: int,
        warning_count: int,
        high_risk_count: int,
        match_rate: float,
        url_summaries: List[UrlMatchSummary] = None,
    ) -> str:
        """最終判定の理由文を生成する。"""
        parts = []

        if danger_count > 0:
            parts.append(f"危険フレーズ {danger_count}件")
        if warning_count > 0:
            parts.append(f"要確認フレーズ {warning_count}件")
        if high_risk_count > 0:
            parts.append(f"高リスクフレーズ {high_risk_count}件")
        if match_rate >= OVERALL_DANGER_RATE:
            parts.append(f"記事全体の類似率 {match_rate:.1f}%（危険ライン{OVERALL_DANGER_RATE}%超）")
        elif match_rate >= OVERALL_WARNING_RATE:
            parts.append(f"記事全体の類似率 {match_rate:.1f}%（要注意ライン{OVERALL_WARNING_RATE}%超）")
        if url_summaries:
            top = url_summaries[0]
            if top.match_count >= 2:
                parts.append(f"同一URL({top.match_count}フレーズ一致)あり")

        if not parts:
            return "類似フレーズが検出されませんでした。"

        return "検出内容：" + "、".join(parts)
