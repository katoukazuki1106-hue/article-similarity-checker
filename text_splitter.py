"""
text_splitter.py
記事本文を段落・文・チェック対象フレーズに分割する。
日本語記事を想定。
"""

import re
from dataclasses import dataclass
from typing import List

from config import (
    MIN_TEXT_LENGTH,
    MAX_PHRASE_LENGTH,
    IGNORED_PHRASES,
)


@dataclass
class TextFragment:
    """チェック対象フレーズの単位"""
    text: str
    paragraph_index: int


class TextSplitter:

    def split_paragraphs(self, text: str) -> List[str]:
        """空行・改行で段落に分割し、最小文字数未満は除外する。"""
        raw = re.split(r"\n{2,}|\n", text)
        return [p.strip() for p in raw if len(p.strip()) >= MIN_TEXT_LENGTH]

    def split_sentences(self, text: str) -> List[str]:
        """。！？ で文に分割し、長文は読点でさらに分割する。"""
        # 句点・感嘆符・疑問符の後ろで分割（区切り文字はそのまま残す）
        raw = re.split(r"(?<=[。！？])", text)
        result = []
        for sentence in raw:
            sentence = sentence.strip()
            if len(sentence) < MIN_TEXT_LENGTH:
                continue
            if len(sentence) > MAX_PHRASE_LENGTH:
                result.extend(self._split_long_sentence(sentence))
            else:
                result.append(sentence)
        return result

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """MAX_PHRASE_LENGTH 超の文を読点・カンマで分割する。"""
        parts = re.split(r"(?<=[、,，])", sentence)
        chunks: List[str] = []
        current = ""
        for part in parts:
            if len(current) + len(part) > MAX_PHRASE_LENGTH and current:
                chunks.append(current.strip())
                current = part
            else:
                current += part
        if current.strip():
            chunks.append(current.strip())
        return [c for c in chunks if len(c) >= MIN_TEXT_LENGTH]

    def extract_check_phrases(self, text: str) -> List[TextFragment]:
        """
        チェック対象フレーズを抽出する。
        - 最小文字数未満は除外
        - 一般的すぎる短文は除外
        """
        paragraphs = self.split_paragraphs(text)
        fragments: List[TextFragment] = []

        for para_idx, para in enumerate(paragraphs):
            for sentence in self.split_sentences(para):
                if self._should_skip(sentence):
                    continue
                fragments.append(TextFragment(
                    text=sentence,
                    paragraph_index=para_idx,
                ))

        return fragments

    def _should_skip(self, text: str) -> bool:
        """IGNORED_PHRASES に完全一致・または前方一致する場合はスキップ。"""
        stripped = text.strip()
        for phrase in IGNORED_PHRASES:
            if stripped == phrase or stripped.startswith(phrase):
                return True
        return False
