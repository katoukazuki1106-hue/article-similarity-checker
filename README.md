# article_similarity_checker

記事盗作・類似チェック補助ツール（Python製CLIツール）

---

## ⚠️ 重要な注意事項

**本ツールは、盗作・著作権侵害を断定するものではありません。**
あくまで、Web上の記事との一致・類似が疑われる箇所を抽出し、編集者による確認を支援するためのツールです。
最終判断は、引用の有無、出典表記、事実情報、一般的表現、文脈を確認したうえで行ってください。

---

## 1. ツール概要

外部ライターから納品された記事について、ネット上の記事との一致・類似箇所を抽出するための補助ツールです。
HTMLおよびCSVレポートを出力し、編集者が確認しやすい形で提供します。

## 2. このツールでできること

- `.txt` / `.md` / `.docx` 形式の記事ファイルを読み込み
- 記事本文をフレーズ単位に分割してチェック
- 検索APIまたはモックデータと照合し、類似フレーズを検出
- 類似度スコア・連続一致文字数をもとにリスクを4段階で判定
- 編集者向けコメント付きのHTMLレポートとCSVレポートを出力

## 3. このツールでできないこと

- 法的な盗作・著作権侵害の断定
- ネット上のすべての記事との照合（API制限・検索範囲の限界あり）
- 画像・動画の盗用チェック
- 日本語以外の言語への最適化（対応言語は主に日本語）

## 4. インストール方法

Python 3.9以上が必要です。

```bash
# リポジトリをクローンまたはZIPを展開後、フォルダに移動
cd article_similarity_checker

# 依存パッケージをインストール
pip install -r requirements.txt

# .envファイルを作成（モックモードではAPIキー不要）
cp .env.example .env
```

## 5. 実行方法

### 基本的な使い方（モックモード・APIキー不要）

```bash
python main.py --input samples/sample_article.txt
```

### オプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--input` | チェックする記事ファイルのパス（必須） | - |
| `--output` | レポート出力先ディレクトリ | `reports/` |
| `--format` | 出力形式（`html` / `csv` / `both`） | `both` |
| `--threshold` | 類似度しきい値（0〜100） | `80` |
| `--mock` | モック検索を使用するか（`true` / `false`） | `true` |

### 実行例

```bash
# HTMLとCSVの両方を出力
python main.py --input samples/sample_article.txt --format both --mock true

# リスクのあるサンプル記事をチェック
python main.py --input samples/sample_article_risky.txt --format both --mock true

# .docxファイルをチェック
python main.py --input article.docx --output ./results --format html

# 類似度しきい値を75%に変更
python main.py --input article.txt --threshold 75
```

## 6. サンプル記事でのテスト方法

以下のコマンドでサンプル記事のチェックを実行できます。

```bash
# 問題なしサンプル（低リスク）
python main.py --input samples/sample_article.txt --format both

# 類似フレーズありサンプル（高リスク）
python main.py --input samples/sample_article_risky.txt --format both
```

`reports/` フォルダにHTMLとCSVが生成されます。

## 7. レポートの見方

### 最終判定スコア（0〜100）

| スコア | 判定 | 意味 |
|-------|------|------|
| 0〜19 | ✅ 問題なし | 類似フレーズが検出されませんでした |
| 20〜49 | ⚠️ 要確認 | 一部に類似表現があります。確認を推奨します |
| 50〜79 | 🔶 高リスク | 複数の類似フレーズが検出されました |
| 80〜100 | 🚨 危険 | 高い類似度の一致が検出されました |

### フレーズごとの判定基準

| 判定 | 条件 |
|------|------|
| 危険 | 類似度90%以上、または連続80文字以上の一致 |
| 要確認 | 類似度80%以上、または連続50文字以上の一致 |
| 高リスク | 類似度60%以上、または連続30文字以上の一致 |
| 問題なし | 上記に該当しない |

## 8. よくあるエラー

**`ModuleNotFoundError: No module named 'rapidfuzz'`**
→ `pip install -r requirements.txt` を実行してください。

**`FileNotFoundError: ファイルが見つかりません`**
→ `--input` に指定したパスを確認してください。

**`UnicodeDecodeError`**
→ ファイルをUTF-8形式で保存してください。

**`[エラー] 未対応のファイル形式`**
→ 対応形式は `.txt` / `.md` / `.docx` のみです。

## 9. Web検索APIを使う場合の拡張方針

1. `.env` ファイルに使用するAPIのキーを設定
2. `main.py` の実行時に `--mock false` を指定
3. 優先順位：Google Custom Search → Bing Web Search → SerpAPI

```bash
# .envにAPIキーを設定後
python main.py --input article.txt --mock false
```

各APIの取得方法：
- **Google Custom Search**: https://developers.google.com/custom-search/v1/introduction
- **Bing Web Search**: https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
- **SerpAPI**: https://serpapi.com/

## 10. 納品先向けの運用例

1. ライターから記事ファイル（.txt/.md/.docx）を受領
2. 以下のコマンドを実行
   ```bash
   python main.py --input 受領記事.txt --format both
   ```
3. `reports/` フォルダのHTMLレポートをブラウザで確認
4. 「危険」「要確認」判定のフレーズについて類似元URLを確認
5. 引用・盗用の疑いがある場合はライターへ差し戻し

## 11. 納品用ZIP化手順

```bash
# Windowsの場合（PowerShell）
Compress-Archive -Path article_similarity_checker -DestinationPath article_similarity_checker.zip

# Mac/Linuxの場合
zip -r article_similarity_checker.zip article_similarity_checker/
```

ZIP解凍後、`pip install -r requirements.txt` を実行するだけで使用できます。
