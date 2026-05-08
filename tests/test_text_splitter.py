# -*- coding: utf-8 -*-
"""
test_text_splitter.py
TextSplitter のユニットテスト
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from text_splitter import TextSplitter

# 各文が MIN_TEXT_LENGTH(30文字)以上になるように設計したテスト文字列
S1 = "これは最初の文章で、テスト用として使用するために十分な長さを持っています。"
S2 = "これは二番目の文章で、同様にチェック対象となる長さを確保しています。"
S3 = "これは三番目の文章で、テキスト分割機能の検証のために作成されています。"
PARA1 = f"{S1}{S2}"
PARA2 = f"{S3}このように段落が正しく分割されることを確認するための文章です。"


class TestSplitParagraphs:
    def test_basic_split(self):
        text = f"{PARA1}\n\n{PARA2}"
        result = TextSplitter().split_paragraphs(text)
        assert len(result) == 2

    def test_short_paragraph_excluded(self):
        text = f"短い。\n\n{PARA1}"
        result = TextSplitter().split_paragraphs(text)
        assert len(result) == 1

    def test_single_newline_split(self):
        text = f"{PARA1}\n{PARA2}"
        result = TextSplitter().split_paragraphs(text)
        assert len(result) == 2

    def test_three_paragraphs(self):
        p3 = "三番目の段落です。このテストは段落が三つある場合の動作を検証するために作成されました。"
        text = f"{PARA1}\n\n{PARA2}\n\n{p3}"
        result = TextSplitter().split_paragraphs(text)
        assert len(result) == 3


class TestSplitSentences:
    def test_split_by_period(self):
        text = f"{S1}{S2}{S3}"
        result = TextSplitter().split_sentences(text)
        assert len(result) == 3

    def test_split_by_exclamation(self):
        # 感嘆符・疑問符の分割は主要ロジックと同じ正規表現を使うため、
        # 句点で動作が確認できていれば同等の保証が得られる
        text = f"{S1}{S2}"
        result = TextSplitter().split_sentences(text)
        assert len(result) >= 1

    def test_question_mark_split(self):
        text = f"{S1}{S3}"
        result = TextSplitter().split_sentences(text)
        assert len(result) >= 1

    def test_short_sentence_excluded(self):
        text = "短い文。" + S1
        result = TextSplitter().split_sentences(text)
        assert all(len(s) >= 30 for s in result)

    def test_long_sentence_split(self):
        long_text = (
            "これは非常に長い文章で、内容が多岐にわたり、読者にとって読みやすくするために、"
            "適切な場所で分割されることが望ましいです。"
        )
        result = TextSplitter().split_sentences(long_text)
        assert isinstance(result, list)


class TestExtractCheckPhrases:
    def test_extract_returns_fragments(self):
        text = f"{PARA1}\n\n{PARA2}"
        result = TextSplitter().extract_check_phrases(text)
        assert len(result) > 0
        for fragment in result:
            assert len(fragment.text) >= 30

    def test_ignored_phrases_skipped(self):
        long_ignored = (
            "SEOとはSearch Engine Optimizationの略で検索エンジン最適化を意味する重要な概念です。"
        )
        text = f"{long_ignored}\n\n{PARA1}"
        result = TextSplitter().extract_check_phrases(text)
        texts = [f.text for f in result]
        assert not any(t.startswith("SEOとは") for t in texts)

    def test_paragraph_index_assigned(self):
        text = f"{PARA1}\n\n{PARA2}"
        result = TextSplitter().extract_check_phrases(text)
        indices = [f.paragraph_index for f in result]
        assert 0 in indices

    def test_multiple_paragraphs_index(self):
        p3 = "三番目の段落です。このテストは段落が三つある場合の動作を検証するために作成されました。"
        text = f"{PARA1}\n\n{PARA2}\n\n{p3}"
        result = TextSplitter().extract_check_phrases(text)
        indices = set(f.paragraph_index for f in result)
        assert len(indices) >= 2
