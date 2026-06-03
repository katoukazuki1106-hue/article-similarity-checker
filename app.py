"""
app.py
article_similarity_checker のStreamlit Webアプリ版
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st

# モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent))

from article_loader import ArticleLoader
from text_splitter import TextSplitter
from query_builder import QueryBuilder
from search_client import get_search_client
from similarity_checker import SimilarityChecker
from risk_scorer import RiskScorer
from report_generator import ReportGenerator
import config

# ---- ページ設定 ----
st.set_page_config(
    page_title="記事類似チェックツール",
    page_icon="📋",
    layout="wide",
)

# ---- リスクカラー定義 ----
RISK_COLORS = {
    "問題なし": "#4caf50",
    "高リスク":  "#ff9800",
    "要確認":   "#f9a825",
    "危険":     "#f44336",
}

RISK_BG = {
    "問題なし": "#e8f5e9",
    "高リスク":  "#fff3e0",
    "要確認":   "#fff9c4",
    "危険":     "#ffebee",
}


def main():
    st.title("📋 記事盗作・類似チェック補助ツール")
    st.caption("外部ライターから納品された記事のWeb類似チェックを行い、編集者の確認を支援します。")
    st.caption("最終更新: 2026-05-15 | v1.3（URL別一致サマリー追加・検出精度改善）")

    st.warning(
        "⚠️ 本ツールは盗作・著作権侵害を法的に断定するものではありません。"
        "検出結果はあくまで編集者が確認するための補助資料です。",
        icon="⚠️",
    )

    st.divider()

    # ---- サイドバー：設定 ----
    with st.sidebar:
        st.header("⚙️ チェック設定")
        threshold = st.slider(
            "類似度しきい値（%）",
            min_value=50,
            max_value=100,
            value=80,
            step=5,
            help="この値以上の類似度を検出対象にします",
        )
        use_mock = st.toggle("モック検索を使用", value=False, help="ONにするとAPIキー不要で動作します")
        st.divider()
        st.caption("🔗 モックをオフにするとBrave Search APIで実際のWeb全体と照合できます。")

    # ---- ファイルアップロード ----
    uploaded_file = st.file_uploader(
        "チェックしたい記事ファイルをアップロード",
        type=["txt", "md", "docx"],
        help=".txt / .md / .docx 形式に対応しています",
    )

    if not uploaded_file:
        st.info("記事ファイルをアップロードするとチェックが開始できます。")
        _show_sample_info()
        return

    # ---- チェック実行ボタン ----
    if st.button("🔍 チェック開始", type="primary"):
        _run_check(uploaded_file, threshold, use_mock)


def _run_check(uploaded_file, threshold: float, use_mock: bool):
    """チェック処理を実行し、結果を表示する。"""

    with st.spinner("記事を読み込んでいます..."):
        # 一時ファイルに保存して読み込む
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            loader = ArticleLoader()
            article_text = loader.load(tmp_path)
        except Exception as e:
            st.error(str(e))
            return
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    with st.spinner("テキストを分割しています..."):
        splitter = TextSplitter()
        fragments = splitter.extract_check_phrases(article_text)

    if not fragments:
        st.warning("チェック対象フレーズが見つかりませんでした。記事が短すぎる可能性があります。")
        return

    with st.spinner("類似フレーズを検索しています..."):
        builder = QueryBuilder()
        queries = builder.build_queries(fragments)
        search_client = get_search_client(use_mock=use_mock)
        checker = SimilarityChecker()

        matches = []
        debug_rows = []
        progress = st.progress(0, text="検索中...")
        for i, (fragment, query) in enumerate(zip(fragments, queries)):
            results = search_client.search(query)
            match = checker.check_phrase(fragment.text, results)
            # デバッグ用：最初の5件の詳細を記録
            if i < 5:
                top_url = results[0].url if results else "（結果なし）"
                from rapidfuzz import fuzz
                top_score = max(
                    (fuzz.partial_ratio(fragment.text, r.snippet) for r in results),
                    default=0
                ) if results else 0
                debug_rows.append({
                    "クエリ": query,
                    "取得件数": len(results),
                    "上位URL": top_url,
                    "最高類似度": f"{top_score}%",
                })
            if match and match.similarity >= threshold:
                matches.append(match)
            progress.progress((i + 1) / len(queries), text=f"検索中... {i+1}/{len(queries)}")
        progress.empty()

    # デバッグ情報を表示
    with st.expander("🔍 デバッグ情報（最初の5クエリ）", expanded=not matches):
        if debug_rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(debug_rows), width="stretch")
        else:
            st.write("データなし")

    scorer = RiskScorer()
    risk_summary = scorer.calculate(matches, len(fragments))

    # ---- 結果表示 ----
    _show_summary(risk_summary, uploaded_file.name, len(article_text), len(queries))
    _show_url_summaries(risk_summary.url_summaries)
    _show_matches(matches)
    _show_csv_download(matches, uploaded_file.name)


def _show_summary(rs, filename: str, char_count: int, query_count: int):
    """サマリーカードを表示する。"""
    color = RISK_COLORS.get(rs.final_risk, "#4caf50")
    bg = RISK_BG.get(rs.final_risk, "#e8f5e9")

    st.markdown(f"""
    <div style="background:{bg};border-left:6px solid {color};border-radius:8px;padding:20px;margin:16px 0;">
      <div style="font-size:2.2em;font-weight:bold;color:{color};line-height:1;">
        {rs.overall_score} <span style="font-size:0.5em;">/ 100</span>
      </div>
      <div style="font-size:1.2em;font-weight:bold;color:{color};margin-top:4px;">最終判定：{rs.final_risk}</div>
      <div style="color:{color};margin-top:8px;font-size:0.95em;">{rs.summary_reason}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("総文字数", f"{char_count:,}")
    c2.metric("対象フレーズ", rs.total_phrases)
    c3.metric("検索クエリ", query_count)
    c4.metric("類似検出", rs.matched_count)
    c5.metric("危険", rs.danger_count, delta=None)
    c6.metric("要確認", rs.warning_count, delta=None)


