import sqlite3
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts.db_manager import DetectionDBManager

import tempfile
import shutil

@pytest.fixture
def temp_db():
    """テスト用の一時DBパスを提供するフィクスチャ"""
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test_detection.db"
    yield str(db_path)
    # クリーンアップ
    shutil.rmtree(tmp_dir)

@pytest.fixture
def db_manager(temp_db):
    """DBマネージャーのインスタンスを提供するフィクスチャ"""
    return DetectionDBManager(db_path=temp_db)

def test_init_db(temp_db):
    """DB初期化のテスト"""
    DetectionDBManager(db_path=temp_db)
    assert Path(temp_db).exists()
    
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detections'")
        assert cursor.fetchone() is not None

def test_add_detection(db_manager, temp_db):
    """検出結果の追加テスト"""
    db_manager.add_detection("chige", 0.95, "/tmp/image.jpg", True)
    
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT class_name, confidence, is_notified FROM detections")
        row = cursor.fetchone()
        assert row == ("chige", 0.95, 1)

def test_get_recent_high_confidence_detection(db_manager):
    """直近の高信頼度検出確認テスト"""
    threshold = 0.75
    # 1. まだ検出がない場合
    assert db_manager.get_recent_high_confidence_detection("chige", threshold, minutes=5) is False
    
    # 2. 高信頼度の検出を追加（通知の有無は問わない）
    db_manager.add_detection("chige", 0.9, "img1.jpg", False)
    assert db_manager.get_recent_high_confidence_detection("chige", threshold, minutes=5) is True
    
    # 3. 別のクラスの場合
    assert db_manager.get_recent_high_confidence_detection("motsu", threshold, minutes=5) is False
    
    # 4. 信頼度が低い場合
    db_manager.add_detection("motsu", 0.5, "img2.jpg", True)
    assert db_manager.get_recent_high_confidence_detection("motsu", threshold, minutes=5) is False

def test_get_pipeline_stats_summary(db_manager):
    """パイプライン統計サマリーの取得テスト"""
    # 今日のデータ
    db_manager.add_detection("chige", 0.9, "img1.jpg", True)
    db_manager.add_detection("motsu", 0.8, "img2.jpg", False)
    db_manager.add_detection("other", 0.9, "img3.jpg", True)
    
    summary = db_manager.get_pipeline_stats_summary()
    
    assert summary["total_processed"] == 3
    assert summary["notification_sent"] == 2

def test_get_recent_notification_time_limit(db_manager, temp_db):
    """時間の境界値テスト"""
    threshold = 0.75
    # 10分前のデータを手動で挿入 (UTC)
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            "INSERT INTO detections (timestamp, class_name, confidence, is_notified) VALUES (?, ?, ?, ?)",
            (old_time, "chige", 0.9, 1)
        )
    
    # 5分以内ならFalseになるはず
    assert db_manager.get_recent_high_confidence_detection("chige", threshold, minutes=5) is False
    # 15分以内ならTrueになるはず
    assert db_manager.get_recent_high_confidence_detection("chige", threshold, minutes=15) is True

def test_get_daily_stats(db_manager, temp_db):
    """日次統計のテスト"""
    # 今日のデータ
    db_manager.add_detection("chige", 0.9, "img1.jpg", True)
    db_manager.add_detection("chige", 0.8, "img2.jpg", False)
    db_manager.add_detection("motsu", 0.9, "img3.jpg", True)
    
    # 昨日のデータを手動挿入 (UTC)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            "INSERT INTO detections (timestamp, class_name, confidence, is_notified) VALUES (?, ?, ?, ?)",
            (yesterday.isoformat(), "chige", 0.9, 1)
        )
    
    stats = db_manager.get_daily_stats()
    
    # 今日の分だけ集計されているか確認
    assert stats["chige"] == 2  # 昨日のは含まない
    assert stats["motsu"] == 1
    assert stats.get("other", 0) == 0

def test_register_detection_with_suppression(db_manager, temp_db):
    """アトミックな検出登録と抑制のテスト"""
    threshold = 0.75
    
    # 初回の検出 -> 通知すべき(True)
    should_notify, rec_id = db_manager.register_detection_with_suppression(
        "chige", 0.9, "img1.jpg", threshold, 5
    )
    assert should_notify is True
    assert rec_id > 0
    
    # 直後の同じ検出 -> 通知すべきでない(False)
    should_notify, rec_id2 = db_manager.register_detection_with_suppression(
        "chige", 0.9, "img2.jpg", threshold, 5
    )
    assert should_notify is False
    assert rec_id2 > rec_id
    
    # 別のクラス -> 通知すべき(True)
    should_notify, _ = db_manager.register_detection_with_suppression(
        "motsu", 0.9, "img3.jpg", threshold, 5
    )
    assert should_notify is True

    # 通知失敗時の更新テスト
    db_manager.update_notification_status(rec_id, False)
    
    # ステータス更新確認
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_notified FROM detections WHERE id = ?", (rec_id,))
        assert cursor.fetchone()[0] == 0
