"""
crawler.py
媒体照合モード用の「過去1か月インデックス」を更新するクローラ。

各 enabled 媒体のRSSを巡回し、記事URL・タイトル・公開日・本文を取得して
corpus_store に upsert する。最後に30日より古い記事をパージし、
"ローリング過去1か月" インデックスを維持する。

実行:
  python crawler.py                # 全 enabled 媒体を巡回
  python crawler.py --media ナタリー  # 媒体名で1媒体だけ巡回（部分一致）
  python crawler.py --no-purge     # パージしない（検証用）

保存先は corpus_store.get_store() が自動選択（SupabaseかSQLite）。
"""

import argparse
import calendar
import gzip
import io
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import feedparser

from media_sources import MediaSource, enabled_sources
from corpus_store import Article, get_store, _now_iso
from page_fetcher import fetch_page_text, _HEADERS

# config（無ければ既定値）
try:
    from config import (
        MEDIA_INDEX_RECENT_DAYS,
        MEDIA_BODY_MAX_CHARS,
        CRAWL_POLITE_DELAY_SEC,
        CRAWL_MAX_ENTRIES_PER_FEED,
        SITEMAP_MAX_SUBS,
        SITEMAP_MAX_URLS_PER_MEDIA,
        SITEMAP_FETCH_RETRIES,
    )
except Exception:  # pragma: no cover
    MEDIA_INDEX_RECENT_DAYS = 30
    MEDIA_BODY_MAX_CHARS = 8000
    CRAWL_POLITE_DELAY_SEC = 1.0
    CRAWL_MAX_ENTRIES_PER_FEED = 100
    SITEMAP_MAX_SUBS = 4
    SITEMAP_MAX_URLS_PER_MEDIA = 80
    SITEMAP_FETCH_RETRIES = 3

# 日付不明エントリを「最古」として末尾に回すためのソート番兵
_DT_MIN = datetime.min.replace(tzinfo=timezone.utc)


def _entry_published_iso(entry) -> str:
    """feedparserエントリの公開日時をISO8601(UTC)で返す。無ければ現在時刻。"""
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            # feedparserはUTCのstruct_timeに正規化する
            dt = datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
            return dt.isoformat()
    return _now_iso()


def _discover_feeds(domain: str) -> List[str]:
    """媒体トップページから <link rel=alternate type=rss/atom> を探す（フォールバック）。"""
    import urllib.request

    found: List[str] = []
    for scheme in ("https://", "http://"):
        url = f"{scheme}{domain}/"
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read(200_000).decode("utf-8", errors="replace")
        except Exception:
            continue
        # <link ... type="application/rss+xml" ... href="...">（属性順不同に対応）
        for m in re.finditer(r"<link\b[^>]*>", html, flags=re.IGNORECASE):
            tag = m.group(0)
            if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.IGNORECASE):
                href = re.search(r'href=["\']([^"\']+)["\']', tag)
                if href:
                    link = href.group(1)
                    if link.startswith("/"):
                        link = f"{scheme}{domain}{link}"
                    found.append(link)
        if found:
            break
    return found


# ---------------------------------------------------------------------------
# サイトマップ取り込み（type="sitemap" 媒体・RSS未提供媒体の代替経路）
# ---------------------------------------------------------------------------

_URL_BLOCK = re.compile(r"<url\b.*?</url>", re.DOTALL | re.IGNORECASE)
_SITEMAP_BLOCK = re.compile(r"<sitemap\b.*?</sitemap>", re.DOTALL | re.IGNORECASE)


def _parse_iso(s: str) -> Optional[datetime]:
    """ISO8601文字列をUTC aware datetimeへ。失敗/空は None。"""
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _fetch_sitemap(url: str) -> str:
    """サイトマップXMLを取得（gzip自動展開・リトライ付き）。失敗時は空文字。"""
    last = ""
    for _ in range(SITEMAP_FETCH_RETRIES):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read(5_000_000)
            if url.endswith(".gz") or raw[:2] == b"\x1f\x8b":
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read(20_000_000)
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last = str(e)
            time.sleep(2)
    print(f"    [失敗] サイトマップ取得: {url} ({last[:60]})")
    return ""


