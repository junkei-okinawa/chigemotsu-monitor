"""
Integration tests for the entire chigemotsu detection system
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

try:
    import numpy as np
except ImportError:
    np = None

# TensorFlowとtfliteのモック設定（インポート前に設定）
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.append(str(Path(__file__).parent.parent / "fixtures"))

# モックモジュールを事前に設定
sys.modules['tflite_runtime'] = Mock()
sys.modules['tflite_runtime.interpreter'] = Mock()
sys.modules['tensorflow'] = Mock()

# mock tflite interpreter
mock_interpreter = Mock()
mock_interpreter.allocate_tensors = Mock()
mock_interpreter.set_tensor = Mock()
mock_interpreter.invoke = Mock()
mock_interpreter.get_tensor = Mock(return_value=[[0.1, 0.9]])  # mock prediction
mock_interpreter.get_input_details = Mock(return_value=[{'index': 0}])
mock_interpreter.get_output_details = Mock(return_value=[{'index': 0}])
sys.modules['tflite_runtime.interpreter'].Interpreter = Mock(return_value=mock_interpreter)

try:
    from scripts.integrated_detection import ChigemotsuDetector
    from scripts.line_image_notifier import LineImageNotifier
    from scripts.r2_uploader import R2Uploader
except ImportError:
    pytest.skip("Required modules not available", allow_module_level=True)


class TestChigemotsuSystemIntegration(unittest.TestCase):
    """システム全体の統合テスト"""

    def setUp(self):
        """テスト前の準備"""
        # テスト用設定を作成
        self.test_config = {
            "detection": {
                "model_path": "./weights/mobilenet_v2_cat_detection.tflite",
                "class_names": ["background", "cat"],
                "confidence_threshold": 0.5,
                "max_detections": 10,
                "input_size": [224, 224]
            },
            "line": {
                "api_url": "https://api.line.me/v2/bot/message/push",
                "credentials_file": "./config/line_credentials.json",
                "line_user_id": "test_user_id",
                "retry_count": 3,
                "retry_delay": 1.0,
                "timeout": 30
            },
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            },
            "image": {
                "quality": 85,
                "max_width": 1024,
                "max_height": 1024
            },
            "cleanup": {
                "enabled": True,
                "max_age_days": 30,
                "max_count": 1000
            }
        }

        self.line_credentials = {
            "line_access_token": "test_access_token",
            "line_user_id": "test_user_id"
        }

        self.r2_credentials = {
            "account_id": "test_account_id",
            "access_key_id": "test_access_key",
            "secret_access_key": "test_secret_key",
            "bucket_name": "test-bucket",
            "public_url_base": "https://pub-test.r2.dev"
        }

        # 一時設定ファイルを作成
        self.temp_config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.test_config, self.temp_config_file)
        self.temp_config_file.close()

        # テスト用画像ファイルのパス（実際のファイルを使用）
        self.test_image_path = str(Path(__file__).parent.parent / "fixtures" / "test_cat.jpg")

    def tearDown(self):
        """テスト後のクリーンアップ"""
        if hasattr(self, 'temp_config_file') and os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)

    def _create_mock_open(self):
        """ファイル読み込み用のモックを作成"""
        def open_side_effect(file, mode='r', *args, **kwargs):
            file_str = str(file)
            if 'line_credentials' in file_str:
                return mock_open(read_data=json.dumps(self.line_credentials)).return_value
            elif 'r2_credentials' in file_str:
                return mock_open(read_data=json.dumps(self.r2_credentials)).return_value
            else:
                return mock_open(read_data=json.dumps(self.test_config)).return_value
        return open_side_effect

    @patch('scripts.integrated_detection.tflite')
    @patch('scripts.line_image_notifier.requests.post')
    @patch('scripts.r2_uploader.boto3.client')
    @patch('PIL.Image.open')  # PILをモック
    def test_end_to_end_detection_flow(self, mock_pil_open, mock_boto3, mock_requests, mock_tflite):
        """エンドツーエンドの検出フローのテスト"""
        # PIL Imageモック
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_resized = Mock()
        mock_resized.size = (224, 224)
        mock_image.resize.return_value = mock_resized
        mock_pil_open.return_value = mock_image
        
        # TFLiteインタープリターのモック
        mock_interpreter = Mock()
        mock_tflite.Interpreter.return_value = mock_interpreter
        mock_interpreter.get_input_details.return_value = [{'shape': [1, 224, 224, 3], 'index': 0}]
        mock_interpreter.get_output_details.return_value = [{'index': 0}]
        
        # 推論結果をモック（tolist()メソッドを持つ）
        mock_output = Mock()
        mock_output.tolist.return_value = [[0.1, 0.9]]  # cat detection
        mock_interpreter.get_tensor.return_value = mock_output

        # R2アップローダーのモック
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.upload_file.return_value = None

        # LINE APIのモック
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response

        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            with patch('pathlib.Path.exists', return_value=True), \
                 patch('time.time', return_value=1234567890), \
                 patch('numpy.array') as mock_numpy:

                # Numpyの配列モック（数値演算をサポート）
                if np is not None:
                    mock_array = np.zeros((224, 224, 3), dtype=np.float32)
                else:
                    # numpyが利用できない場合は、数値演算をサポートするMockを作成
                    mock_array = Mock()
                    mock_array.shape = (224, 224, 3)
                    mock_array.__truediv__ = Mock(return_value=mock_array)
                    mock_array.__mul__ = Mock(return_value=mock_array)
                    mock_array.__sub__ = Mock(return_value=mock_array)
                    mock_array.__add__ = Mock(return_value=mock_array)
                mock_numpy.return_value = mock_array

                # sys.argvをモックしてコマンドライン引数をシミュレート
                with patch('sys.argv', ['integrated_detection.py', self.test_image_path, '--config', self.temp_config_file.name]):
                    
                    # integrated_detection.pyのmain関数を直接呼び出し
                    from scripts.integrated_detection import main
                    
                    try:
                        main()
                        
                        # TFLiteが呼び出されたことを確認
                        mock_tflite.Interpreter.assert_called_once()
                        
                        # モデルの推論が実行されたことを確認
                        mock_interpreter.set_tensor.assert_called()
                        mock_interpreter.invoke.assert_called()
                        
                        # R2への画像アップロードが実行されたことを確認
                        mock_boto3.assert_called()
                        mock_s3_client.upload_file.assert_called()
                        
                        # LINE通知が送信されたことを確認
                        mock_requests.assert_called()
                    
                    except Exception as e:
                        self.fail(f"統合テストが失敗しました: {e}")

    @patch('scripts.integrated_detection.tflite')
    @patch('scripts.r2_uploader.boto3.client')
    @patch('PIL.Image.open')  # PILをモック
    def test_low_confidence_detection(self, mock_pil_open, mock_boto3, mock_tflite):
        """低信頼度検出時の動作テスト"""
        # PIL Imageモック
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (800, 600)
        mock_resized = Mock()
        mock_resized.size = (224, 224)
        mock_image.resize.return_value = mock_resized
        mock_pil_open.return_value = mock_image
        
        # 低信頼度の検出結果をモック
        mock_interpreter = Mock()
        mock_tflite.Interpreter.return_value = mock_interpreter
        mock_interpreter.get_input_details.return_value = [{'shape': [1, 224, 224, 3], 'index': 0}]
        mock_interpreter.get_output_details.return_value = [{'index': 0}]
        
        # 推論結果をモック（背景検出：低信頼度）
        mock_output = Mock()
        mock_output.tolist.return_value = [[0.9, 0.1]]  # background detection
        mock_interpreter.get_tensor.return_value = mock_output

        # R2アップローダーのモック
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}

        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            with patch('pathlib.Path.exists', return_value=True), \
                 patch('time.time', return_value=1234567890), \
                 patch('numpy.array') as mock_numpy:

                # Numpyの配列モック（数値演算をサポート）
                if np is not None:
                    mock_array = np.zeros((224, 224, 3), dtype=np.float32)
                else:
                    # numpyが利用できない場合は、数値演算をサポートするMockを作成
                    mock_array = Mock()
                    mock_array.shape = (224, 224, 3)
                    mock_array.__truediv__ = Mock(return_value=mock_array)
                    mock_array.__mul__ = Mock(return_value=mock_array)
                    mock_array.__sub__ = Mock(return_value=mock_array)
                    mock_array.__add__ = Mock(return_value=mock_array)
                mock_numpy.return_value = mock_array

                # sys.argvをモックしてコマンドライン引数をシミュレート
                with patch('sys.argv', ['integrated_detection.py', self.test_image_path, '--config', self.temp_config_file.name]):
                    
                    from scripts.integrated_detection import main
                    
                    try:
                        main()
                        
                        # TFLiteが呼び出されたことを確認
                        mock_tflite.Interpreter.assert_called_once()
                        
                        # 低信頼度のため、R2アップロードは実行されない
                        mock_s3_client.upload_file.assert_not_called()
                    
                    except Exception as e:
                        self.fail(f"低信頼度検出テストが失敗しました: {e}")

    @patch('scripts.line_image_notifier.requests.post')
    @patch('scripts.r2_uploader.boto3.client')
    def test_notification_system_integration(self, mock_boto3, mock_requests):
        """通知システムの統合テスト"""
        # R2アップローダーのモック
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.upload_file.return_value = None

        # LINE APIのモック
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response

        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            with patch('pathlib.Path.exists', return_value=True), \
                 patch('time.time', return_value=1234567890):

                # 通知システムを作成
                from scripts.line_image_notifier import LineImageNotifier

                notifier = LineImageNotifier(config_path=self.temp_config_file.name)

                # 検出結果データ（実際のテスト画像を使用）
                confidence = 0.85
                class_name = 'cat'

                # 通知送信
                result = notifier.send_detection_notification(
                    image_path=self.test_image_path,
                    confidence=confidence,
                    class_name=class_name
                )

                # アサーション
                self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
