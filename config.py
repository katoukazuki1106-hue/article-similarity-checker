"""
article_similarity_checker 設定ファイル
各種しきい値・パラメータはここで一元管理する。
"""

# ---- テキスト処理 ----
MIN_TEXT_LENGTH = 40        # チェック対象とする最小文字数（40文字未満は創作性が低い可能性あり）
MAX_PHRASE_LENGTH = 80      # 分割対象とする最大文字数（超えたら読点で分割）

# ---- 類似度判定しきい値 ----
HIGH_SIMILARITY_THRESHOLD = 90    # これ以上を「危険」と判定
WARNING_SIMILARITY_THRESHOLD = 80 # これ以上を「要確認」と判定
MID_SIMILARITY_THRESHOLD = 60     # これ以上を「高リスク」と判定

# ---- 連続一致文字数しきい値 ----
DANGER_CONTINUOUS_MATCH_LENGTH = 60  # これ以上の連続一致を「危険」と判定
WARNING_CONTINUOUS_MATCH_LENGTH = 40  # これ以上の連続一致を「要確認」と判定
CAUTION_CONTINUOUS_MATCH_LENGTH = 25  # これ以上の連続一致を「高リスク」と判定

# ---- 検索 ----
MAX_SEARCH_QUERIES = 30    # 1記事あたりの最大検索クエリ数
SEARCH_QUERY_MAX_LEN = 50  # クエリの最大文字数

# ---- 媒体照合モード（指定媒体・過去1か月インデックスとローカル照合）----
MEDIA_INDEX_RECENT_DAYS = 30      # インデックスに保持する日数（ローリング過去1か月）
MEDIA_BODY_MAX_CHARS = 8000       # 1記事あたり保存する本文の最大文字数（容量管理）
MEDIA_CANDIDATE_TOP_K = 8         # 1フレーズあたり照合候補として返す記事数
MEDIA_TRIGRAM_MIN_OVERLAP = 3     # 候補とみなす最小trigram重なり数

# ---- クローラ ----
CRAWL_POLITE_DELAY_SEC = 1.0      # 記事取得間の待機秒（媒体への配慮）
CRAWL_MAX_ENTRIES_PER_FEED = 100  # 1フィードから取得する最大エントリ数

# ---- サイトマップ取り込み（type="sitemap" 媒体）----
# RSS未提供の媒体は news-sitemap / 記事サイトマップから記事URL・公開日を取得する。
SITEMAP_MAX_SUBS = 4              # サイトマップindexから辿るサブサイトマップの最大数（新しい順）
SITEMAP_MAX_URLS_PER_MEDIA = 80  # 1媒体あたり本文取得する記事数の上限（公開日が新しい順）
SITEMAP_FETCH_RETRIES = 3        # サイトマップ取得のリトライ回数（アンチボット対策）

# ---- 全体リスク率 ----
OVERALL_DANGER_RATE = 40.0  # 類似フレーズ率がこれ以上（%）を「危険」
OVERALL_WARNING_RATE = 20.0 # 類似フレーズ率がこれ以上（%）を「要注意」

# ---- 出力 ----
REPORT_OUTPUT_DIR = "reports"

# ---- スキップする一般的短文 ----
# 編集部が追加・削除可能
IGNORED_PHRASES = [
    "SEOとは",
    "Webマーケティングとは",
    "コンテンツマーケティングとは",
    "ホームページとは",
    "デジタルマーケティングとは",
    "SNSとは",
    "CVRとは",
    "CTRとは",
]
