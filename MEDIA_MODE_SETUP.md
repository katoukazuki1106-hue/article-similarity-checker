# 媒体照合モード セットアップ手順（指定媒体・過去1か月照合）

外部ライターの納品記事が、**指定エンタメ媒体の過去1か月の記事をコピペ・流用していないか**を、
検索ランキングに依存せず**再現性高く**チェックする機能です。

## 仕組み

```
GitHub Actions（無料cron・4時間ごと）
   └─ crawler.py … 各媒体のRSSを巡回 → 本文取得 → Supabaseへ保存 → 30日より古い記事をパージ
                                  │
                         Supabase 無料Postgres（articlesテーブル＝ローリング過去1か月）
                                  │
Render の Streamlit アプリ … 「📰 媒体照合モード」ON時、過去1か月コーパスとローカル照合
```

- RSSは直近分しか出ないため、**高頻度で回して貯め続ける**ことで「過去1か月」を構築する。
- 照合はローカル比較なので**同じ記事は毎回同じ判定**（再現性が高い）。検証は何回でもAPI課金ゼロ。

## コスト
- 照合: **$0**（ローカル比較・API課金なし）
- 基盤: GitHub Actions（無料枠）＋ Supabase 無料Postgres → **実質 $0/月**
- 月200〜300本の検証でも追加コストなし。

---

## セットアップ手順

### 1. Supabase（永続インデックスの保存先）

1. https://supabase.com で無料アカウント作成 → 新規プロジェクト作成。
2. SQL Editor で以下を実行してテーブル作成：
   ```sql
   create table articles (
     url          text primary key,
     media_name   text not null,
     title        text,
     published_at timestamptz,
     body_text    text,
     fetched_at   timestamptz
   );
   create index on articles (published_at);
   ```
3. Project Settings → API から以下を控える：
   - `Project URL`（= `SUPABASE_URL`）
   - `service_role` key（= `SUPABASE_KEY`。サーバ専用・公開禁止）

### 2. GitHub Actions（定期クロール）

1. このリポジトリの Settings → Secrets and variables → Actions に登録：
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
2. `.github/workflows/crawl.yml` が4時間ごとに `crawler.py` を実行する（手動実行も可：Actions → media-crawl → Run workflow）。
3. 初回は Run workflow で手動実行し、Supabaseの `articles` に行が入ることを確認。

### 3. Render（Webアプリ）

1. Render の対象サービスの Environment に以下を追加：
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
2. `requirements.txt` に `feedparser` を追加済み。再デプロイすれば反映される。
3. アプリを開き、サイドバーの「📰 媒体照合モード」をON（既定でON）。
   収録記事数・最終クロール時刻が表示されれば接続成功。

> 環境変数 `SUPABASE_URL`/`SUPABASE_KEY` が無い環境では自動的にローカルSQLite
> （`media_corpus.db`）にフォールバックする（ローカル検証用）。

---

## 媒体の追加・管理（`media_sources.py`）

- `MEDIA_SOURCES` に媒体を定義。`enabled=True` の媒体だけクロールする。
- 媒体を増やすときは `enabled=True` にし、`feed_urls` に正しいRSSを設定。
- フィードURLが不確かでも、`crawler.py` がトップページからRSSを自動探索（autodiscovery）する。

### 2026-06-18 時点の実機確認結果（重要）
- **稼働確認済み 11媒体（enabled=True）**:
  ナタリー / ライブドアニュース / ガジェット通信 / ENCOUNT / マイナビニュース /
  リアルサウンド / billboard JAPAN / シネマトゥデイ / BARKS / エンタのおはなし / WWSチャンネル
  - リアルサウンド=`/atom.xml`、billboard=`/d_news/doc.xml`、シネマトゥデイ=`/index.xml`、
    BARKS=`/feed`、エンタのおはなし=`/feed/`、WWS=`/feed`（いずれも公開日あり）
- **RSS取得不可で保留 9媒体（enabled=False）**:
  - オリコン … 旧RSSが **410 Gone**（廃止）。
  - ねとらぼ … `rss.itmedia netlab.xml` が **更新停止（2025-05でstale）**。ITmedia topstoryは
    「ねとらぼ専用」でないため不採用。
  - 映画.com … `/rss/*` が 404/403。
  - モデルプレス / TRILL / クランクイン / WEBザ・テレビジョン … feed/atom/index/autodiscovery
    いずれも取得不可（SPA/アプリ型でRSS未提供と判断）。
  - Yahoo!ニュース・LINEニュース … RSSが弱く、かつ他媒体の配信先（アグリゲータ）。元媒体側で実質捕捉。
- 保留9媒体は将来 **サイトマップ対応**（`type="sitemap"`）で取り込む方針。

---

## 既知の限界
- **初日問題**: 運用開始直後はインデックスが空。約1か月かけて記事が蓄積される。
- **RSS非掲載記事**: フィードに出ない記事は捕捉できない（媒体の仕様による）。
- **ナビ/定型文ノイズ**: 記事本文にサイト共通のナビ等が混じることがある（ユーザー記事の散文とは
  一致しないため誤検知にはなりにくい）。本文抽出は `page_fetcher.py` でCSS等を除去済み。
- **本文上限**: 1記事 `MEDIA_BODY_MAX_CHARS`（既定8000字）まで保存（容量管理）。

## ローカルでの動作確認
```bash
pip install feedparser
python crawler.py --no-purge          # SQLiteにクロール（SUPABASE未設定時）
python crawler.py --media ガジェット通信  # 1媒体だけ
streamlit run app.py                  # 媒体照合モードON で照合
```
