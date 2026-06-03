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