def _extract_urlset(text: str) -> List[Tuple[str, Optional[datetime], str]]:
    """<urlset> から (記事URL, 公開日, タイトル) を抽出。
    公開日は news:publication_date を優先し、無ければ lastmod を使う。"""
    out: List[Tuple[str, Optional[datetime], str]] = []
    for blk in _URL_BLOCK.findall(text):
        loc = re.search(r"<loc>(.*?)</loc>", blk, re.DOTALL)
        if not loc:
            continue
        url = loc.group(1).strip()
        pub = re.search(r"<news:publication_date>(.*?)</news:publication_date>", blk, re.DOTALL)
        lm = re.search(r"<lastmod>(.*?)</lastmod>", blk, re.DOTALL)
        date = _parse_iso(pub.group(1) if pub else (lm.group(1) if lm else ""))
        t = re.search(r"<news:title>(.*?)</news:title>", blk, re.DOTALL)
        title = t.group(1).strip() if t else ""
        out.append((url, date, title))
    return out


def _trailing_int(s: str) -> int:
    """URL末尾の連番を取り出す（post-2026_53.xml → 53）。無ければ -1。
    サイトマップindexのlastmodが全サブ同一（index生成時刻）の媒体で、
    連番が新しい順を表すケース（ねとらぼ等）の正しい並べ替えに使う。"""
    nums = re.findall(r"(\d+)", s)
    return int(nums[-1]) if nums else -1


def _extract_index(text: str) -> List[Tuple[str, Optional[datetime]]]:
    """<sitemapindex> から (サブサイトマップURL, lastmod) を抽出。"""
    out: List[Tuple[str, Optional[datetime]]] = []
    for blk in _SITEMAP_BLOCK.findall(text):
        loc = re.search(r"<loc>(.*?)</loc>", blk, re.DOTALL)
        if not loc:
            continue
        lm = re.search(r"<lastmod>(.*?)</lastmod>", blk, re.DOTALL)
        out.append((loc.group(1).strip(), _parse_iso(lm.group(1) if lm else "")))
    return out


