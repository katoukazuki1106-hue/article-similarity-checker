"""
article_loader.py
.txt / .md / .docx ファイルを読み込み、本文テキストを返す。
"""

from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx"}


class ArticleLoader:
    def load(self, file_path: str) -> str:
        """
        ファイルを読み込んでテキストを返す。
        存在しない・非対応形式の場合はわかりやすいエラーを出す。
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"[エラー] ファイルが見つかりません: {file_path}\n"
                f"パスを確認してください。"
            )

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"[エラー] 未対応のファイル形式です: '{ext}'\n"
                f"対応形式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        if ext in {".txt", ".md"}:
            return self._load_text(path)
        else:
            return self._load_docx(path)

    def _load_text(self, path: Path) -> str:
        """UTF-8 → Shift-JIS の順でフォールバックして読む。"""
        for encoding in ("utf-8", "shift_jis", "cp932"):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        raise ValueError(
            f"[エラー] ファイルのエンコーディングを判定できませんでした: {path}\n"
            f"UTF-8 または Shift-JIS 形式で保存してください。"
        )

    def _load_docx(self, path: Path) -> str:
        """python-docx を使って .docx を読み込む。"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "[エラー] python-docx がインストールされていません。\n"
                "pip install python-docx を実行してください。"
            )

        doc = Document(str(path))
        lines = [para.text for para in doc.paragraphs if para.text.strip()]
        if not lines:
            raise ValueError(
                f"[エラー] .docx ファイルにテキストが含まれていません: {path}"
            )
        return "\n".join(lines)
