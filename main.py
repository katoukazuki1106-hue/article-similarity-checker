"""
main.py
article_similarity_checker のCLIエントリポイント。

使用例:
  python main.py --input samples/sample_article.txt
  python main.py --input samples/sample_article_risky.txt --format both --mock true
"""

import argparse
import sys
from pathlib import Path

# Windows環境でのUTF-8出力を強制する
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from article_loader import ArticleLoader
from text_splitter import TextSplitter
from query_builder import QueryBuilder
from search_client import get_search_client
from similarity_checker import SimilarityChecker
from risk_scorer import RiskScorer
from report_generator import ReportGenerator


def parse_args():
    parser = argparse.ArgumentParser(
        description="記事盗作・類似チェック補助ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --input samples/sample_article.txt
  python main.py --input samples/sample_article_risky.txt --format both --mock true
  python main.py --input article.docx --output ./results --format html --threshold 75
        """,
    )
    parser.add_argument("--input", required=True, help="チェックする記事ファイルのパス（.txt/.md/.docx）")
    parser.add_argument("--output", default=config.REPORT_OUTPUT_DIR, help="レポート出力先ディレクトリ（デフォルト: reports/）")
    parser.add_argument("--format", default="both", choices=["html", "csv", "both"], help="出力形式（デフォルト: both）")
    parser.add_argument("--threshold", type=float, default=config.WARNING_SIMILARITY_THRESHOLD,
                        help=f"類似度しきい値（デフォルト: {config.WARNING_SIMILARITY_THRESHOLD}）")
    parser.add_argument("--mock", default="true", choices=["true", "false"],
                        help="モック検索を使用するか（デフォルト: true）")
    return parser.parse_args()


def main():
    args = parse_args()
    use_mock = args.mock.lower() == "true"

    print("=" * 60)
    print("  記事盗作・類似チェック補助ツール  article_similarity_checker")
    print("=" * 60)
    print(f"  入力ファイル : {args.input}")
    print(f"  出力形式     : {args.format}")
    print(f"  類似度しきい値: {args.threshold}%")
    print(f"  検索モード   : {'モック（ローカル）' if use_mock else '実API'}")
    print("-" * 60)

    # ---- Step 1: 記事読み込み ----
    print("[1/6] 記事を読み込んでいます...")
    try:
        loader = ArticleLoader()
        article_text = loader.load(args.input)
    except (FileNotFoundError, ValueError, ImportError) as e:
        print(str(e))
        sys.exit(1)

    print(f"      文字数: {len(article_text):,} 文字")

    # ---- Step 2: テキスト分割 ----
    print("[2/6] テキストを分割しています...")
    splitter = TextSplitter()
    fragments = splitter.extract_check_phrases(article_text)
    print(f"      チェック対象フレーズ数: {len(fragments)} 件")

    if not fragments:
        print("[警告] チェック対象フレーズが見つかりませんでした。")
        print("       記事が短すぎるか、最小文字数の設定を確認してください。")
        sys.exit(0)

    # ---- Step 3: クエリ生成 ----
    print("[3/6] 検索クエリを生成しています...")
    builder = QueryBuilder()
    queries = builder.build_queries(fragments)
    print(f"      クエリ数: {len(queries)} 件")

    # ---- Step 4: 検索 ----
    print("[4/6] 検索を実行しています...")
    search_client = get_search_client(use_mock=use_mock)
    checker = SimilarityChecker()

    all_matches = []
    for i, (fragment, query) in enumerate(zip(fragments, queries), 1):
        if i % 10 == 0 or i == len(queries):
            print(f"      {i}/{len(queries)} クエリ処理中...", end="\r")
        results = search_client.search(query)
        match = checker.check_phrase(fragment.text, results)
        if match and match.similarity >= args.threshold:
            all_matches.append(match)

    print(f"\n      類似検出: {len(all_matches)} 件")

    # ---- Step 5: リスクスコア算出 ----
    print("[5/6] リスクスコアを算出しています...")
    scorer = RiskScorer()
    risk_summary = scorer.calculate(all_matches, len(fragments))
    print(f"      全体スコア: {risk_summary.overall_score} / 100  [{risk_summary.final_risk}]")

    # ---- Step 6: レポート生成 ----
    print("[6/6] レポートを生成しています...")
    generator = ReportGenerator()
    output_files = generator.generate(
        input_file=args.input,
        article_text=article_text,
        matches=all_matches,
        risk_summary=risk_summary,
        query_count=len(queries),
        output_dir=args.output,
        fmt=args.format,
    )

    print("\n" + "=" * 60)
    print("  チェック完了")
    print("=" * 60)
    _print_final_result(risk_summary)
    print()
    for fmt, path in output_files.items():
        print(f"  {fmt.upper()} レポート → {path}")
    print()
    print("  ⚠️  " + "本結果は盗作を断定するものではありません。編集者による最終確認をお願いします。")
    print("=" * 60)


def _print_final_result(rs):
    labels = {
        "問題なし": "[OK]   問題なし",
        "要確認":   "[!]    要確認",
        "高リスク": "[!!]   高リスク",
        "危険":     "[危険] 危険",
    }
    label = labels.get(rs.final_risk, rs.final_risk)
    print(f"  最終判定: {label}  （スコア: {rs.overall_score}/100）")
    print(f"  {rs.summary_reason}")


if __name__ == "__main__":
    main()
