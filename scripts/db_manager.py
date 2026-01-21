import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Tuple

class DetectionDBManager:
    """検出結果の保存と統計情報の取得を行うデータベースマネージャー"""

    def __init__(self, db_path: str = "logs/detection.db"):
        """
        検出結果を保存するSQLiteデータベースマネージャーとデータベース本体を初期化する

        Args:
            db_path (str): 使用するSQLiteデータベースファイルのパス。
                デフォルトは "logs/detection.db" で、このパス配下のディレクトリが存在しない場合は作成されます。
                また、必要に応じてデータベースファイルの作成、テーブルおよびインデックスの初期化を行います。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """データベースとテーブルの初期化"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    image_path TEXT,
                    is_notified BOOLEAN DEFAULT 0
                )
            """)
            # インデックス作成（検索パフォーマンス向上）
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_class_conf_time
                ON detections(class_name, confidence, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_timestamp_class
                ON detections(timestamp, class_name)
            """)
            conn.commit()

    def _get_today_start_utc(self) -> str:
        """
        ローカル時間の「今日の開始時刻（00:00）」に対応するUTC時刻文字列を取得する
        """
        # 現在のローカル時間から、ローカルの「今日の開始時刻（00:00）」を算出
        now_local = datetime.now().astimezone()
        today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # UTCに変換してISOフォーマット文字列として返す
        return today_start_local.astimezone(timezone.utc).isoformat()

    def add_detection(self, class_name: str, confidence: float, image_path: str, is_notified: bool):
        """
        検出結果をデータベースに保存する

        Args:
            class_name (str): 検出されたクラス名（例: 'chige', 'motsu', 'other'）
            confidence (float): 検出信頼度（0.0〜1.0）
            image_path (str): 保存された画像のパス
            is_notified (bool): LINE通知を送信したかどうか
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detections (timestamp, class_name, confidence, image_path, is_notified)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, class_name, confidence, image_path, is_notified))
            conn.commit()

    def register_detection_with_suppression(self, class_name: str, confidence: float, image_path: str,
                                          threshold: float, suppression_minutes: int) -> Tuple[bool, int]:
        """
        検出を登録し、通知すべきかどうかを判定する（トランザクションによるアトミック操作）
        レースコンディションを防ぐため、判定と登録を同時に行う。
        
        Args:
            class_name: クラス名
            confidence: 信頼度
            image_path: 画像パス
            threshold: 信頼度閾値
            suppression_minutes: 重複抑制時間（分）

        Returns:
            (should_notify, record_id): 通知すべきかどうかのフラグと、挿入されたレコードID
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        threshold_time = (datetime.now(timezone.utc) - timedelta(minutes=suppression_minutes)).isoformat()
        
        # isolation_level=Noneで自動トランザクションを無効化し、手動制御する
        with sqlite3.connect(self.db_path, isolation_level=None) as conn:
            try:
                # 書き込みロックを取得してトランザクション開始
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.cursor()
                
                # 直近の検出を確認
                cursor.execute("""
                    SELECT 1 FROM detections
                    WHERE class_name = ? AND confidence >= ? AND timestamp > ?
                    LIMIT 1
                """, (class_name, threshold, threshold_time))
                
                exists = cursor.fetchone() is not None
                
                # 検出済みなら通知しない(False)、未検出なら通知する(True)
                should_notify = not exists
                
                # 通知予定なら1(True)、そうでなければ0(False)でレコード作成
                # 通知予定として登録することで、他プロセスからの重複通知をブロックする
                is_notified_val = 1 if should_notify else 0
                
                cursor.execute("""
                    INSERT INTO detections (timestamp, class_name, confidence, image_path, is_notified)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, class_name, confidence, image_path, is_notified_val))
                
                record_id = cursor.lastrowid
                return should_notify, record_id
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    def update_notification_status(self, record_id: int, is_notified: bool):
        """通知ステータスを更新する（送信失敗時のロールバック用など）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE detections SET is_notified = ? WHERE id = ?", (1 if is_notified else 0, record_id))
            conn.commit()

    def get_recent_high_confidence_detection(self, class_name: str, threshold: float, minutes: int = 5) -> bool:
        """
        指定された時間内に同じクラスで、かつ閾値以上の信頼度の検出があったかを確認する
        （通知の有無は問わない）

        Args:
            class_name (str): 確認対象のクラス名
            threshold (float): 信頼度の閾値
            minutes (int): 遡る時間（分）。デフォルトは5分。

        Returns:
            bool: 条件に合致する検出がある場合はTrue
        """
        threshold_time = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM detections
                    WHERE class_name = ? AND confidence >= ? AND timestamp > ?
                )
            """, (class_name, threshold, threshold_time))
            exists = cursor.fetchone()[0]
            return bool(exists)

    def get_pipeline_stats_summary(self) -> Dict[str, int]:
        """
        パイプライン統計用の日次集計を取得する

        Note:
            タイムスタンプはUTCで保存されています。
            集計はローカル時間（システム時刻）の00:00:00以降を対象とします。

        Returns:
            Dict[str, int]:
                - total_processed: 本日の全検出数
                - successful_detections: 本日の成功検出数（現在は全検出数と同じ）
                - notification_sent: 本日の通知送信数
        """
        # UTCに変換して検索クエリに使用
        today_start_utc = self._get_today_start_utc()
        
        with sqlite3.connect(self.db_path) as conn:
            # 本メソッドは頻繁に呼び出されないため、毎回短命な接続を確立してクリーンにクローズする方針とする。
            cursor = conn.cursor()
            
            # 全処理数と通知送信数を1つのクエリで取得
            cursor.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_notified = 1 THEN 1 ELSE 0 END)
                FROM detections 
                WHERE timestamp >= ?
            """, (today_start_utc,))
            
            row = cursor.fetchone()
            total_processed = row[0]
            notification_sent = row[1] if row[1] is not None else 0
            
            return {
                "total_processed": total_processed,
                "successful_detections": total_processed,
                "notification_sent": notification_sent
            }

    def get_daily_stats(self) -> Dict[str, int]:
        """
        今日の検出統計を取得する
        
        Note:
            システムローカル時間の00:00:00以降のデータを集計します。
            内部的にUTCに変換して検索を行います。

        Returns:
            Dict[str, int]: クラス名をキー、検出数を値とする辞書
                            例: {'chige': 5, 'motsu': 3}
        """
        # UTCに変換して検索クエリに使用
        today_start_utc = self._get_today_start_utc()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT class_name, COUNT(*) FROM detections
                WHERE timestamp >= ?
                GROUP BY class_name
            """, (today_start_utc,))
            return dict(cursor.fetchall())