def _show_url_summaries(url_summaries):
    """URL別一致サマリーを表示する。"""
    if not url_summaries:
        return

    st.divider()
    st.subheader("🔗 類似元URL別サマリー")
    st.caption("同一URLから複数フレーズが一致している場合、コピー元の可能性が高くなります。")

    for us in url_summaries:
        color = RISK_COLORS.get(us.risk_level, "#4caf50")
        badge = f"<span style='background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.85em;'>{us.risk_level}</span>"
        st.markdown(
            f"{badge} &nbsp; **{us.match_count}フレーズ一致** &nbsp; 最高類似度:{us.max_similarity:.0f}% &nbsp; "
            f"[{us.title or us.url}]({us.url})",
            unsafe_allow_html=True,
        )


def _show_matches(matches):
    """類似検出フレーズ一覧を表示する。"""
    st.divider()
    st.subheader("類似検出フレーズ一覧")

    if not matches:
        st.success("類似フレーズは検出されませんでした。")
        return

    for m in matches:
        color = RISK_COLORS.get(m.risk_level, "#4caf50")
        bg = RISK_BG.get(m.risk_level, "#e8f5e9")
        with st.expander(f"[{m.risk_level}]  {m.phrase[:60]}{'…' if len(m.phrase)>60 else ''}"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"**判定**")
                st.markdown(f"<span style='background:{bg};color:{color};padding:3px 10px;border-radius:12px;font-weight:bold;'>{m.risk_level}</span>", unsafe_allow_html=True)
                st.metric("類似度", f"{m.similarity:.0f}%")
                st.metric("連続一致", f"{m.continuous_match_length}文字")
            with col2:
                st.markdown("**本文フレーズ**")
                st.info(m.phrase)
                st.markdown("**類似元**")
                st.markdown(f"[{m.title}]({m.url})")
                st.caption(m.matched_snippet[:150] + "…" if len(m.matched_snippet) > 150 else m.matched_snippet)
            st.markdown(f"**判定理由：** {m.reason}")
            st.markdown(f"**編集者コメント：** {m.editor_comment}")

    st.divider()
    st.caption(
        "⚠️ 本レポートは、既存Web記事との一致・類似が疑われる箇所を抽出するための補助資料です。"
        "盗作・著作権侵害を法的に断定するものではありません。"
        "最終判断は編集担当者が、出典・引用・文脈を確認したうえで行ってください。"
    )


def _show_csv_download(matches, filename: str):
    """CSVダウンロードボタンを表示する。"""
    if not matches:
        return

    import csv, io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "判定", "類似度", "連続一致文字数", "本文フレーズ",
        "類似元タイトル", "類似元URL", "判定理由", "編集者コメント",
    ])
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

    st.download_button(
        label="📥 CSVレポートをダウンロード",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"{Path(filename).stem}_report.csv",
        mime="text/csv",
    )


def _show_sample_info():
    """使い方の説明を表示する。"""
    with st.expander("📖 使い方"):
        st.markdown("""
1. 左上の「Browse files」からチェックしたい記事ファイルをアップロード
2. 「チェック開始」ボタンを押す
3. 結果が表示されます

**対応ファイル形式：** `.txt` / `.md` / `.docx`

**判定基準：**
| 判定 | スコア |
|------|-------|
| 問題なし | 0〜19 |
| 要確認 | 20〜49 |
| 高リスク | 50〜79 |
| 危険 | 80〜100 |
        """)


if __name__ == "__main__":
    main()
