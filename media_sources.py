"""
media_sources.py
媒体照合モードで巡回する媒体レジストリ。

媒体の追加・差し替え・有効化はこのファイルだけ編集すればよい。
- enabled=True の媒体だけクローラが巡回する（フェーズ1は代表5媒体のみTrue）。
- feed_urls は複数指定可（媒体内のカテゴリ別RSSなど）。
- feed_urls が空 or 取得失敗時、crawler が media のトップページからRSSを
  自動探索（autodiscovery）するため、URLが多少ずれていても拾える設計。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class MediaSource:
    name: str                       # 媒体名（表示用）
    domain: str                     # 代表ドメイン（自動探索の起点・所属判定にも使用）
    feed_urls: List[str] = field(default_factory=list)  # RSS/AtomフィードURL
    type: str = "rss"               # "rss" or "sitemap"（RSS未提供媒体はサイトマップから取得）
    enabled: bool = True            # クロール対象にするか
    # --- type="sitemap" 用 ---
    sitemap_urls: List[str] = field(default_factory=list)  # 起点サイトマップ（index可）
    sitemap_filter: str = ""        # サイトマップindexを辿る時、サブのlocをこの正規表現で絞る
                                    # （例: post-2026_ で記事サイトマップだけ拾う。空=全サブ）


# ---------------------------------------------------------------------------
# 媒体レジストリ（20媒体）
# enabled=True（13媒体・2026-06-18）:
#   [RSS・11媒体] ナタリー / ライブドア / ガジェット通信 / ENCOUNT / マイナビ /
#     リアルサウンド / billboard JAPAN / シネマトゥデイ / BARKS / エンタのおはなし / WWSチャンネル
#   [サイトマップ・2媒体] ねとらぼ(post-2026_N) / モデルプレス(Google News)
# enabled=False（7媒体・サイトマップ取り込み不可 or 不安定）:
#   オリコン(記事が429で不安定) / 映画.com(news.xml.gzが403) / TRILL(日付無し18747件) /
#   クランクイン(SM未特定) / WEBザテレビジョン(セクションのみ) / Yahoo・LINE(アグリゲータ)
# ---------------------------------------------------------------------------

MEDIA_SOURCES: List[MediaSource] = [
    # --- フェーズ1: 稼働確認済み5媒体（enabled=True）---
    MediaSource(
        name="ナタリー",
        domain="natalie.mu",
        feed_urls=[
            "https://natalie.mu/music/feed/news",
            "https://natalie.mu/eiga/feed/news",
            "https://natalie.mu/owarai/feed/news",
        ],
        enabled=True,  # 30件/フィード。公開日フィールド無し→取得時刻で代替
    ),
    MediaSource(
        name="ライブドアニュース",
        domain="news.livedoor.com",
        feed_urls=[
            "https://news.livedoor.com/topics/rss/ent.xml",
        ],
        enabled=True,  # 公開日あり
    ),
    MediaSource(
        name="ガジェット通信", domain="getnews.jp",
        feed_urls=["https://getnews.jp/feed"],
        enabled=True,  # WordPress /feed・公開日あり
    ),
    MediaSource(
        name="ENCOUNT", domain="encount.press",
        feed_urls=["https://encount.press/feed"],
        enabled=True,  # WordPress /feed・公開日あり
    ),
    MediaSource(
        name="マイナビニュース", domain="news.mynavi.jp",
        feed_urls=["https://news.mynavi.jp/rss/index"],
        enabled=True,  # 50件。公開日フィールド無し→取得時刻で代替
    ),

    # --- サイトマップ取り込み（2026-06-18・type="sitemap"）---
    MediaSource(
        name="オリコンニュース", domain="oricon.co.jp",
        # news-sitemap自体は取得可・URL/lastmodも正常だが、記事ページが 429 Too Many
        # Requests を強めに返し（1秒間隔でも約25%失敗・叩くとIP単位で一定時間ブロック）、
        # 80件の安定取得が困難。fetch_delayを十分長くすれば復活可能だが当面は保留。
        feed_urls=[], type="sitemap", enabled=False,
        sitemap_urls=["https://www.oricon.co.jp/sitemap/sitemap_news_index.xml"],
    ),
    MediaSource(
        name="ねとらぼ", domain="nlab.itmedia.co.jp",
        # 旧netlab.xmlはstale。汎用サイトマップindexから post-2026_N.xml（記事・lastmodあり）
        # だけを正規表現で絞り、新しいサブ数件を辿る（Nは増え続けるので動的に最新を拾う）。
        feed_urls=[], type="sitemap", enabled=True,
        sitemap_urls=["https://nlab.itmedia.co.jp/sitemap/sitemap.xml"],
        sitemap_filter=r"/post-2026_\d+\.xml",
    ),
    MediaSource(
        name="映画.com", domain="eiga.com",
        # news.xml.gz がサイトマップ取得時に403でブロックされる（2026-06-18）。当面保留。
        feed_urls=[], type="sitemap", enabled=False,
        sitemap_urls=["https://eiga.com/sitemap/news.xml.gz"],
    ),

    # --- フェーズ2追加: 稼働確認済み6媒体（2026-06-18・enabled=True）---
    MediaSource(
        name="リアルサウンド", domain="realsound.jp",
        feed_urls=["https://realsound.jp/atom.xml"], enabled=True,  # Atom・公開日あり
    ),
    MediaSource(
        name="billboard JAPAN", domain="billboard-japan.com",
        feed_urls=["https://www.billboard-japan.com/d_news/doc.xml"], enabled=True,  # 公開日あり
    ),
    MediaSource(
        name="シネマトゥデイ", domain="cinematoday.jp",
        feed_urls=["https://www.cinematoday.jp/index.xml"], enabled=True,  # 公開日あり
    ),
    MediaSource(
        name="BARKS", domain="barks.jp",
        feed_urls=["https://www.barks.jp/feed"], enabled=True,  # WordPress・公開日あり
    ),
    MediaSource(
        name="エンタのおはなし", domain="entametalk.com",
        feed_urls=["https://entametalk.com/feed/"], enabled=True,  # WordPress・公開日あり
    ),
    MediaSource(
        name="WWSチャンネル", domain="wws-channel.com",
        feed_urls=["https://www.wws-channel.com/feed"], enabled=True,  # 50件・公開日あり
    ),

    # --- RSS未提供で保留（SPA/アプリ型等・将来サイトマップ対応・enabled=False）---
    # 2026-06-18: feed/atom/index/autodiscovery いずれも取得不可を確認済み。
    MediaSource(
        name="モデルプレス", domain="mdpr.jp",
        # Googleニュースサイトマップ（news:publication_date・news:title付き・約174件）。
        feed_urls=[], type="sitemap", enabled=True,
        sitemap_urls=["https://mdpr.jp/rss/google_news_sitemap.xml"],
    ),
    MediaSource(
        name="TRILL", domain="trilltrill.jp",
        # article.xml.gz は18747件・日付フィールド無しで過去1か月に絞れない。保留。
        feed_urls=[], type="sitemap", enabled=False,
        sitemap_urls=["https://trilltrill.jp/sitemap/article.xml.gz"],
    ),
    MediaSource(
        name="クランクイン！", domain="crank-in.net",
        # robots.txt取得不可・サイトマップ未特定。保留。
        feed_urls=[], type="sitemap", enabled=False,
    ),
    MediaSource(
        name="WEBザ・テレビジョン", domain="thetv.jp",
        # サイトマップはセクションページのみで記事URL粒度が取れない。保留。
        feed_urls=[], type="sitemap", enabled=False,
    ),
    # Yahoo!ニュース・LINEニュースはRSSが弱く、他媒体の配信先（アグリゲータ）。
    # 元媒体側で実質捕捉できるため、当面はベストエフォート（保留）。
    MediaSource(
        name="Yahoo!ニュース", domain="news.yahoo.co.jp",
        feed_urls=[], type="sitemap", enabled=False,
    ),
    MediaSource(
        name="LINEニュース", domain="news.line.me",
        feed_urls=[], type="sitemap", enabled=False,
    ),
]


def enabled_sources() -> List[MediaSource]:
    """クロール対象（enabled=True）の媒体だけ返す。"""
    return [m for m in MEDIA_SOURCES if m.enabled]
