import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from scripts.chigemotsu_pipeline import ChigemotsuPipeline

import tempfile
import shutil
import os

@pytest.fixture
def mock_pipeline():
    """モック化されたパイプラインフィクスチャ"""
    tmp_dir = tempfile.mkdtemp()
    config_path = Path(tmp_dir) / "config.json"
    import json
    with open(config_path, 'w') as f:
        json.dump({"line": {"notification_enabled": True}}, f)

    with patch('scripts.chigemotsu_pipeline.ChigemotsuDetector') as MockDetector, \
         patch('scripts.chigemotsu_pipeline.LineImageNotifier') as MockNotifier, \
         patch('scripts.chigemotsu_pipeline.DetectionDBManager') as MockDB:
        
        pipeline = ChigemotsuPipeline(config_path=str(config_path))
        
        # 各コンポーネントのモックを取得
        pipeline.detector = MockDetector.return_value
        pipeline.notifier = MockNotifier.return_value
        pipeline.db_manager = MockDB.return_value
        
        yield pipeline
    
    # クリーンアップ
    shutil.rmtree(tmp_dir)

def test_notification_sent_when_no_recent_history(mock_pipeline):
    """直近の通知がない場合、通知が送信されること"""
    # 設定: 検出成功(chige, 0.9)、直近通知なし
    mock_pipeline.detector.process_image.return_value = {
        "class_name": "chige", "confidence": 0.9, "box": []
    }
    mock_pipeline.db_manager.get_recent_notification.return_value = False
    mock_pipeline.notifier.send_detection_notification.return_value = True

    # 実行
    mock_pipeline.process_motion_image("test.jpg")

    # 検証: 通知メソッドが呼ばれたか
    mock_pipeline.notifier.send_detection_notification.assert_called_once()
    # 検証: DBに通知済み(True)として保存されたか
    mock_pipeline.db_manager.add_detection.assert_called_with("chige", 0.9, "test.jpg", True)

def test_notification_skipped_when_recent_history_exists(mock_pipeline):
    """直近の通知がある場合、通知がスキップされること"""
    # 設定: 検出成功(chige, 0.9)、直近通知あり(True)
    mock_pipeline.detector.process_image.return_value = {
        "class_name": "chige", "confidence": 0.9, "box": []
    }
    mock_pipeline.db_manager.get_recent_notification.return_value = True

    # 実行
    mock_pipeline.process_motion_image("test.jpg")

    # 検証: 通知メソッドが呼ばれていないこと
    mock_pipeline.notifier.send_detection_notification.assert_not_called()
    # 検証: DBに未通知(False)として保存されたか（ログ目的）
    mock_pipeline.db_manager.add_detection.assert_called_with("chige", 0.9, "test.jpg", False)

def test_notification_skipped_low_confidence(mock_pipeline):
    """信頼度が低い場合、通知がスキップされ、DBには未通知として記録されること"""
    # 設定: 検出成功だが信頼度低い(0.5)
    mock_pipeline.detector.process_image.return_value = {
        "class_name": "chige", "confidence": 0.5, "box": []
    }
    # configの閾値はデフォルト0.75

    # 実行
    mock_pipeline.process_motion_image("test.jpg")

    # 検証: 通知なし
    mock_pipeline.notifier.send_detection_notification.assert_not_called()
    # 検証: DBに未通知(False)として保存
    mock_pipeline.db_manager.add_detection.assert_called_with("chige", 0.5, "test.jpg", False)

