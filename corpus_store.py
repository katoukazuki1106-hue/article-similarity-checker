"""
corpus_store.py
媒体照合モード用の「過去1か月インデックス」を保存・取得する永続化レイヤ。

2実装を提供する:
- SqliteStore   … ローカル検証用（ファイル1個・依存ゼロ）
- SupabaseStore … 本番用（Supabase無料Postgres / PostgREST 経由・requestsのみ）

get_store() が環境変数を見て自動で切り替える:
  SUPABASE_URL と SUPABASE_KEY があれば SupabaseStore、無ければ SqliteStore。

テーブル/レコード共通スキーマ（articles）:
  url          TEXT  UNIQUE  … 一意キー（重複排除）
  media_name   TEXT          … 媒体名
  title        TEXT          … 記事タイトル
  published_at TEXT          … 公開日時 ISO8601（無ければ取得時刻）
  body_text    TEXT          … 本文プレーンテキスト（長さ上限あり）
  fetched_at   TEXT          … クロール取得時刻 ISO8601
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Article:
    media_name: str
    url: str
    title: str
    published_at: str
    body_text: str
    fetched_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# 基底クラス
# ---------------------------------------------------------------------------

class BaseCorpusStore:
    def upsert_article(self, article: Article) -> None:
        raise NotImplementedError

    def iter_recent_articles(self, days: int = 30) -> List[Article]:
        raise NotImplementedError

    def purge_old(self, days: int = 30) -> int:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def last_fetched_at(self) -> Optional[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# SQLite（ローカル検証用）
# ---------------------------------------------------------------------------

class SqliteStore(BaseCorpusStore):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("MEDIA_DB_PATH", "media_corpus.db")
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    url          TEXT PRIMARY KEY,
                    media_name   TEXT NOT NULL,
                    title        TEXT,
                    published_at TEXT,
                    body_text    TEXT,
                    fetched_at   TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_published_at ON articles(published_at)"
            )

    def upsert_article(self, article: Article) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO articles (url, media_name, title, published_at, body_text, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    media_name=excluded.media_name,
                    title=excluded.title,
                    published_at=excluded.published_at,
                    body_text=excluded.body_text,
                    fetched_at=excluded.fetched_at
                """,
                (
                    article.url,
                    article.media_name,
                    article.title,
                    article.published_at,
                    article.body_text,
                    article.fetched_at or _now_iso(),
                ),
            )

    def iter_recent_articles(self, days: int = 30) -> List[Article]:
        cutoff = _cutoff_iso(days)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            ).fetchall()
        return [self._row_to_article(r) for r in rows]

    def purge_old(self, days: int = 30) -> int:
        cutoff = _cutoff_iso(days)
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
            return cur.rowcount

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    def last_fetched_at(self) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute("SELECT MAX(fetched_at) FROM articles").fetchone()
        return row[0] if row else None

    @staticmethod
    def _row_to_article(r: sqlite3.Row) -> Article:
        return Article(
            media_name=r["media_name"],
            url=r["url"],
            title=r["title"] or "",
            published_at=r["published_at"] or "",
            body_text=r["body_text"] or "",
            fetched_at=r["fetched_at"] or "",
        )


# ---------------------------------------------------------------------------
# Supabase（本番用・PostgREST を requests で直叩き）
# ---------------------------------------------------------------------------

class SupabaseStore(BaseCorpusStore):
    """
    Supabase の REST API（PostgREST）経由で articles テーブルを操作する。
    事前にSupabase側で以下のテーブルを作成しておくこと:

        create table articles (
          url text primary key,
          media_name text not null,
          title text,
          published_at timestamptz,
          body_text text,
          fetched_at timestamptz
        );
        create index on articles (published_at);

    環境変数: SUPABASE_URL, SUPABASE_KEY（service_role 推奨）
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.base = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_KEY", "")
        if not self.base or not self.key:
            raise ValueError("[エラー] SUPABASE_URL / SUPABASE_KEY を設定してください。")
        self.endpoint = f"{self.base}/rest/v1/articles"

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {
            "apikey": self.key,
            "Content-Type": "application/json",
        }
        # 旧式キー(JWT・"eyJ"で始まる service_role/anon)は Authorization に載せると
        # PostgREST が role claim を読んで service_role に解決する。
        # 一方、新方式の secret キー(sb_secret_...)は JWT ではないため Authorization に
        # 載せるとユーザトークンとして解釈に失敗し anon に落ちて 403 になる。
        # secret キーは apikey だけで送れば Supabase 側が service_role に昇格させる。
        if self.key.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.key}"
        if extra:
            h.update(extra)
        return h

    def upsert_article(self, article: Article) -> None:
        import requests

        payload = {
            "url": article.url,
            "media_name": article.media_name,
            "title": article.title,
            "published_at": article.published_at,
            "body_text": article.body_text,
            "fetched_at": article.fetched_at or _now_iso(),
        }
        # on_conflict=url + merge-duplicates でupsert
        resp = requests.post(
            f"{self.endpoint}?on_conflict=url",
            headers=self._headers({"Prefer": "resolution=merge-duplicates"}),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()

    def iter_recent_articles(self, days: int = 30) -> List[Article]:
        import requests

        cutoff = _cutoff_iso(days)
        articles: List[Article] = []
        offset = 0
        page = 1000
        while True:
            params = {
                "select": "*",
                "published_at": f"gte.{cutoff}",
                "order": "published_at.desc",
                "limit": str(page),
                "offset": str(offset),
            }
            resp = requests.get(self.endpoint, headers=self._headers(), params=params, timeout=30)
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                break
            articles.extend(self._row_to_article(r) for r in rows)
            if len(rows) < page:
                break
            offset += page
        return articles

    def purge_old(self, days: int = 30) -> int:
        import requests

        cutoff = _cutoff_iso(days)
        # 日時の "+00:00" の "+" を素のURLに埋めると空白へ化け 400 になるため、
        # params 経由で渡して requests に確実にURLエンコードさせる。
        resp = requests.delete(
            self.endpoint,
            headers=self._headers({"Prefer": "return=representation"}),
            params={"published_at": f"lt.{cutoff}"},
            timeout=30,
        )
        resp.raise_for_status()
        try:
            return len(resp.json())
        except Exception:
            return -1

    def count(self) -> int:
        import requests

        resp = requests.get(
            self.endpoint,
            headers=self._headers({"Prefer": "count=exact", "Range": "0-0"}),
            params={"select": "url"},
            timeout=30,
        )
        resp.raise_for_status()
        # Content-Range: 0-0/1234 の形式から総数を取り出す
        content_range = resp.headers.get("Content-Range", "*/0")
        try:
            return int(content_range.split("/")[-1])
        except ValueError:
            return 0

    def last_fetched_at(self) -> Optional[str]:
        import requests

        resp = requests.get(
            self.endpoint,
            headers=self._headers(),
            params={"select": "fetched_at", "order": "fetched_at.desc", "limit": "1"},
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0]["fetched_at"] if rows else None

    @staticmethod
    def _row_to_article(r: dict) -> Article:
        return Article(
            media_name=r.get("media_name", ""),
            url=r.get("url", ""),
            title=r.get("title") or "",
            published_at=r.get("published_at") or "",
            body_text=r.get("body_text") or "",
            fetched_at=r.get("fetched_at") or "",
        )


# ---------------------------------------------------------------------------
# ファクトリ
# ---------------------------------------------------------------------------

def get_store() -> BaseCorpusStore:
    """
    SUPABASE_URL / SUPABASE_KEY があれば SupabaseStore、無ければ SqliteStore。
    """
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        return SupabaseStore()
    return SqliteStore()
