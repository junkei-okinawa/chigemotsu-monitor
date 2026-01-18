"""
R2Uploader クラスのユニットテスト
Cloudflare R2 ストレージとの連携機能をテスト
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, mock_open

import pytest
from botocore.exceptions import ClientError

from scripts.r2_uploader import R2Uploader


class TestR2Uploader(unittest.TestCase):
    """R2Uploader のユニットテスト"""

    def setUp(self):
        """テストの準備"""
        self.test_config = {
            "r2": {
                "credentials_file": "./config/r2_credentials.json"
            }
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
    
    def tearDown(self):
        """テストの後始末"""
        import os
        if os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)

    def _create_mock_open(self):
        """ファイル読み込み用のモックを作成"""
        def open_side_effect(file, mode='r', *args, **kwargs):
            if 'r2_credentials' in str(file):
                return mock_open(read_data=json.dumps(self.r2_credentials)).return_value
            else:
                return mock_open(read_data=json.dumps(self.test_config)).return_value
        return open_side_effect

    @patch('scripts.r2_uploader.boto3.client')
    def test_init_success(self, mock_boto3_client):
        """正常な初期化のテスト"""
        # boto3クライアントのモック設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # アサーション
            self.assertIsNotNone(uploader)
            self.assertEqual(uploader.bucket_name, "test-bucket")

    @patch('scripts.r2_uploader.boto3.client')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    @patch('pathlib.Path.read_bytes')
    @patch('time.time')
    def test_upload_image_success(self, mock_time, mock_read_bytes, mock_stat, mock_exists, mock_boto3_client):
        """画像アップロードの成功テスト"""
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.upload_file.return_value = None

        # ファイル操作のモック
        mock_exists.return_value = True
        mock_stat_result = Mock()
        mock_stat_result.st_size = 1024 * 1024  # 1MB
        mock_stat.return_value = mock_stat_result
        mock_read_bytes.return_value = b"fake_image_data"
        mock_time.return_value = 1234567890

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # アップロード実行
            result_url = uploader.upload_image("/path/to/test_image.jpg")

            # アサーション
            self.assertIsNotNone(result_url)
            self.assertTrue(result_url.startswith("https://"))

    @patch('scripts.r2_uploader.boto3.client')
    @patch('pathlib.Path.exists')
    def test_upload_image_file_not_found(self, mock_exists, mock_boto3_client):
        """存在しないファイルのアップロードテスト"""
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_exists.return_value = False

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # 存在しないファイルをアップロード（例外が発生することを期待）
            with self.assertRaises(FileNotFoundError):
                uploader.upload_image("/path/to/nonexistent.jpg")

    @patch('scripts.r2_uploader.boto3.client')
    def test_list_images(self, mock_boto3_client):
        """画像一覧取得のテスト"""
        from datetime import datetime, timezone
        
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}

        # list_objects_v2のレスポンスをモック（datetimeオブジェクトを使用）
        mock_response = {
            'Contents': [
                {
                    'Key': 'chigemotsu/test_image1.jpg',
                    'Size': 1024,
                    'LastModified': datetime(2023, 1, 1, tzinfo=timezone.utc)
                },
                {
                    'Key': 'chigemotsu/test_image2.jpg',
                    'Size': 2048,
                    'LastModified': datetime(2023, 1, 2, tzinfo=timezone.utc)
                }
            ]
        }
        mock_s3_client.list_objects_v2.return_value = mock_response

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # 画像一覧取得
            images = uploader.list_images()

            # アサーション
            self.assertEqual(len(images), 2)
            self.assertEqual(images[0]['key'], 'chigemotsu/test_image1.jpg')

    @patch('scripts.r2_uploader.boto3.client')
    def test_delete_image(self, mock_boto3_client):
        """画像削除のテスト"""
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.delete_object.return_value = {}

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # 画像削除
            result = uploader.delete_image("test_image.jpg")

            # アサーション
            self.assertTrue(result)

    @patch('scripts.r2_uploader.boto3.client')
    def test_test_connection_success(self, mock_boto3_client):
        """接続テストの成功テスト"""
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.list_objects_v2.return_value = {'Contents': []}

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open()

            uploader = R2Uploader(config_path=self.temp_config_file.name)

            # 接続テスト
            result = uploader.test_connection()

            # アサーション
            self.assertTrue(result)


class TestR2UploaderPytest:
    """pytest形式のR2Uploaderテスト"""

    def _create_mock_open(self, test_config, r2_credentials):
        """ファイル読み込み用のモックを作成"""
        def open_side_effect(file, mode='r', *args, **kwargs):
            if 'r2_credentials' in str(file):
                return mock_open(read_data=json.dumps(r2_credentials)).return_value
            else:
                return mock_open(read_data=json.dumps(test_config)).return_value
        return open_side_effect

    @patch('scripts.r2_uploader.boto3.client')
    def test_bucket_stats(self, mock_boto3_client, test_config, r2_credentials, temp_config_file):
        """バケット統計取得のテスト"""
        from datetime import datetime, timezone
        
        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}

        # list_images をモック（datetimeオブジェクトを使用）
        mock_response = {
            'Contents': [
                {
                    'Key': 'test1.jpg', 
                    'Size': 1024,
                    'LastModified': datetime(2023, 1, 1, tzinfo=timezone.utc)
                },
                {
                    'Key': 'test2.jpg', 
                    'Size': 2048,
                    'LastModified': datetime(2023, 1, 2, tzinfo=timezone.utc)
                }
            ]
        }
        mock_s3_client.list_objects_v2.return_value = mock_response

        # ファイル読み込みをモック
        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open(test_config, r2_credentials)

            uploader = R2Uploader(config_path=temp_config_file)

            # バケット統計取得
            stats = uploader.get_bucket_stats()

            # アサーション
            assert stats is not None
            assert 'total_images' in stats
            assert stats['total_images'] == 2
            assert 'total_size_mb' in stats

    @patch('scripts.r2_uploader.boto3.client')
    def test_url_generation_with_custom_domain(self, mock_boto3_client, test_config, temp_config_file):
        """カスタムドメイン使用時のURL生成テスト"""
        # カスタムドメインを含む認証情報
        r2_credentials_with_domain = {
            "account_id": "test_account_id",
            "access_key_id": "test_access_key",
            "secret_access_key": "test_secret_key",
            "bucket_name": "test-bucket",
            "public_url_base": "https://pub-test.r2.dev",
            "custom_domain": "images.example.com"
        }

        # モックの設定
        mock_s3_client = Mock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_bucket.return_value = {}
        mock_s3_client.upload_file.return_value = None

        with patch('builtins.open', create=True) as mock_open_func:
            mock_open_func.side_effect = self._create_mock_open(test_config, r2_credentials_with_domain)

            with patch('pathlib.Path.exists', return_value=True), \
                 patch('pathlib.Path.stat') as mock_stat, \
                 patch('pathlib.Path.read_bytes', return_value=b"test"), \
                 patch('time.time', return_value=1234567890):

                mock_stat_result = Mock()
                mock_stat_result.st_size = 1024
                mock_stat.return_value = mock_stat_result

                uploader = R2Uploader(config_path=temp_config_file)

                # アップロード実行
                result_url = uploader.upload_image("test.jpg")

                # アサーション
                assert result_url is not None
                assert "images.example.com" in result_url


if __name__ == '__main__':
    unittest.main()
