"""
page_fetcher.py
検索結果のURLからページ全文テキストを取得する。
スニペット（160文字）ではなく全文と照合することで検出精度を向上させる。
"""

import re
import urllib.request
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


def fetch_page_text(url: str, timeout: int = 8) -> Optional[str]:
    """
    URLのページを取得してプレーンテキストを返す。
    取得失敗時は None を返す。
    """
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = _detect_charset(resp.headers.get_content_charset())
            raw = resp.read(MAX_FETCH_CHARS * 3)  # バイト数に余裕を持って読む
        html = raw.decode(charset, errors="replace")
        return _html_to_text(html)[:MAX_FETCH_CHARS]
    except Exception:
        return None


def _detect_charset(declared: Optional[str]) -> str:
    if declared:
        return declared
    return "utf-8"


def _html_to_text(html: str) -> str:
    """HTMLタグを除去してプレーンテキストを抽出する。"""
    # script / style ブロックを丸ごと削除
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # タグ除去
    text = re.sub(r"<[^>]+>", " ", html)
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
