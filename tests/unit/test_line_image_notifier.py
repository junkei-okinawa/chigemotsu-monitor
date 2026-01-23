"""
Unit tests for LineImageNotifier class
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# テスト対象をインポート
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))

try:
    from scripts.line_image_notifier import LineImageNotifier
except ImportError:
    pytest.skip("LineImageNotifier module not available", allow_module_level=True)


class TestLineImageNotifier(unittest.TestCase):
    """LineImageNotifierのユニットテスト"""

    def setUp(self):
        """テスト前の準備"""
        # テスト用設定
        self.test_config = {
            "line": {
                "credentials_file": "./config/line_credentials.json",
                "api_url": "https://api.line.me/v2/bot/message/push",
                "line_user_id": "test_user_id",
                "timeout_seconds": 15,
                "retry_count": 3
            },
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            }
        }

        # LINE認証情報
        self.line_credentials = {
            "line_access_token": "test_access_token",
            "line_user_id": "test_user_id"
        }

        # 一時的な設定ファイルを作成
        self.temp_config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_config, self.temp_config_file)
        self.temp_config_file.close()

        # 一時的なLINE認証ファイルを作成
        self.temp_line_creds_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.line_credentials, self.temp_line_creds_file)
        self.temp_line_creds_file.close()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # 一時ファイルを削除
        if os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)
        if os.path.exists(self.temp_line_creds_file.name):
            os.unlink(self.temp_line_creds_file.name)

    @patch('scripts.line_image_notifier.R2Uploader')
    def test_init_success(self, mock_r2_uploader):
        """正常な初期化のテスト"""
        # R2Uploaderのモック設定
        mock_r2_uploader.return_value = Mock()

        # LINE認証ファイルの読み込みをモック
        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(self.test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(self.line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=self.temp_config_file.name)
            
            # 初期化が正常に完了することを確認
            self.assertIsNotNone(notifier.config)
            self.assertIn('line', notifier.config)
            self.assertEqual(notifier.config['line']['line_access_token'], 'test_access_token')

    def test_init_missing_config(self):
        """設定ファイルが見つからない場合のテスト"""
        with self.assertRaises(FileNotFoundError):
            LineImageNotifier(config_path="nonexistent_config.json")

    @patch('scripts.line_image_notifier.R2Uploader')
    @patch('scripts.line_image_notifier.requests.post')
    def test_send_line_message_success(self, mock_post, mock_r2_uploader):
        """LINE メッセージ送信の成功テスト"""
        # モックの設定
        mock_r2_uploader.return_value = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # LINE認証ファイルの読み込みをモック
        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(self.test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(self.line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=self.temp_config_file.name)
            
            # メッセージ送信をテスト
            result = notifier._send_line_message(
                image_url="https://example.com/test.jpg",
                message="Test message"
            )
            
            # 結果の検証
            self.assertTrue(result)
            mock_post.assert_called_once()

    @patch('scripts.line_image_notifier.R2Uploader')
    @patch('scripts.line_image_notifier.requests.post')
    def test_send_line_message_failure(self, mock_post, mock_r2_uploader):
        """LINE メッセージ送信の失敗テスト"""
        # モックの設定
        mock_r2_uploader.return_value = Mock()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        # LINE認証ファイルの読み込みをモック
        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(self.test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(self.line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=self.temp_config_file.name)
            
            # メッセージ送信をテスト
            result = notifier._send_line_message(
                image_url="https://example.com/test.jpg",
                message="Test message"
            )
            
            # 結果の検証
            self.assertFalse(result)

    @patch('scripts.line_image_notifier.R2Uploader')
    def test_send_detection_notification(self, mock_r2_uploader):
        """検出通知の送信テスト"""
        # R2Uploaderのモック設定
        mock_r2_instance = Mock()
        mock_r2_instance.upload_image.return_value = "https://example.com/test.jpg"
        mock_r2_instance.cleanup_old_images.return_value = []
        mock_r2_uploader.return_value = mock_r2_instance

        # LINE認証ファイルの読み込みをモック
        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(self.test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(self.line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=self.temp_config_file.name)
            
            # _send_line_messageをモック
            with patch.object(notifier, '_send_line_message', return_value=True) as mock_send:
                result = notifier.send_detection_notification(
                    image_path="/path/to/test.jpg",
                    confidence=85.0,
                    class_name="chige"
                )
                
                # 結果の検証
                self.assertTrue(result)
                mock_send.assert_called_once()
                
                # 呼び出された引数を確認
                args, kwargs = mock_send.call_args
                self.assertIn("chige", args[1])  # メッセージにクラス名が含まれる
                self.assertIn("85.0%", args[1])  # 信頼度が含まれる


@pytest.mark.unit
class TestLineImageNotifierPytest:
    """pytestスタイルのユニットテスト"""

    @pytest.fixture
    def test_config(self):
        """テスト用設定"""
        return {
            "line": {
                "credentials_file": "./config/line_credentials.json",
                "api_url": "https://api.line.me/v2/bot/message/push",
                "line_user_id": "test_user_id",
                "timeout_seconds": 15,
                "retry_count": 3
            },
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            }
        }

    @pytest.fixture
    def line_credentials(self):
        """LINE認証情報"""
        return {
            "line_access_token": "test_access_token",
            "line_user_id": "test_user_id"
        }

    @pytest.fixture
    def temp_config_file(self, test_config):
        """一時的な設定ファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_file = f.name
        
        yield temp_file
        
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @patch('scripts.line_image_notifier.R2Uploader')
    def test_config_loading(self, mock_r2_uploader, test_config, line_credentials, temp_config_file):
        """設定ファイル読み込みのテスト"""
        mock_r2_uploader.return_value = Mock()

        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=temp_config_file)
            
            assert notifier.config is not None
            assert 'line' in notifier.config
            assert notifier.config['line']['line_access_token'] == 'test_access_token'

    def test_invalid_config_path(self):
        """無効な設定ファイルパスのテスト"""
        with pytest.raises(FileNotFoundError):
            LineImageNotifier(config_path="invalid_path.json")

    @patch('scripts.line_image_notifier.R2Uploader')
    @patch('scripts.line_image_notifier.requests.post')
    def test_message_format(self, mock_post, mock_r2_uploader, test_config, line_credentials, temp_config_file):
        """メッセージフォーマットのテスト"""
        # モックの設定
        mock_r2_uploader.return_value = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch('builtins.open', create=True) as mock_open:
            # 設定ファイルの読み込み
            mock_config = unittest.mock.mock_open(read_data=json.dumps(test_config))
            mock_credentials = unittest.mock.mock_open(read_data=json.dumps(line_credentials))
            
            def open_side_effect(file, mode='r', *args, **kwargs):
                if 'line_credentials' in str(file):
                    return mock_credentials.return_value
                else:
                    return mock_config.return_value
            
            mock_open.side_effect = open_side_effect

            notifier = LineImageNotifier(config_path=temp_config_file)
            
            result = notifier._send_line_message(
                image_url="https://example.com/test.jpg",
                message="Test message"
            )
            
            assert result is True
            
            # POST呼び出しの引数を確認
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert 'to' in payload
            assert 'messages' in payload
            assert len(payload['messages']) == 2  # テキストメッセージ + 画像メッセージ
            
            # 画像メッセージの形式を確認
            image_message = payload['messages'][1]
            assert image_message['type'] == 'image'
            assert image_message['originalContentUrl'] == "https://example.com/test.jpg"


if __name__ == '__main__':
    unittest.main()
