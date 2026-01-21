import pytest
import sqlite3
from unittest.mock import patch
import sys
from pathlib import Path

# scriptsモジュールをインポートできるようにパスを追加
project_root = Path(__file__).parents[2]
sys.path.append(str(project_root))

from scripts.send_daily_summary import main

def test_send_daily_summary_success():
    """日次サマリー送信の成功パターン"""
    with patch('scripts.send_daily_summary.DetectionDBManager') as MockDB, \
         patch('scripts.send_daily_summary.LineImageNotifier') as MockNotifier, \
         patch('sys.argv', ["send_daily_summary.py"]):
        
        # モックの設定
        db_instance = MockDB.return_value
        # chige: 3, motsu: 2, other: 1
        db_instance.get_daily_stats.return_value = {"chige": 3, "motsu": 2, "other": 1}
        
        notifier_instance = MockNotifier.return_value
        notifier_instance.send_message.return_value = True

        # main関数実行
        main()
        
        # 検証: get_daily_statsが呼ばれたか
        db_instance.get_daily_stats.assert_called_once()
        
        # 検証: send_messageが呼ばれ、内容に集計結果が含まれているか
        notifier_instance.send_message.assert_called_once()
        args, _ = notifier_instance.send_message.call_args
        message = args[0]
        
        assert "三毛猫（ちげ）: 3回" in message
        assert "白黒猫（もつ）: 2回" in message
        assert "その他: 1回" in message
        assert "合計検出数: 6回" in message

def test_send_daily_summary_empty():
    """データが0件の場合のテスト"""
    with patch('scripts.send_daily_summary.DetectionDBManager') as MockDB, \
         patch('scripts.send_daily_summary.LineImageNotifier') as MockNotifier, \
         patch('sys.argv', ["send_daily_summary.py"]):
        
        db_instance = MockDB.return_value
        db_instance.get_daily_stats.return_value = {}  # 空の辞書
        
        notifier_instance = MockNotifier.return_value
        notifier_instance.send_message.return_value = True

        main()
        
        args, _ = notifier_instance.send_message.call_args
        message = args[0]
        
        assert "三毛猫（ちげ）: 0回" in message
        assert "合計検出数: 0回" in message

def test_send_daily_summary_db_error():
    """DBエラー時のテスト"""
    with patch('scripts.send_daily_summary.DetectionDBManager') as MockDB, \
         patch('scripts.send_daily_summary.LineImageNotifier') as MockNotifier, \
         patch('sys.argv', ["send_daily_summary.py"]):
        
        # DB初期化でエラー発生
        MockDB.side_effect = sqlite3.Error("DB Connection Failed")
        
        # SystemExit(1)が発生することを確認
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

def test_send_daily_summary_send_failure():
    """LINE送信失敗時のテスト"""
    with patch('scripts.send_daily_summary.DetectionDBManager') as MockDB, \
         patch('scripts.send_daily_summary.LineImageNotifier') as MockNotifier, \
         patch('sys.argv', ["send_daily_summary.py"]):
        
        db_instance = MockDB.return_value
        db_instance.get_daily_stats.return_value = {"chige": 1}
        
        notifier_instance = MockNotifier.return_value
        notifier_instance.send_message.return_value = False  # 送信失敗
        
        # SystemExit(1)が発生することを確認
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

def test_send_daily_summary_with_config_arg():
    """--config引数が正しくパースされるかのテスト"""
    custom_config_path = "/tmp/custom_config.json"
    with patch('scripts.send_daily_summary.DetectionDBManager') as MockDB,          patch('scripts.send_daily_summary.LineImageNotifier') as MockNotifier,          patch('sys.argv', ["send_daily_summary.py", "--config", custom_config_path]):
        
        db_instance = MockDB.return_value
        db_instance.get_daily_stats.return_value = {"chige": 1}
        notifier_instance = MockNotifier.return_value
        notifier_instance.send_message.return_value = True

        main()
        
        # LineImageNotifierがカスタム設定パスで初期化されたか確認
        MockNotifier.assert_called_with(config_path=custom_config_path)
