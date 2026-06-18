"""
search_client.py
検索処理を担当するクライアント群。

初期実装: MockSearchClient（APIキー不要・テスト用）
将来的に GoogleSearchClient / BingSearchClient / SerpApiClient へ差し替え可能。
"""

import os
import random
import re
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    media_name: str = ""      # 媒体照合モードで使用（媒体名）
    published_at: str = ""    # 媒体照合モードで使用（公開日時 ISO8601）


# ---------------------------------------------------------------------------
# 基底クラス（インターフェース定義）
# ---------------------------------------------------------------------------

class BaseSearchClient:
    """全検索クライアントが継承する基底クラス。"""

    def search(self, query: str) -> List[SearchResult]:
        raise NotImplementedError("search() を実装してください。")


# ---------------------------------------------------------------------------
# モッククライアント（API不要・ローカルのみで動作）
# ---------------------------------------------------------------------------

# モック用の架空Web記事データベース
# 「実在記事の無断引用を避けるため、すべて架空のテスト用文章」
_MOCK_DB = [
    {
        "title": "SEO対策の基本と仕組み｜初心者向け完全ガイド",
        "url": "https://example-seo-guide.jp/basics",
        "snippets": [
            "SEOとは、Search Engine Optimizationの略で、検索エンジン最適化のことを指します。"
            "Googleをはじめとする検索エンジンで自社サイトを上位表示させるための技術や施策を総称したものです。",
            "検索エンジンは、クローラーと呼ばれるプログラムがWebページを巡回し、"
            "情報を収集・インデックス化することで機能しています。このプロセスを理解することがSEO対策の第一歩です。",
            "上位表示されるためには、コンテンツの品質向上・内部リンクの整備・外部リンクの獲得の3要素が重要です。",
        ],
    },
    {
        "title": "コンテンツマーケティング入門｜基本戦略と実践方法",
        "url": "https://content-marketing-lab.example.com/intro",
        "snippets": [
            "コンテンツマーケティングとは、ターゲットユーザーにとって有益なコンテンツを継続的に発信することで、"
            "潜在顧客を引き付け、最終的に収益につなげるマーケティング手法です。",
            "質の高いコンテンツを定期的に公開することで、検索エンジンからの自然流入を増やすことができます。"
            "特にロングテールキーワードを狙った記事は、競合が少なく成果を出しやすい傾向があります。",
            "読者の悩みを解決する記事を書き続けることが、長期的なブランド構築につながります。",
        ],
    },
    {
        "title": "キーワード調査の方法と選定基準｜SEO担当者向けマニュアル",
        "url": "https://keyword-research.example.net/guide",
        "snippets": [
            "キーワード調査とは、ユーザーが検索エンジンに入力する言葉を調査・分析する作業です。"
            "適切なキーワードを選定することで、ターゲットとなるユーザーにリーチしやすくなります。",
            "検索ボリュームが多すぎるキーワードは競合が激しく、新規サイトでは上位表示が困難です。"
            "まずは月間1,000〜5,000程度の中規模キーワードから着手するのが現実的な戦略です。",
            "ユーザーの検索意図（サーチインテント）を理解した上でキーワードを選ぶことが重要です。",
        ],
    },
    {
        "title": "内部リンク最適化｜Webサイトの回遊率を高める設計方法",
        "url": "https://internal-link-seo.example.org/optimize",
        "snippets": [
            "内部リンクを適切に設計することで、クローラーのサイト巡回効率が上がり、"
            "重要なページへの評価が集中しやすくなります。",
            "アンカーテキストにはリンク先の内容を端的に表す言葉を使用することが推奨されます。"
            "「こちら」「詳しくは」などの曖昧な表現は避けましょう。",
        ],
    },
    {
        "title": "Webライティングの基本｜読まれる記事の書き方",
        "url": "https://web-writing-tips.example.jp/basic",
        "snippets": [
            "Web上で読まれる記事を書くためには、まず結論を冒頭に提示することが重要です。"
            "ユーザーはスクロールせずに情報を得たいと考えており、最初の数行で価値を伝える必要があります。",
            "見出しは記事全体の構成を示すナビゲーションとして機能します。"
            "H2・H3を適切に使い分けることで、読者が目的の情報にたどり着きやすくなります。",
            "文章は短く、一文一義を心がけましょう。長い文章は読者の離脱を招く原因となります。",
        ],
    },
]


