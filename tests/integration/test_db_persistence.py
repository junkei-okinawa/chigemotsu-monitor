import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from pathlib import Path
from scripts.chigemotsu_pipeline import ChigemotsuPipeline
from scripts.db_manager import DetectionDBManager

import tempfile
import shutil
import os

@pytest.fixture
def integration_env():
    """統合テスト用の環境セットアップ"""
    tmp_dir = tempfile.mkdtemp()
    log_dir = Path(tmp_dir) / "logs"
    log_dir.mkdir()
    config_file = Path(tmp_dir) / "config.json"
    db_file = Path(tmp_dir) / "detection.db"
    
    # ダミー設定ファイル
    import json
    with open(config_file, 'w') as f:
        json.dump({
            "model": {"threshold": 0.75},
            "line": {"notification_enabled": True},
            "motion": {"cleanup_days": 1}
        }, f)
        
    yield {"config": str(config_file), "db": str(db_file)}
    
    # クリーンアップ
    shutil.rmtree(tmp_dir)

class MockPipeline(ChigemotsuPipeline):
    """ログ設定を無効化したテスト用パイプラインクラス"""
    def _setup_logging(self):
        self.logger = MagicMock()

def test_pipeline_db_integration(integration_env):
    """パイプライン実行とDB保存の統合テスト"""
    config_path = integration_env["config"]
    db_path = integration_env["db"]
    
    with patch('scripts.chigemotsu_pipeline.ChigemotsuDetector') as MockDetector, \
         patch('scripts.chigemotsu_pipeline.LineImageNotifier') as MockNotifier:
        
        # ログ設定を無効化したサブクラスを使用
        pipeline = MockPipeline(config_path=config_path)
        
        # DBマネージャーをテスト用DBで再初期化して差し替え
        pipeline.db_manager = DetectionDBManager(db_path=db_path)
        
        # モックの設定
        pipeline.detector.process_image.return_value = {
            "class_name": "chige", "confidence": 0.9, "box": []
        }
        pipeline.notifier.send_detection_notification.return_value = True
        
        # 1回目: 通知されるはず
        pipeline.process_motion_image("img1.jpg")
        
        # 検証: DBに保存されたか
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM detections WHERE is_notified=1")
            assert cursor.fetchone()[0] == 1
            
        # 2回目: 直後なので通知抑制されるはず（DBには保存されるがis_notified=0）
        pipeline.process_motion_image("img2.jpg")
        
        # 検証: 通知メソッドは呼ばれていない（前回と合わせて1回のみ）
        assert pipeline.notifier.send_detection_notification.call_count == 1
        
        # 検証: DBには2レコードあるはず（1つは通知済み、1つは未通知）
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM detections")
            assert cursor.fetchone()[0] == 2
            
            cursor.execute("SELECT is_notified FROM detections ORDER BY id DESC LIMIT 1")
            assert cursor.fetchone()[0] == 0  # 最新は未通知
