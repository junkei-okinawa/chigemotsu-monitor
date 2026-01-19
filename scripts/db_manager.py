import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

class DetectionDBManager:
    """検出結果の保存と統計情報の取得を行うデータベースマネージャー"""

    def __init__(self, db_path: str = "logs/detection.db"):
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
                CREATE INDEX IF NOT EXISTS idx_detections_class_notified_time
                ON detections(class_name, is_notified, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_timestamp_class
                ON detections(timestamp, class_name)
            """)
            conn.commit()

    def add_detection(self, class_name: str, confidence: float, image_path: str, is_notified: bool):
        """
        検出結果をデータベースに保存する

        Args:
            class_name (str): 検出されたクラス名（例: 'chige', 'motsu', 'other'）
            confidence (float): 検出信頼度（0.0〜1.0）
            image_path (str): 保存された画像のパス
            is_notified (bool): LINE通知を送信したかどうか
        """
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO detections (timestamp, class_name, confidence, image_path, is_notified)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, class_name, confidence, image_path, is_notified))
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
        threshold_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM detections
                WHERE class_name = ? AND confidence >= ? AND timestamp > ?
            """, (class_name, threshold, threshold_time))
            count = cursor.fetchone()[0]
            return count > 0

    def get_pipeline_stats_summary(self) -> Dict[str, int]:
        """
        パイプライン統計用の日次集計を取得する

        Returns:
            Dict[str, int]:
                - total_processed: 本日の全検出数
                - notification_sent: 本日の通知送信数
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 全処理数（本日のレコード数）
            cursor.execute("SELECT COUNT(*) FROM detections WHERE timestamp >= ?", (today_start,))
            total_processed = cursor.fetchone()[0]
            
            # 通知送信数
            cursor.execute("SELECT COUNT(*) FROM detections WHERE timestamp >= ? AND is_notified = 1", (today_start,))
            notification_sent = cursor.fetchone()[0]
            
            return {
                "total_processed": total_processed,
                "notification_sent": notification_sent
            }

    def get_daily_stats(self) -> Dict[str, int]:
        """
        今日の検出統計を取得する
        
        システムローカル時間の00:00:00以降のデータを集計する。

        Returns:
            Dict[str, int]: クラス名をキー、検出数を値とする辞書
                            例: {'chige': 5, 'motsu': 3}
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT class_name, COUNT(*) FROM detections
                WHERE timestamp >= ?
                GROUP BY class_name
            """, (today_start,))
            return dict(cursor.fetchall())
