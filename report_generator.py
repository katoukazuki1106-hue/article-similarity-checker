"""
report_generator.py
HTMLレポートとCSVレポートを生成する。
"""

import csv
import html
from datetime import datetime
from pathlib import Path
from typing import List

from risk_scorer import RiskSummary
from similarity_checker import SimilarityMatch

# リスクレベルと色のマッピング
_RISK_COLORS = {
    "問題なし": ("#e8f5e9", "#2e7d32", "#4caf50"),   # bg, text, border
    "高リスク":  ("#fff3e0", "#e65100", "#ff9800"),
    "要確認":   ("#fff9c4", "#f57f17", "#f9a825"),
    "危険":     ("#ffebee", "#b71c1c", "#f44336"),
}

_DISCLAIMER = (
    "本レポートは、既存Web記事との一致・類似が疑われる箇所を抽出するための補助資料です。"
    "盗作・著作権侵害を法的に断定するものではありません。"
    "最終判断は編集担当者が、出典・引用・文脈を確認したうえで行ってください。"
)


class ReportGenerator:

    def generate(
        self,
        input_file: str,
        article_text: str,
        matches: List[SimilarityMatch],
        risk_summary: RiskSummary,
        query_count: int,
        output_dir: str,
        fmt: str = "both",
    ) -> dict:
        """
        HTMLとCSVのレポートを出力する。
        fmt: 'html' / 'csv' / 'both'
        戻り値: {'html': パス, 'csv': パス} （出力したもののみ）
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(input_file).stem
        output: dict = {}

        if fmt in ("html", "both"):
            html_path = str(Path(output_dir) / f"{base_name}_{timestamp}.html")
            self._write_html(html_path, input_file, article_text, matches, risk_summary, query_count)
            output["html"] = html_path

        if fmt in ("csv", "both"):
            csv_path = str(Path(output_dir) / f"{base_name}_{timestamp}.csv")
            self._write_csv(csv_path, matches)
            output["csv"] = csv_path

        return output

    # ------------------------------------------------------------------
    # HTML レポート
    # ------------------------------------------------------------------

    def _write_html(
        self,
        path: str,
        input_file: str,
        article_text: str,
        matches: List[SimilarityMatch],
        rs: RiskSummary,
        query_count: int,
    ) -> None:
        bg, text_color, border = _RISK_COLORS.get(rs.final_risk, _RISK_COLORS["問題なし"])
        check_dt = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

        rows_html = self._build_match_rows(matches)

        content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>記事類似チェック レポート｜{html.escape(Path(input_file).name)}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, 'Hiragino Sans', 'Meiryo', sans-serif;
          background: #f4f6f8; color: #333; margin: 0; padding: 20px; font-size: 14px; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 1.5em; margin: 0; }}
  h2 {{ font-size: 1.1em; border-left: 4px solid #607d8b; padding-left: 10px;
        margin: 24px 0 12px; color: #455a64; }}
  .header {{ background: #2c3e50; color: #fff; padding: 20px 24px;
              border-radius: 8px 8px 0 0; }}
  .header small {{ opacity: 0.7; font-size: 0.85em; }}
  .card {{ background: #fff; border-radius: 0 0 8px 8px;
           padding: 24px; box-shadow: 0 2px 6px rgba(0,0,0,.08); margin-bottom: 20px; }}
  .summary-box {{ background: {bg}; border-left: 6px solid {border};
                  border-radius: 6px; padding: 18px 20px; margin: 16px 0; }}
  .summary-box .score {{ font-size: 2.4em; font-weight: bold; color: {text_color}; line-height: 1; }}
  .summary-box .label {{ font-size: 1.1em; font-weight: bold; color: {text_color}; margin-left: 12px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }}
  .stat {{ background: #f9fafb; border: 1px solid #e0e0e0; border-radius: 6px;
            padding: 12px 16px; min-width: 140px; }}
  .stat .val {{ font-size: 1.6em; font-weight: bold; color: #37474f; }}
  .stat .key {{ font-size: 0.82em; color: #78909c; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
  th {{ background: #eceff1; padding: 10px 12px; text-align: left;
        border-bottom: 2px solid #cfd8dc; white-space: nowrap; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #eceff1; vertical-align: top; word-break: break-all; }}
  tr:hover td {{ background: #fafafa; }}
  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 12px;
             font-size: 0.82em; font-weight: bold; white-space: nowrap; }}
  .badge-問題なし {{ background: #e8f5e9; color: #2e7d32; }}
  .badge-高リスク  {{ background: #fff3e0; color: #e65100; }}
  .badge-要確認   {{ background: #fff9c4; color: #f57f17; }}
  .badge-危険     {{ background: #ffebee; color: #b71c1c; }}
  .phrase {{ background: #f5f5f5; border-left: 3px solid #90a4ae;
              padding: 4px 8px; border-radius: 2px; font-size: 0.9em; }}
  .url a {{ color: #1565c0; text-decoration: none; font-size: 0.85em; }}
  .url a:hover {{ text-decoration: underline; }}
  .disclaimer {{ background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px;
                 padding: 14px 16px; font-size: 0.88em; color: #666; line-height: 1.7; }}
  .disclaimer strong {{ color: #c62828; }}
  .no-matches {{ text-align: center; padding: 30px; color: #78909c; font-size: 1.05em; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📋 記事類似チェック レポート</h1>
    <small>チェック日時：{check_dt}　|　入力ファイル：{html.escape(Path(input_file).name)}</small>
  </div>
  <div class="card">

    <h2>最終判定</h2>
    <div class="summary-box">
      <span class="score">{rs.overall_score}</span>
      <span class="label">/ 100　{rs.final_risk}</span>
      <p style="margin:10px 0 0;color:{text_color};font-size:.95em;">{html.escape(rs.summary_reason)}</p>
    </div>

    <h2>チェック概要</h2>
    <div class="stats">
      <div class="stat"><div class="val">{len(article_text):,}</div><div class="key">総文字数</div></div>
      <div class="stat"><div class="val">{rs.total_phrases}</div><div class="key">チェック対象フレーズ数</div></div>
      <div class="stat"><div class="val">{query_count}</div><div class="key">検索クエリ数</div></div>
      <div class="stat"><div class="val">{rs.matched_count}</div><div class="key">類似検出件数</div></div>
      <div class="stat"><div class="val" style="color:#b71c1c">{rs.danger_count}</div><div class="key">危険 件数</div></div>
      <div class="stat"><div class="val" style="color:#f57f17">{rs.warning_count}</div><div class="key">要確認 件数</div></div>
      <div class="stat"><div class="val" style="color:#e65100">{rs.high_risk_count}</div><div class="key">高リスク 件数</div></div>
      <div class="stat"><div class="val">{rs.match_rate}%</div><div class="key">全体類似率</div></div>
    </div>

    <h2>類似検出フレーズ一覧</h2>
    {rows_html}

    <h2>注意事項</h2>
    <div class="disclaimer">
      <strong>【重要】</strong>
      {html.escape(_DISCLAIMER)}
    </div>

  </div>
</div>
</body>
</html>"""

        Path(path).write_text(content, encoding="utf-8")

    def _build_match_rows(self, matches: List[SimilarityMatch]) -> str:
        if not matches:
            return '<div class="no-matches">✅ 類似フレーズは検出されませんでした。</div>'

        rows = ""
        for m in matches:
            badge = f'<span class="badge badge-{m.risk_level}">{m.risk_level}</span>'
            phrase_esc = html.escape(m.phrase)
            snippet_esc = html.escape(m.matched_snippet[:120] + ("…" if len(m.matched_snippet) > 120 else ""))
            title_esc = html.escape(m.title)
            url_esc = html.escape(m.url)
            reason_esc = html.escape(m.reason)
            comment_esc = html.escape(m.editor_comment)
            rows += f"""
<tr>
  <td>{badge}</td>
  <td>{m.similarity:.0f}%</td>
  <td>{m.continuous_match_length}文字</td>
  <td><div class="phrase">{phrase_esc}</div></td>
  <td class="url"><strong>{title_esc}</strong><br><a href="{url_esc}" target="_blank">{url_esc}</a><br>
      <small style="color:#555">{snippet_esc}</small></td>
  <td>{reason_esc}</td>
  <td style="font-size:.88em;color:#555">{comment_esc}</td>
</tr>"""

        return f"""<table>
<thead>
<tr>
  <th>判定</th><th>類似度</th><th>連続一致</th><th>本文フレーズ</th>
  <th>類似元（タイトル / URL / スニペット）</th><th>判定理由</th><th>編集者コメント</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>"""

    # ------------------------------------------------------------------
    # CSV レポート
    # ------------------------------------------------------------------

    def _write_csv(self, path: str, matches: List[SimilarityMatch]) -> None:
        fieldnames = [
            "判定", "類似度", "連続一致文字数",
            "本文フレーズ", "類似元タイトル", "類似元URL",
            "判定理由", "編集者コメント",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in matches:
                writer.writerow({
                    "判定": m.risk_level,
                    "類似度": f"{m.similarity:.1f}%",
                    "連続一致文字数": m.continuous_match_length,
                    "本文フレーズ": m.phrase,
                    "類似元タイトル": m.title,
                    "類似元URL": m.url,
                    "判定理由": m.reason,
                    "編集者コメント": m.editor_comment,
                })
