#!/usr/bin/env python3
"""
Cloudflare R2画像アップローダー
S3互換APIでRaspberry Pi Zero対応
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, NoCredentialsError

# パッケージリソースアクセス用
try:
    from importlib import resources
except ImportError:
    # Python 3.8以前の場合
    import importlib_resources as resources

script_path = Path(__file__)
project_root = script_path.parent.parent

class R2Uploader:
    def __init__(self, config_path=None):
        """Cloudflare R2アップローダー初期化"""
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()

        # R2設定を取得
        r2_config = self.config.get("r2", {})

        self.account_id = r2_config.get("account_id")
        self.access_key_id = r2_config.get("access_key_id")
        self.secret_access_key = r2_config.get("secret_access_key")
        self.bucket_name = r2_config.get("bucket_name")
        self.public_url_base = r2_config.get("public_url_base")  # 正しい公開URLベース
        self.custom_domain = r2_config.get("custom_domain")  # オプション

        if not all(
            [
                self.account_id,
                self.access_key_id,
                self.secret_access_key,
                self.bucket_name,
            ]
        ):
            raise ValueError("Cloudflare R2 configuration missing")

        # R2のS3互換エンドポイント
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        # ログ設定
        self._setup_logging()

        # S3クライアント初期化
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=Config(signature_version="s3v4"),
                region_name="auto",  # R2では'auto'を使用
            )

            # 接続テスト
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"R2 client initialized for bucket: {self.bucket_name}")

        except NoCredentialsError:
            raise ValueError("R2 credentials not found or invalid")
        except ClientError as e:
            raise ValueError(f"R2 bucket access failed: {e}")

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルの読み込み"""
        if self.config_path is None:
            # パッケージリソースから設定ファイルを読み込み
            try:
                config_text = (
                    resources.files("config")
                    .joinpath("config.json")
                    .read_text(encoding="utf-8")
                )
                config = json.loads(config_text)
            except (FileNotFoundError, ModuleNotFoundError):
                raise FileNotFoundError(
                    "パッケージリソースから設定ファイルを読み込めません"
                )
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"設定ファイルが見つかりません: {self.config_path}"
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"設定ファイルの形式が正しくありません: {e}")

        # R2設定を読み込み
        r2_config = self._load_r2_credentials(config)
        config["r2"] = r2_config

        return config

    def _load_r2_credentials(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """R2認証情報の読み込み"""
        r2_config = config.get("r2", {})

        # credentials_fileから読み込み
        if "credentials_file" in r2_config:
            credentials_file = r2_config["credentials_file"]

            if self.config_path is None:
                # パッケージリソースから認証情報を読み込み
                try:
                    r2_credentials_text = (
                        resources.files("config")
                        .joinpath("r2_credentials.json")
                        .read_text(encoding="utf-8")
                    )
                    r2_credentials = json.loads(r2_credentials_text)
                    return r2_credentials
                except (FileNotFoundError, ModuleNotFoundError):
                    raise FileNotFoundError(
                        "R2認証ファイルがパッケージに含まれていません"
                    )
            else:
                # 相対パスの場合は絶対パスに変換
                if not os.path.isabs(credentials_file):
                    # 相対パスを config.json の位置を基準として解決
                    credentials_file = self.config_path.parent / credentials_file.lstrip("./")
                else:
                    credentials_file = Path(credentials_file)

                try:
                    with open(credentials_file, "r", encoding="utf-8") as f:
                        r2_credentials = json.load(f)
                    return r2_credentials

                except FileNotFoundError:
                    print(f"エラー: R2認証ファイルが見つかりません: {credentials_file}")
                    raise
                except json.JSONDecodeError as e:
                    print(f"エラー: R2認証ファイルの形式が正しくありません: {e}")
                    raise

        # フォールバック: 従来の形式
        return r2_config

    def _setup_logging(self):
        """ログ設定"""
        if self.config_path:
            # 従来のファイルパスベース
            log_dir = self.config_path.parent.parent / "logs"
        else:
            # パッケージリソース使用時はカレントディレクトリのlogsフォルダ
            log_dir = Path.cwd() / "logs"

        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "r2_uploader.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def upload_image(self, image_path, description=""):
        """画像をR2にアップロードして公開URLを返す"""
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # ファイルサイズチェック
        file_size = image_path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB制限
            raise ValueError("File size too large (max 10MB)")

        # ユニークなファイル名生成
        timestamp = str(int(time.time()))
        hash_obj = hashlib.md5(image_path.read_bytes())
        filename = f"chigemotsu_{timestamp}_{hash_obj.hexdigest()[:8]}.jpg"
        key = f"chigemotsu/{filename}"

        try:
            # メタデータ準備
            metadata = {
                "description": description,
                "upload_time": timestamp,
                "original_filename": image_path.name,
            }

            # R2にアップロード
            self.s3_client.upload_file(
                str(image_path),
                self.bucket_name,
                key,
                ExtraArgs={
                    "ACL": "public-read",
                    "ContentType": "image/jpeg",
                    "Metadata": metadata,
                    "CacheControl": "max-age=86400",  # 1日キャッシュ
                },
            )

            # 公開URLを生成
            if self.custom_domain:
                public_url = f"https://{self.custom_domain}/{key}"
            elif self.public_url_base:
                public_url = f"{self.public_url_base}/{key}"
            else:
                # フォールバック: 従来のURLパターン（非推奨）
                public_url = f"https://pub-{self.account_id}.r2.dev/{key}"

            logging.info(f"Image uploaded to R2: {public_url}")
            return public_url

        except ClientError as e:
            logging.error(f"R2 upload failed: {e}")
            raise Exception(f"R2 upload failed: {e}")

    def delete_image(self, image_url_or_key):
        """R2から画像を削除"""
        try:
            # URLの場合はキーを抽出
            if image_url_or_key.startswith("http"):
                if self.custom_domain and self.custom_domain in image_url_or_key:
                    key = image_url_or_key.split(f"{self.custom_domain}/")[1]
                elif self.public_url_base and self.public_url_base in image_url_or_key:
                    key = image_url_or_key.split(f"{self.public_url_base}/")[1]
                else:
                    # フォールバック: 従来のURLパターン
                    key = image_url_or_key.split(f"pub-{self.account_id}.r2.dev/")[1]
            else:
                key = image_url_or_key

            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)

            logging.info(f"Image deleted from R2: {key}")
            return True

        except Exception as e:
            logging.error(f"R2 delete failed: {e}")
            return False

    def list_images(self, max_keys=100):
        """R2内の画像一覧を取得"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix="chigemotsu/", MaxKeys=max_keys
            )

            images = []
            for obj in response.get("Contents", []):
                if self.custom_domain:
                    url = f"https://{self.custom_domain}/{obj['Key']}"
                elif self.public_url_base:
                    url = f"{self.public_url_base}/{obj['Key']}"
                else:
                    url = f"https://pub-{self.account_id}.r2.dev/{obj['Key']}"

                images.append(
                    {
                        "key": obj["Key"],
                        "url": url,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    }
                )

            return images

        except ClientError as e:
            logging.error(f"R2 list failed: {e}")
            return []

    def cleanup_old_images(self, max_age_days=7):
        """古い画像を削除"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 3600)

            images = self.list_images(max_keys=1000)
            deleted_count = 0

            for image in images:
                try:
                    # ファイル名から作成時刻を取得
                    filename = Path(image["key"]).name
                    timestamp_str = filename.split("_")[
                        1
                    ]  # chigemotsu_TIMESTAMP_hash.jpg
                    file_time = int(timestamp_str)

                    if file_time < cutoff_time:
                        self.s3_client.delete_object(
                            Bucket=self.bucket_name, Key=image["key"]
                        )
                        deleted_count += 1
                        logging.info(f"Deleted old image: {image['key']}")

                except (ValueError, IndexError):
                    # タイムスタンプが取得できない場合はスキップ
                    continue

            logging.info(f"Cleanup completed: {deleted_count} images deleted")
            return deleted_count

        except Exception as e:
            logging.error(f"Cleanup failed: {e}")
            return 0

    def get_bucket_stats(self):
        """バケット統計を取得"""
        try:
            images = self.list_images(max_keys=1000)

            total_count = len(images)
            total_size = sum(img["size"] for img in images)

            return {
                "total_images": total_count,
                "total_size_mb": total_size / (1024 * 1024),
                "bucket_name": self.bucket_name,
                "account_id": self.account_id,
                "endpoint_url": self.endpoint_url,
            }

        except Exception as e:
            logging.error(f"Stats retrieval failed: {e}")
            return {}

    def test_connection(self):
        """R2接続テスト"""
        try:
            # バケットの存在確認
            self.s3_client.head_bucket(Bucket=self.bucket_name)

            # 簡単なリスト操作
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)

            return True
        except Exception as e:
            logging.error(f"R2 connection test failed: {e}")
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cloudflare R2 Image Uploader")
    parser.add_argument(
        "command",
        choices=["upload", "list", "cleanup", "stats", "test"],
        help="Command to execute",
    )
    parser.add_argument("--image", help="Image file path (for upload)")
    parser.add_argument(
        "--config",
        default=str(project_root / "config" / "config.json"),
        help="Config file path",
    )
    parser.add_argument("--description", default="", help="Image description")
    parser.add_argument(
        "--days", type=int, default=7, help="Max age for cleanup (days)"
    )

    args = parser.parse_args()

    try:
        uploader = R2Uploader(args.config)

        if args.command == "test":
            if uploader.test_connection():
                print("✅ R2接続テスト成功")
            else:
                print("❌ R2接続テスト失敗")

        elif args.command == "upload":
            if not args.image:
                print("Error: --image required for upload")
                exit(1)
            url = uploader.upload_image(args.image, args.description)
            print(f"Upload successful: {url}")

        elif args.command == "list":
            images = uploader.list_images()
            print(f"Found {len(images)} images:")
            for img in images[:10]:  # 最初の10個を表示
                print(f"  {img['key']} ({img['size']} bytes)")
                print(f"    URL: {img['url']}")

        elif args.command == "cleanup":
            count = uploader.cleanup_old_images(args.days)
            print(f"Cleaned up {count} old images")

        elif args.command == "stats":
            stats = uploader.get_bucket_stats()
            print("R2 Bucket Statistics:")
            print(f"  Images: {stats.get('total_images', 0)}")
            print(f"  Total Size: {stats.get('total_size_mb', 0):.2f} MB")
            print(f"  Bucket: {stats.get('bucket_name', 'N/A')}")
            print(f"  Account: {stats.get('account_id', 'N/A')}")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
