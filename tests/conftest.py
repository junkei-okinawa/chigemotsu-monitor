"""
pytest設定ファイル
テスト間で共有されるフィクスチャと設定を定義
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# プロジェクトのルートパスを設定
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "scripts"


@pytest.fixture(scope="session")
def project_root():
    """プロジェクトルートディレクトリのパス"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def scripts_path():
    """スクリプトディレクトリのパス"""
    return SCRIPTS_PATH


@pytest.fixture
def test_config():
    """テスト用の基本設定"""
    return {
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


@pytest.fixture
def line_credentials():
    """テスト用LINE認証情報"""
    return {
        "line_access_token": "test_line_access_token_12345",
        "line_user_id": "test_user_id_abcde"
    }


@pytest.fixture
def r2_credentials():
    """テスト用R2認証情報"""
    return {
        "account_id": "test_account_id_12345",
        "access_key_id": "test_access_key_abcde",
        "secret_access_key": "test_secret_access_key_xyz",
        "bucket_name": "test-chigemotsu-bucket",
        "public_url_base": "https://pub-test12345.r2.dev"
    }


@pytest.fixture
def temp_config_file(test_config):
    """一時的な設定ファイル"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_file = f.name
    
    yield temp_file
    
    # クリーンアップ
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def temp_line_credentials_file(line_credentials):
    """一時的なLINE認証ファイル"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(line_credentials, f)
        temp_file = f.name
    
    yield temp_file
    
    # クリーンアップ
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def temp_r2_credentials_file(r2_credentials):
    """一時的なR2認証ファイル"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(r2_credentials, f)
        temp_file = f.name
    
    yield temp_file
    
    # クリーンアップ
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def test_image_file():
    """テスト用画像ファイル"""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        # 簡単なJPEGヘッダーを作成
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00')
        f.write(b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t')
        f.write(b'\xff\xd9')  # JPEG終了マーカー
        temp_file = f.name
    
    yield temp_file
    
    # クリーンアップ
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def mock_tflite_interpreter():
    """TFLiteインタープリターのモック"""
    with patch('scripts.integrated_detection.tflite.Interpreter') as mock_interpreter:
        mock_instance = Mock()
        mock_interpreter.return_value = mock_instance
        mock_instance.get_input_details.return_value = [
            {'shape': [1, 224, 224, 3], 'index': 0}
        ]
        mock_instance.get_output_details.return_value = [{'index': 0}]
        yield mock_instance


@pytest.fixture
def mock_boto3_client():
    """boto3 S3クライアントのモック"""
    with patch('scripts.r2_uploader.boto3.client') as mock_boto3:
        mock_s3_client = Mock()
        mock_boto3.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.upload_file.return_value = None
        mock_s3_client.delete_object.return_value = {}
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}
        yield mock_s3_client


@pytest.fixture
def mock_line_api():
    """LINE API のモック"""
    with patch('scripts.line_image_notifier.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def mock_file_operations():
    """ファイル操作のモック"""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.stat') as mock_stat, \
         patch('pathlib.Path.read_bytes', return_value=b"fake_image_data"), \
         patch('time.time', return_value=1234567890):
        
        # ファイルサイズのモック
        mock_stat_result = Mock()
        mock_stat_result.st_size = 1024 * 1024  # 1MB
        mock_stat.return_value = mock_stat_result
        
        yield


@pytest.fixture
def mock_pil_image():
    """PIL Imageのモック"""
    with patch('PIL.Image.open') as mock_open:
        mock_image = Mock()
        mock_image.mode = 'RGB'
        mock_image.size = (1024, 768)
        mock_image.resize.return_value = mock_image
        mock_open.return_value = mock_image
        yield mock_image


# pytestマーカーの設定
def pytest_configure(config):
    """pytest設定"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "raspberry_pi: marks tests that require Raspberry Pi hardware"
    )


# テスト前の共通セットアップ
@pytest.fixture(autouse=True)
def setup_test_environment():
    """各テストの前に実行される共通セットアップ"""
    # ログレベルをテスト用に設定
    import logging
    logging.getLogger().setLevel(logging.WARNING)
    
    yield
    
    # テスト後のクリーンアップ（必要に応じて）
    pass


@pytest.fixture(autouse=True)
def disable_logging():
    """すべてのテストでログ機能を無効化"""
    import logging
    
    def mock_setup_logging(self):
        """ログ設定のモック - 基本的なloggerを設定"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.WARNING)  # テスト中は警告以上のみ
        # ハンドラーは追加しない（テスト中はファイル出力不要）
    
    # パッチを適用し、ログディレクトリ作成もモック
    with patch('scripts.integrated_detection.ChigemotsuDetector._setup_logging', mock_setup_logging), \
         patch('scripts.line_image_notifier.LineImageNotifier._setup_logging', mock_setup_logging), \
         patch('scripts.r2_uploader.R2Uploader._setup_logging', mock_setup_logging), \
         patch('pathlib.Path.mkdir'):  # ログディレクトリ作成をモック
        yield


# 条件付きテストスキップ用
def pytest_runtest_setup(item):
    """テスト実行前のセットアップ"""
    # Raspberry Pi専用テストのスキップ条件
    if item.get_closest_marker("raspberry_pi"):
        import platform
        if not platform.machine().startswith('arm'):
            pytest.skip("Raspberry Pi hardware required")


# テスト結果のカスタム表示
def pytest_runtest_makereport(item, call):
    """テスト結果のカスタマイズ"""
    if call.when == "call" and call.excinfo is not None:
        # テスト失敗時の追加情報を表示
        if hasattr(item, 'fixturenames'):
            print(f"\nTest '{item.name}' failed with fixtures: {item.fixturenames}")


# テストファイルの検出パターン
def pytest_collection_modifyitems(config, items):
    """テストアイテムの修正"""
    # 統合テストにslowマーカーを自動追加
    for item in items:
        if "integration" in item.fspath.basename:
            item.add_marker(pytest.mark.slow)