class MockSearchClient(BaseSearchClient):
    """
    テスト用のモック検索クライアント。
    APIキーなしでローカル完結で動作する。
    クエリに含まれるキーワードをもとに、モックDBから関連スニペットを返す。
    """

    def search(self, query: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        query_lower = query.lower()

        for article in _MOCK_DB:
            score = self._relevance_score(query_lower, article)
            if score > 0:
                # 関連スニペットを最大2件選択
                for snippet in article["snippets"][:2]:
                    results.append(SearchResult(
                        title=article["title"],
                        url=article["url"],
                        snippet=snippet,
                    ))

        # スコアが低い場合でも最低1件は返す（クエリを含む汎用スニペット）
        if not results:
            results.append(self._generic_result(query))

        return results

    def _relevance_score(self, query: str, article: dict) -> int:
        """クエリとarticleのキーワード一致数でスコアを算出する。"""
        keywords = re.findall(r"[\w぀-ヿ一-鿿]{2,}", query)
        score = 0
        combined = article["title"] + " ".join(article["snippets"])
        for kw in keywords:
            if kw in combined:
                score += 1
        return score

    def _generic_result(self, query: str) -> SearchResult:
        """どのarticleにもヒットしなかった場合の汎用ダミー結果。"""
        return SearchResult(
            title="Web記事（モック）",
            url="https://example.com/mock-article",
            snippet=f"このトピックに関する情報は多数のWebサイトで公開されています。{query[:30]}",
        )


# ---------------------------------------------------------------------------
# 将来実装：Google Custom Search API
# ---------------------------------------------------------------------------

class GoogleSearchClient(BaseSearchClient):
    """
    Google Custom Search API を使った検索クライアント。
    .env に GOOGLE_API_KEY と GOOGLE_SEARCH_ENGINE_ID を設定して使用する。
    """

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        if not self.api_key or not self.engine_id:
            raise ValueError(
                "[エラー] .env に GOOGLE_API_KEY と GOOGLE_SEARCH_ENGINE_ID を設定してください。"
            )

    def search(self, query: str) -> List[SearchResult]:
        import requests
        from page_fetcher import fetch_page_text

        api_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": query,
            "num": 3,
        }
        try:
            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"[警告] Google検索API呼び出し失敗: {e}")
            return []

        results = []
        for item in data.get("items", []):
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            # ページ全文を取得してスニペットの代わりに使用（失敗時はスニペットで代替）
            full_text = fetch_page_text(link)
            results.append(SearchResult(
                title=item.get("title", ""),
                url=link,
                snippet=full_text if full_text else snippet,
            ))
        return results


# ---------------------------------------------------------------------------
# DuckDuckGo検索（APIキー不要・Web全体検索）
# ---------------------------------------------------------------------------

class DuckDuckGoSearchClient(BaseSearchClient):
    """
    DuckDuckGo検索クライアント。APIキー不要でWeb全体を検索できる。
    """

    def search(self, query: str) -> List[SearchResult]:
        from page_fetcher import fetch_page_text
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=3):
                    url = r.get("href", "")
                    snippet = r.get("body", "")
                    full_text = fetch_page_text(url)
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=url,
                        snippet=full_text if full_text else snippet,
                    ))
        except Exception as e:
            print(f"[警告] DuckDuckGo検索失敗: {e}")
        return results


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------

class BraveSearchClient(BaseSearchClient):
    """
    Brave Search API を使った検索クライアント。
    .env に BRAVE_SEARCH_API_KEY を設定して使用する。
    """

    def __init__(self):
        self.api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not self.api_key:
            raise ValueError("[エラー] .env に BRAVE_SEARCH_API_KEY を設定してください。")

    def search(self, query: str) -> List[SearchResult]:
        import requests

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": 5,
            "text_decorations": False,
        }
        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"[警告] Brave検索API呼び出し失敗: {e}")
            return []

        results = []
        for item in data.get("web", {}).get("results", []):
            # ページ全文取得はノイズが多いためBraveスニペットをそのまま使用
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
            ))
        return results


# ---------------------------------------------------------------------------
# 媒体照合モード：指定媒体・過去1か月インデックスとローカル照合
# ---------------------------------------------------------------------------

