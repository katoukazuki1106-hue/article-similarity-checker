"""
page_fetcher.py
検索結果のURLからページ全文テキストを取得する。
スニペット（160文字）ではなく全文と照合することで検出精度を向上させる。
"""

import gzip
import io
import re
import urllib.request
import zlib
from typing import Optional


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 取得する最大文字数（長すぎると処理が重くなるため）
MAX_FETCH_CHARS = 30_000
# 生HTMLを読むバイト数。WordPress等はheadに巨大なインラインCSSがあり、
# その後ろに本文が来るため、十分大きく読まないと本文ごと切り落としてしまう。
RAW_FETCH_BYTES = 800_000


def fetch_page_text(url: str, timeout: int = 8) -> Optional[str]:
    """
    URLのページを取得してプレーンテキストを返す。
    取得失敗時は None を返す。
    """
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = _detect_charset(resp.headers.get_content_charset())
            encoding = (resp.headers.get("Content-Encoding") or "").lower()
            raw = resp.read(RAW_FETCH_BYTES)
        raw = _decompress(raw, encoding)
        html = raw.decode(charset, errors="replace")
        return _html_to_text(html)[:MAX_FETCH_CHARS]
    except Exception:
        return None


def _decompress(raw: bytes, encoding: str) -> bytes:
    """Content-Encoding（gzip/deflate）やgzipマジックバイトを見て本文を展開する。
    一部の媒体（mdpr等）は Accept-Encoding を送っていなくても gzip で返すため、
    展開しないと本文が文字化けして取得失敗扱いになる。
    RAW_FETCH_BYTES で途中まで読んだ圧縮ストリームでも、展開できた分は返す。"""
    is_gzip = encoding == "gzip" or raw[:2] == b"\x1f\x8b"
    if is_gzip:
        out = io.BytesIO()
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
                while True:
                    chunk = gz.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
        except Exception:
            pass  # 末尾が切れていても、ここまで展開できた分を使う
        data = out.getvalue()
        return data if data else raw
    if encoding == "deflate":
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompressobj(wbits).decompress(raw)
            except Exception:
                continue
    return raw


def _detect_charset(declared: Optional[str]) -> str:
    if declared:
        return declared
    return "utf-8"


def _html_to_text(html: str) -> str:
    """HTMLタグを除去してプレーンテキストを抽出する。"""
    # script / style / noscript ブロックを丸ごと削除
    html = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        " ", html, flags=re.DOTALL | re.IGNORECASE,
    )
    # 閉じタグが読み込み範囲外で未閉鎖になった script/style は末尾まで削除
    html = re.sub(r"<(script|style)[^>]*>.*", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # タグ除去
    text = re.sub(r"<[^>]+>", " ", html)
    # NUL・制御文字の除去（改行/タブは下の空白整理で吸収）。
    # 一部媒体（ITmedia系）の本文にNUL(\x00)が混じり、SQLiteのlength()が途中で
    # 止まったり、Postgres(Supabase)がNUL文字を含む文字列を拒否する不具合を防ぐ。
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # 残存CSSルール（.wp-block-…{…} 等）の除去。日本語本文に { } はほぼ出ないため安全。
    text = re.sub(r"@[a-z-]+[^{};]*\{[^{}]*\}", " ", text, flags=re.IGNORECASE)  # @media等
    text = re.sub(r"[^{}<>]{0,120}\{[^{}]*\}", " ", text)                        # セレクタ{宣言}
    # HTML実体参照の簡易デコード
    text = (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
            .replace("&#160;", " "))
    # 連続空白・改行を整理
    text = re.sub(r"\s+", " ", text).strip()
    return text