def _collect_sitemap_entries(media: MediaSource) -> List[Tuple[str, Optional[datetime], str]]:
    """サイトマップ媒体から記事候補 (URL, 公開日, タイトル) を集約。

    - sitemapindex なら sitemap_filter で絞り、新しい順に SITEMAP_MAX_SUBS 個だけ辿る
      （ねとらぼ post-2026_N のように番号が増え続けても最新サブを自動で拾える）。
    - 過去 MEDIA_INDEX_RECENT_DAYS 日に絞り、公開日が新しい順に
      SITEMAP_MAX_URLS_PER_MEDIA 件まで返す（日付不明は残す＝最古扱い）。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=MEDIA_INDEX_RECENT_DAYS)
    entries: dict = {}  # url -> (date, title) で重複排除

    for sm_url in media.sitemap_urls:
        text = _fetch_sitemap(sm_url)
        if not text:
            continue
        if "<sitemapindex" in text:
            subs = _extract_index(text)
            if media.sitemap_filter:
                subs = [(u, d) for (u, d) in subs if re.search(media.sitemap_filter, u)]
            # lastmod → 末尾連番 の順で新しい順に並べ、上位だけ辿る。
            # （lastmodが全サブ同一の媒体は連番で新旧を判定する＝ねとらぼ post-2026_N）
            subs.sort(key=lambda x: (x[1] or _DT_MIN, _trailing_int(x[0])), reverse=True)
            subs = subs[:SITEMAP_MAX_SUBS]
            print(f"    index {sm_url} → サブ{len(subs)}件を辿る")
            for sub_url, _ in subs:
                sub_text = _fetch_sitemap(sub_url)
                for u, d, t in _extract_urlset(sub_text):
                    entries[u] = (d, t)
                time.sleep(CRAWL_POLITE_DELAY_SEC)
        else:
            for u, d, t in _extract_urlset(text):
                entries[u] = (d, t)

    items = [(u, d, t) for u, (d, t) in entries.items() if (d is None or d >= cutoff)]
    items.sort(key=lambda x: (x[1] or _DT_MIN), reverse=True)
    items = items[:SITEMAP_MAX_URLS_PER_MEDIA]
    print(f"    記事候補 {len(items)}件（過去{MEDIA_INDEX_RECENT_DAYS}日・上限{SITEMAP_MAX_URLS_PER_MEDIA}）")
    return items


def _collect_feed_entries(media: MediaSource) -> list:
    """媒体の全 feed_urls をパースしてエントリを集約。0件ならautodiscovery。"""
    entries = []
    for feed_url in media.feed_urls:
        parsed = feedparser.parse(feed_url)
        if parsed.entries:
            entries.extend(parsed.entries[:CRAWL_MAX_ENTRIES_PER_FEED])
            print(f"    [OK] {feed_url} … {len(parsed.entries)}件")
        else:
            print(f"    [空] {feed_url}（entries=0）")

    if not entries:
        print(f"    → autodiscovery を試行: {media.domain}")
        for disc in _discover_feeds(media.domain):
            parsed = feedparser.parse(disc)
            if parsed.entries:
                entries.extend(parsed.entries[:CRAWL_MAX_ENTRIES_PER_FEED])
                print(f"    [OK*] {disc} … {len(parsed.entries)}件")
    return entries


def _collect_records(media: MediaSource) -> List[Tuple[str, str, str, str]]:
    """媒体種別に応じて (URL, タイトル, 公開日ISO, 本文フォールバック) のリストを返す。

    RSS媒体はfeedparserエントリから、サイトマップ媒体は記事サイトマップから生成する。
    どちらも以降の本文取得ループが同じ形で扱えるよう正規化する。
    """
    if media.type == "sitemap":
        records = []
        for url, date, title in _collect_sitemap_entries(media):
            published = date.isoformat() if date else _now_iso()
            records.append((url, title, published, ""))  # サイトマップにsummaryは無い
        return records

    # RSS（従来通り）
    records = []
    for e in _collect_feed_entries(media):
        url = (e.get("link", "") or "").strip()
        title = (e.get("title", "") or "").strip()
        published = _entry_published_iso(e)
        summary = re.sub(r"<[^>]+>", " ", e.get("summary", "") or "").strip()
        records.append((url, title, published, summary))
    return records


def crawl_media(media: MediaSource, store) -> int:
    """1媒体を巡回してupsert。新規/更新した件数を返す。"""
    print(f"[{media.name}] 巡回開始（{media.type}）")
    records = _collect_records(media)
    if not records:
        print(f"[{media.name}] エントリを取得できませんでした。")
        return 0

    saved = 0
    seen_urls = set()
    for url, title, published, summary in records:
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        body = fetch_page_text(url)
        if not body:
            # 本文取得失敗時はRSSのsummaryで代替（あれば。サイトマップは空）
            body = summary
        if not body:
            continue
        body = body[:MEDIA_BODY_MAX_CHARS]

        store.upsert_article(Article(
            media_name=media.name,
            url=url,
            title=title,
            published_at=published,
            body_text=body,
            fetched_at=_now_iso(),
        ))
        saved += 1
        time.sleep(CRAWL_POLITE_DELAY_SEC)  # 礼儀正しく巡回

    print(f"[{media.name}] {saved}件 保存/更新")
    return saved


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="媒体照合インデックス更新クローラ")
    parser.add_argument("--media", help="媒体名で1媒体だけ巡回（部分一致）")
    parser.add_argument("--no-purge", action="store_true", help="30日パージをスキップ")
    args = parser.parse_args(argv)

    store = get_store()
    print(f"保存先: {type(store).__name__}")

    sources = enabled_sources()
    if args.media:
        sources = [m for m in sources if args.media in m.name]
        if not sources:
            print(f"[警告] '{args.media}' に一致する有効な媒体がありません。")
            return 1

    total = 0
    for media in sources:
        try:
            total += crawl_media(media, store)
        except Exception as e:
            print(f"[エラー] {media.name} の巡回に失敗: {e}")

    if not args.no_purge:
        removed = store.purge_old(MEDIA_INDEX_RECENT_DAYS)
        print(f"パージ: {removed}件削除（{MEDIA_INDEX_RECENT_DAYS}日より古い記事）")

    print(f"完了: 合計{total}件 保存/更新 / 収録総数 {store.count()}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