class MediaIndexSearchClient(BaseSearchClient):
    """
    corpus_store に貯めた「指定媒体・過去1か月」の記事コーパスを
    ローカルで照合する検索クライアント。

    - 生成時にコーパスを1回だけメモリにロードし、文字trigramの転置インデックスを構築。
    - search(query) はtrigram重なりで候補記事を素早く絞り、上位K件を返す。
    - 返すSearchResultのsnippetは記事本文（全体）なので、既存のSimilarityChecker
      （fuzz.partial_ratio）がそのまま最良部分一致を拾える＝Checker無改修。
    検索ランキング非依存のため、同じ入力には常に同じ結果（再現性が高い）。
    """

    def __init__(self, store=None, recent_days: Optional[int] = None):
        from corpus_store import get_store
        try:
            from config import (
                MEDIA_INDEX_RECENT_DAYS,
                MEDIA_CANDIDATE_TOP_K,
                MEDIA_TRIGRAM_MIN_OVERLAP,
            )
        except Exception:
            MEDIA_INDEX_RECENT_DAYS, MEDIA_CANDIDATE_TOP_K, MEDIA_TRIGRAM_MIN_OVERLAP = 30, 8, 3

        self.top_k = MEDIA_CANDIDATE_TOP_K
        self.min_overlap = MEDIA_TRIGRAM_MIN_OVERLAP
        self.store = store or get_store()
        self.articles = self.store.iter_recent_articles(
            recent_days if recent_days is not None else MEDIA_INDEX_RECENT_DAYS
        )
        # trigram転置インデックス: trigram -> 記事インデックスのリスト
        self._inverted: dict = {}
        for idx, art in enumerate(self.articles):
            for g in self._trigrams(art.body_text):
                self._inverted.setdefault(g, []).append(idx)

    @staticmethod
    def _normalize(text: str) -> str:
        """照合候補絞り込み用の正規化（NFKC・小文字化・記号/空白除去）。"""
        import unicodedata
        text = unicodedata.normalize("NFKC", text).lower()
        # 英数・ひらがな・カタカナ・漢字以外を除去
        return re.sub(r"[^0-9a-z぀-ヿ一-鿿]", "", text)

    def _trigrams(self, text: str) -> set:
        norm = self._normalize(text)
        if len(norm) < 3:
            return set()
        return {norm[i:i + 3] for i in range(len(norm) - 2)}

    def search(self, query: str) -> List[SearchResult]:
        if not self.articles:
            return []

        qgrams = self._trigrams(query)
        if not qgrams:
            return []

        # 転置インデックスで候補記事の重なり数を集計
        overlap: dict = {}
        for g in qgrams:
            for idx in self._inverted.get(g, ()):  # 該当trigramを含む記事
                overlap[idx] = overlap.get(idx, 0) + 1

        # 重なりが閾値以上の候補を上位K件
        candidates = sorted(
            (i for i, c in overlap.items() if c >= self.min_overlap),
            key=lambda i: overlap[i],
            reverse=True,
        )[: self.top_k]

        results: List[SearchResult] = []
        for idx in candidates:
            art = self.articles[idx]
            results.append(SearchResult(
                title=art.title,
                url=art.url,
                snippet=art.body_text,
                media_name=art.media_name,
                published_at=art.published_at,
            ))
        return results


# ---------------------------------------------------------------------------
# 将来実装：Bing Web Search API
# ---------------------------------------------------------------------------

class BingSearchClient(BaseSearchClient):
    """
    Bing Web Search API を使った検索クライアント。
    .env に BING_SEARCH_API_KEY を設定して使用する。
    """

    def __init__(self):
        self.api_key = os.getenv("BING_SEARCH_API_KEY")
        if not self.api_key:
            raise ValueError("[エラー] .env に BING_SEARCH_API_KEY を設定してください。")

    def search(self, query: str) -> List[SearchResult]:
        # TODO: requests を使った実装
        raise NotImplementedError("Bing Web Search API の実装は将来対応予定です。")


# ---------------------------------------------------------------------------
# 将来実装：SerpAPI
# ---------------------------------------------------------------------------

class SerpApiClient(BaseSearchClient):
    """
    SerpAPI を使った検索クライアント。
    .env に SERPAPI_KEY を設定して使用する。
    """

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY")
        if not self.api_key:
            raise ValueError("[エラー] .env に SERPAPI_KEY を設定してください。")

    def search(self, query: str) -> List[SearchResult]:
        # TODO: serpapi ライブラリを使った実装
        raise NotImplementedError("SerpAPI の実装は将来対応予定です。")


# ---------------------------------------------------------------------------
# クライアントファクトリ
# ---------------------------------------------------------------------------

def get_search_client(use_mock: bool = True, media_mode: bool = False) -> BaseSearchClient:
    """
    media_mode=True → MediaIndexSearchClient（指定媒体・過去1か月インデックスと照合）
    use_mock=True   → MockSearchClient（APIキー不要）
    use_mock=False  → BraveSearchClient（BRAVE_SEARCH_API_KEY が必要）

    優先度: media_mode > use_mock。
    """
    if media_mode:
        return MediaIndexSearchClient()

    if use_mock:
        return MockSearchClient()

    return BraveSearchClient()
