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

### 2026-06-18 時点の実機確認結果（重要・サイトマップ対応追加済み）
- **稼働確認済み 13媒体（enabled=True）**:
  - **[RSS・11媒体]** ナタリー / ライブドアニュース / ガジェット通信 / ENCOUNT / マイナビニュース /
    リアルサウンド / billboard JAPAN / シネマトゥデイ / BARKS / エンタのおはなし / WWSチャンネル
    - リアルサウンド=`/atom.xml`、billboard=`/d_news/doc.xml`、シネマトゥデイ=`/index.xml`、
      BARKS=`/feed`、エンタのおはなし=`/feed/`、WWS=`/feed`（いずれも公開日あり）
  - **[サイトマップ・2媒体（`type="sitemap"`）]**
    - モデルプレス … Googleニュースサイトマップ `https://mdpr.jp/rss/google_news_sitemap.xml`
      （公開日・タイトル付き）。
    - ねとらぼ … 汎用サイトマップindex `https://nlab.itmedia.co.jp/sitemap/sitemap.xml` から
      `sitemap_filter=r"/post-2026_\d+\.xml"` で記事サイトマップだけを絞り、連番が新しいものを辿る
      （番号は増え続けるため最新サブを自動追従）。
- **保留 7媒体（enabled=False）**:
  - オリコン … news-sitemapは取得可だが、記事ページが **429 Too Many Requests** を強く返し安定取得が困難
    （`fetch_delay` を十分長く取れば将来復活可能）。
  - 映画.com … `news.xml.gz` がサイトマップ取得時に **403**。
  - TRILL … `article.xml.gz` は **日付フィールドが無く 18,747 件**で過去1か月に絞れない。
  - クランクイン … robots.txt 取得不可・サイトマップ未特定。
  - WEBザ・テレビジョン … サイトマップがセクションページのみで記事URL粒度が取れない。
  - Yahoo!ニュース・LINEニュース … RSS/サイトマップが弱く、かつ他媒体の配信先（アグリゲータ）。元媒体側で実質捕捉。

### サイトマップ媒体の追加方法（`type="sitemap"`）
`media_sources.py` で `type="sitemap"` とし、起点サイトマップを `sitemap_urls` に設定する。
- サイトマップindexの場合は `crawler.py` が自動で再帰し、`sitemap_filter`（正規表現）で
  辿るサブを絞れる。lastmod→末尾連番の順で新しいものから `SITEMAP_MAX_SUBS`(既定4)件だけ辿る。
- 各記事は news拡張の `publication_date`／`lastmod` を公開日として使い、過去
  `MEDIA_INDEX_RECENT_DAYS`(30)日に絞り、媒体あたり `SITEMAP_MAX_URLS_PER_MEDIA`(80)件まで本文取得。
- gzip(`.gz`/Content-Encoding)サイトマップは自動展開。

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
