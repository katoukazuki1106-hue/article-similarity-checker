"""
query_builder.py
チェック対象フレーズから検索APIへ投げるクエリを生成する。
"""

import re
from typing import List

from config import MAX_SEARCH_QUERIES, SEARCH_QUERY_MAX_LEN
from text_splitter import TextFragment


class QueryBuilder:

    def build_queries(self, fragments: List[TextFragment]) -> List[str]:
        """
        フレーズリストからユニークな検索クエリを生成する。
        上限は MAX_SEARCH_QUERIES。
        """
        queries: List[str] = []
        seen: set = set()

        # 特徴的なフレーズを優先するためスコア付きでソート
        ranked = self._rank_fragments(fragments)

        for fragment in ranked:
            query = self._clean_for_search(fragment.text)
            if not query or query in seen:
                continue
            queries.append(query)
            seen.add(query)
            if len(queries) >= MAX_SEARCH_QUERIES:
                break

        return queries

    def _clean_for_search(self, text: str) -> str:
        """
        句読点・記号を除去して検索クエリ化する。
        SEARCH_QUERY_MAX_LEN 文字に切り詰める。
        """
        cleaned = re.sub(r"[。！？、，「」『』【】・…・＊※]", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # クエリが長すぎると精度が落ちるため先頭部分のみ使用
        return cleaned[:SEARCH_QUERY_MAX_LEN].strip()

    def _rank_fragments(self, fragments: List[TextFragment]) -> List[TextFragment]:
        """
        固有名詞・数字・特徴語を多く含むフレーズを優先する。
        スコアが高い順に返す。
        """
        def score(f: TextFragment) -> int:
            text = f.text
            pts = 0
            # 英数字・数字は特徴的な情報を含む可能性が高い
            pts += len(re.findall(r"[A-Za-z0-9０-９]{3,}", text)) * 3
            # カタカナ固有名詞（ツール名・サービス名など）
            pts += len(re.findall(r"[ァ-ヶー]{4,}", text)) * 2
            # 長いフレーズほど特定性が高い
            pts += min(len(text) // 10, 5)
            return pts

        return sorted(fragments, key=score, reverse=True)
