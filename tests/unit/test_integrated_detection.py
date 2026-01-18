"""
Unit tests for ChigemotsuDetector class
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from PIL import Image

# テスト対象をインポート
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))

from scripts.integrated_detection import ChigemotsuDetector


class TestChigemotsuDetector(unittest.TestCase):
    """ChigemotsuDetectorのユニットテスト"""

    def setUp(self):
        """テスト前の準備"""
        # テスト用設定ファイルを作成
        self.test_config = {
            "model": {
                "model_path": "./models/test_model.tflite",
                "class_names": ["chige", "motsu", "other"],
                "threshold": 0.75
            },
            "line": {
                "credentials_file": "./config/line_credentials.json",
                "api_url": "https://api.line.me/v2/bot/message/push",
                "timeout_seconds": 15,
                "retry_count": 3
            },
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            },
            "logging": {
                "level": "INFO"
            }
        }

        # 一時的な設定ファイルを作成
        self.temp_config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_config, self.temp_config_file)
        self.temp_config_file.close()

        # テスト用画像を作成
        self.test_image = tempfile.NamedTemporaryFile(
            suffix='.jpg', delete=False
        )
        # 224x224のテスト画像を作成
        test_img = Image.new('RGB', (224, 224), color='red')
        test_img.save(self.test_image.name, 'JPEG')
        self.test_image.close()

    def tearDown(self):
        """テスト後のクリーンアップ"""
        # 一時ファイルを削除
        if os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)
        if os.path.exists(self.test_image.name):
            os.unlink(self.test_image.name)

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_init_success(self, mock_interpreter, mock_line_notifier):
        """正常な初期化のテスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # 初期化が正常に完了することを確認
            self.assertIsNotNone(detector.config)
            self.assertEqual(detector.class_names, ["chige", "motsu", "other"])
            self.assertIsNotNone(detector.line_notifier)

    def test_init_config_not_found(self):
        """設定ファイルが見つからない場合のテスト"""
        with self.assertRaises(FileNotFoundError):
            ChigemotsuDetector(config_path="nonexistent_config.json")

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_preprocess_image_success(self, mock_interpreter, mock_line_notifier):
        """画像前処理の成功テスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # 画像前処理を実行
            result = detector.preprocess_image(self.test_image.name)
            
            # 結果の検証
            self.assertIsNotNone(result)
            self.assertEqual(result.shape, (1, 224, 224, 3))
            self.assertTrue(np.all(result >= 0.0) and np.all(result <= 1.0))

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_preprocess_image_not_found(self, mock_interpreter, mock_line_notifier):
        """存在しない画像の前処理テスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # 存在しない画像の前処理
            result = detector.preprocess_image("nonexistent_image.jpg")
            
            # 結果がNoneであることを確認
            self.assertIsNone(result)

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_predict_success(self, mock_interpreter, mock_line_notifier):
        """推論の成功テスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]
        # 予測結果をモック
        mock_predictions = np.array([[0.1, 0.8, 0.1]])  # motsuが最高スコア
        mock_interpreter_instance.get_tensor.return_value = mock_predictions

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # テスト用の前処理済み画像を作成
            test_input = np.random.random((1, 224, 224, 3)).astype(np.float32)
            
            # 推論を実行
            result = detector.predict(test_input)
            
            # 結果の検証
            self.assertIsNotNone(result)
            self.assertEqual(result['class_name'], 'motsu')
            self.assertAlmostEqual(result['confidence'], 0.8, places=2)
            self.assertTrue(result['is_cat'])
            self.assertIn('inference_time', result)

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_predict_out_of_range_class(self, mock_interpreter, mock_line_notifier):
        """範囲外クラスの推論テスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]
        # 範囲外のクラスが予測される場合
        mock_predictions = np.array([[0.1, 0.1, 0.1, 0.7]])  # 4番目のクラス（範囲外）
        mock_interpreter_instance.get_tensor.return_value = mock_predictions

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # テスト用の前処理済み画像を作成
            test_input = np.random.random((1, 224, 224, 3)).astype(np.float32)
            
            # 推論を実行
            result = detector.predict(test_input)
            
            # 結果の検証
            self.assertIsNotNone(result)
            self.assertEqual(result['class_name'], 'unknown')

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_update_stats(self, mock_interpreter, mock_line_notifier):
        """統計情報更新のテスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=self.temp_config_file.name)
            
            # 初期統計を確認
            initial_stats = detector.get_stats()
            self.assertEqual(initial_stats['total_detections'], 0)
            self.assertEqual(initial_stats['chige_count'], 0)
            self.assertEqual(initial_stats['motsu_count'], 0)

            # chige検出をシミュレート
            chige_result = {'class_name': 'chige', 'confidence': 0.9}
            detector._update_stats(chige_result)

            # motsu検出をシミュレート
            motsu_result = {'class_name': 'motsu', 'confidence': 0.8}
            detector._update_stats(motsu_result)

            # 統計を確認
            updated_stats = detector.get_stats()
            self.assertEqual(updated_stats['total_detections'], 2)
            self.assertEqual(updated_stats['chige_count'], 1)
            self.assertEqual(updated_stats['motsu_count'], 1)


@pytest.mark.unit
class TestChigemotsuDetectorPytest:
    """pytestスタイルのユニットテスト"""

    @pytest.fixture
    def test_config(self):
        """テスト用設定ファイル"""
        return {
            "model": {
                "model_path": "./models/test_model.tflite",
                "class_names": ["chige", "motsu", "other"],
                "threshold": 0.75
            },
            "line": {
                "credentials_file": "./config/line_credentials.json",
                "api_url": "https://api.line.me/v2/bot/message/push"
            },
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            }
        }

    @pytest.fixture
    def temp_config_file(self, test_config):
        """一時的な設定ファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_file = f.name
        
        yield temp_file
        
        # クリーンアップ
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def test_image(self):
        """テスト用画像ファイル"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            test_img = Image.new('RGB', (224, 224), color='blue')
            test_img.save(f.name, 'JPEG')
            temp_file = f.name
        
        yield temp_file
        
        # クリーンアップ
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_load_config_success(self, mock_interpreter, mock_line_notifier, temp_config_file):
        """設定ファイル読み込みの成功テスト"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=temp_config_file)
            
            assert detector.config is not None
            assert "model" in detector.config
            assert "line" in detector.config
            assert "r2" in detector.config

    def test_config_validation_missing_file(self):
        """存在しない設定ファイルのテスト"""
        with pytest.raises(FileNotFoundError):
            ChigemotsuDetector(config_path="invalid_config.json")

    @patch('scripts.integrated_detection.LineImageNotifier')
    @patch('scripts.integrated_detection.tflite.Interpreter')
    def test_image_preprocessing_dimensions(self, mock_interpreter, mock_line_notifier, temp_config_file, test_image):
        """画像前処理の次元チェック"""
        # モックの設定
        mock_interpreter_instance = Mock()
        mock_interpreter.return_value = mock_interpreter_instance
        mock_interpreter_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_interpreter_instance.get_output_details.return_value = [
            {'index': 0}
        ]

        with patch('pathlib.Path.exists', return_value=True):
            detector = ChigemotsuDetector(config_path=temp_config_file)
            
            result = detector.preprocess_image(test_image)
            
            assert result is not None
            assert result.shape == (1, 224, 224, 3)
            assert result.dtype == np.float32
            assert np.all(result >= 0.0) and np.all(result <= 1.0)


if __name__ == '__main__':
    unittest.main()
