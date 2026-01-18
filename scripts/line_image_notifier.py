#!/usr/bin/env python3
"""
LINE画像通知機能の統合実装
R2Uploaderと組み合わせて画像付きLINE通知を送信
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# パッケージリソースアクセス用
try:
    from importlib import resources
except ImportError:
    # Python 3.8以前の場合
    import importlib_resources as resources

# カメラモジュールとR2アップローダーのパスを追加
script_dir = Path(__file__).parent
project_root = script_dir.parent
fixtures_path = project_root / "tests" / "fixtures"
sys.path.append(str(fixtures_path))

from r2_uploader import R2Uploader

try:
    import requests
except ImportError:
    print("Warning: requests not installed. Please install with: pip install requests")
    sys.exit(1)


class LineImageNotifier:
    """LINE画像通知クラス"""

    def __init__(self, config_path: Optional[str] = project_root / "config" / "config.json"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス（デフォルト: config/config.json）
        """
        self.config = self._load_config(config_path)
        self.r2_uploader = R2Uploader(config_path)

        # ログ設定
        self._setup_logging()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """設定ファイルの読み込み"""
        if config_path is None:
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
            # ファイルパスから読み込み
            config_path = Path(config_path)
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
            except json.JSONDecodeError as e:
                raise ValueError(f"設定ファイルの形式が正しくありません: {e}")

        # LINE認証情報を別ファイルから読み込み
        line_config = config.get("line", {})
        credentials_file = line_config.get(
            "credentials_file", "./config/line_credentials.json"
        )

        if config_path is None:
            # パッケージリソースから認証情報を読み込み
            try:
                line_credentials_text = (
                    resources.files("config")
                    .joinpath("line_credentials.json")
                    .read_text(encoding="utf-8")
                )
                line_credentials = json.loads(line_credentials_text)
                config["line"].update(line_credentials)
            except (FileNotFoundError, ModuleNotFoundError):
                raise FileNotFoundError(
                    "LINE認証ファイルがパッケージに含まれていません"
                )
        else:
            # 相対パスの場合は絶対パスに変換
            config_path = Path(config_path)
            if not os.path.isabs(credentials_file):
                # 相対パスを config.json の位置を基準として解決
                credentials_path = config_path.parent / credentials_file.lstrip("./")
            else:
                credentials_path = Path(credentials_file)

            # LINE認証情報を読み込み
            try:
                with open(credentials_path, "r", encoding="utf-8") as f:
                    line_credentials = json.load(f)
                    # 認証情報をメイン設定に統合
                    config["line"].update(line_credentials)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"LINE認証ファイルが見つかりません: {credentials_path}"
                )

        return config

    def _setup_logging(self):
        """ログ設定"""
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,  # INFOレベルに戻す
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "line_image_notifier.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)  # INFOレベルに戻す

    def send_image_notification(
        self,
        image_path: str,
        message: str = "",
        user_id: Optional[str] = None,
        cleanup_after_days: int = 7,
    ) -> bool:
        """
        画像付きLINE通知を送信

        Args:
            image_path: 送信する画像のパス
            message: 付加するメッセージ（オプション）
            user_id: 送信先ユーザーID（指定しない場合は設定ファイルから取得）
            cleanup_after_days: 古い画像を削除する日数

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            # 画像をR2にアップロード
            self.logger.info(f"画像をアップロード開始: {image_path}")
            image_url = self.r2_uploader.upload_image(image_path)

            if not image_url:
                self.logger.error("画像のアップロードに失敗しました")
                return False

            self.logger.info(f"画像アップロード完了: {image_url}")

            # LINE通知を送信
            success = self._send_line_message(image_url, message, user_id)

            if success:
                self.logger.info("LINE画像通知の送信が完了しました")

                # 古い画像を整理
                try:
                    cleaned = self.r2_uploader.cleanup_old_images(
                        max_age_days=cleanup_after_days
                    )
                    if cleaned:
                        self.logger.info(f"{len(cleaned)}個の古い画像を削除しました")
                except Exception as e:
                    self.logger.warning(f"古い画像の削除中にエラー: {e}")

            return success

        except Exception as e:
            self.logger.error(f"画像通知の送信中にエラーが発生: {e}")
            return False

    def _send_line_message(
        self, image_url: str, message: str = "", user_id: Optional[str] = None
    ) -> bool:
        """
        LINE APIを使用してメッセージを送信

        Args:
            image_url: 画像のURL
            message: 付加するメッセージ
            user_id: 送信先ユーザーID

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            # ユーザーIDの取得
            if user_id is None:
                user_id = self.config["line"]["line_user_id"]

            # アクセストークンの取得
            access_token = self.config["line"]["line_access_token"]

            # メッセージの構築
            messages = []

            # テキストメッセージがある場合は追加
            if message:
                messages.append({"type": "text", "text": message})

            # 画像メッセージを追加
            messages.append(
                {
                    "type": "image",
                    "originalContentUrl": image_url,
                    "previewImageUrl": image_url,
                }
            )

            # LINE API呼び出し
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {"to": user_id, "messages": messages}

            # タイムアウトとリトライの設定
            timeout = self.config.get("line", {}).get("timeout_seconds", 15)
            retry_count = self.config.get("line", {}).get("retry_count", 3)

            # APIリクエスト実行
            for attempt in range(retry_count):
                try:
                    response = requests.post(
                        self.config["line"]["api_url"],
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )

                    if response.status_code == 200:
                        self.logger.info("LINE通知の送信に成功しました")
                        return True
                    else:
                        self.logger.warning(
                            f"LINE API応答エラー (試行 {attempt + 1}/{retry_count}): "
                            f"ステータス={response.status_code}, 応答={response.text}"
                        )

                except requests.RequestException as e:
                    self.logger.warning(
                        f"LINE API接続エラー (試行 {attempt + 1}/{retry_count}): {e}"
                    )

                if attempt < retry_count - 1:
                    import time

                    time.sleep(2**attempt)  # 指数バックオフ

            self.logger.error("LINE通知の送信に失敗しました（全試行完了）")
            return False

        except Exception as e:
            self.logger.error(f"LINE通知送信中にエラーが発生: {e}")
            return False

    def send_detection_notification(
        self,
        image_path: str,
        confidence: float,
        class_name: str = "物体",
        cleanup_after_days: int = 7,
    ) -> bool:
        """
        検出結果付き通知を送信

        Args:
            image_path: 検出された物体の画像パス
            confidence: 検出信頼度
            class_name: 検出された物体のクラス名
            cleanup_after_days: 古い画像を削除する日数

        Returns:
            bool: 送信成功時True、失敗時False
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = (
            f"🔍 {class_name}を検出しました\n"
            f"信頼度: {confidence:.1f}%\n"
            f"検出時刻: {timestamp}"
        )

        return self.send_image_notification(
            image_path=image_path,
            message=message,
            cleanup_after_days=cleanup_after_days,
        )

    def test_notification(self, message: str = "📸 LINE画像通知のテストです") -> bool:
        """
        テスト用通知を送信

        Args:
            message: 送信するテストメッセージ（デフォルト: "📸 LINE画像通知のテストです"）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        # テスト用の画像を探す
        test_image_path = None

        if fixtures_path.exists():
            for image_file in fixtures_path.glob("*.jpg"):
                test_image_path = str(image_file)
                break

        if not test_image_path:
            self.logger.error("テスト用の画像が見つかりません")
            return False

        return self.send_image_notification(
            image_path=test_image_path,
            message=message,
            cleanup_after_days=1,  # テスト画像は早めに削除
        )

    def send_message_with_image(
        self,
        image_url: str,
        message: str = "",
        user_id: Optional[str] = None,
    ) -> bool:
        """
        画像URLを使用してLINE通知を送信（R2アップロードなし）

        Args:
            image_url: 送信する画像のURL
            message: 付加するメッセージ（オプション）
            user_id: 送信先ユーザーID（指定しない場合は設定ファイルから取得）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            # LINE通知を送信
            success = self._send_line_message(image_url, message, user_id)

            if success:
                self.logger.info("LINE画像通知の送信が完了しました")

            return success

        except Exception as e:
            self.logger.error(f"画像通知の送信中にエラーが発生: {e}")
            return False

    def send_message(
        self,
        message: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        テキストメッセージのみを送信

        Args:
            message: 送信するメッセージ
            user_id: 送信先ユーザーID（指定しない場合は設定ファイルから取得）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            # ユーザーIDの取得
            if user_id is None:
                user_id = self.config["line"]["line_user_id"]

            # アクセストークンの取得
            access_token = self.config["line"]["line_access_token"]

            # メッセージの構築
            messages = [{"type": "text", "text": message}]

            # LINE API呼び出し
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {"to": user_id, "messages": messages}

            # タイムアウトとリトライの設定
            timeout = self.config.get("line", {}).get("timeout_seconds", 15)
            retry_count = self.config.get("line", {}).get("retry_count", 3)

            # APIリクエスト実行
            for attempt in range(retry_count):
                try:
                    response = requests.post(
                        self.config["line"]["api_url"],
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )

                    if response.status_code == 200:
                        self.logger.info("LINE通知の送信に成功しました")
                        return True
                    else:
                        self.logger.warning(
                            f"LINE API応答エラー (試行 {attempt + 1}/{retry_count}): "
                            f"ステータス={response.status_code}, 応答={response.text}"
                        )

                except requests.RequestException as e:
                    self.logger.warning(
                        f"LINE API接続エラー (試行 {attempt + 1}/{retry_count}): {e}"
                    )

                if attempt < retry_count - 1:
                    import time

                    time.sleep(2**attempt)  # 指数バックオフ

            self.logger.error("LINE通知の送信に失敗しました（全試行完了）")
            return False

        except Exception as e:
            self.logger.error(f"LINE通知送信中にエラーが発生: {e}")
            return False

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        ストレージ使用状況を取得

        Returns:
            Dict: ストレージ統計情報
        """
        try:
            return self.r2_uploader.get_bucket_stats()
        except Exception as e:
            self.logger.error(f"ストレージ統計の取得に失敗: {e}")
            return {}

    def send_message(self, message: str, user_id: Optional[str] = None) -> bool:
        """
        テキストメッセージのみを送信

        Args:
            message: 送信するメッセージ
            user_id: 送信先ユーザーID（指定しない場合は設定ファイルから取得）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            # ユーザーIDの取得
            if user_id is None:
                user_id = self.config["line"]["line_user_id"]

            # アクセストークンの取得
            access_token = self.config["line"]["line_access_token"]

            # メッセージの構築
            messages = [{"type": "text", "text": message}]

            # LINE API呼び出し
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {"to": user_id, "messages": messages}

            # タイムアウトとリトライの設定
            timeout = self.config.get("line", {}).get("timeout_seconds", 15)
            retry_count = self.config.get("line", {}).get("retry_count", 3)

            # APIリクエスト実行
            for attempt in range(retry_count):
                try:
                    response = requests.post(
                        self.config["line"]["api_url"],
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )

                    if response.status_code == 200:
                        self.logger.info("LINE通知の送信に成功しました")
                        return True
                    else:
                        self.logger.warning(
                            f"LINE API応答エラー (試行 {attempt + 1}/{retry_count}): "
                            f"ステータス={response.status_code}, 応答={response.text}"
                        )

                except requests.RequestException as e:
                    self.logger.warning(
                        f"LINE API接続エラー (試行 {attempt + 1}/{retry_count}): {e}"
                    )

                if attempt < retry_count - 1:
                    import time

                    time.sleep(2**attempt)  # 指数バックオフ

            self.logger.error("LINE通知の送信に失敗しました（全試行完了）")
            return False

        except Exception as e:
            self.logger.error(f"LINE通知送信中にエラーが発生: {e}")
            return False

    def send_message_with_image(self, message: str, image_url: str, user_id: Optional[str] = None) -> bool:
        """
        テキストメッセージと画像URLを送信

        Args:
            message: 送信するメッセージ
            image_url: 画像のURL
            user_id: 送信先ユーザーID（指定しない場合は設定ファイルから取得）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        return self._send_line_message(image_url, message, user_id)


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="LINE画像通知送信")
    parser.add_argument("--image", "-i", help="送信する画像のパス")
    parser.add_argument("--message", "-m", default="", help="付加するメッセージ")
    parser.add_argument("--test", action="store_true", help="テスト通知を送信")
    parser.add_argument("--stats", action="store_true", help="ストレージ統計を表示")
    parser.add_argument("--config", "-c", help="設定ファイルのパス")

    args = parser.parse_args()

    try:
        # LineImageNotifierを初期化
        notifier = LineImageNotifier(config_path=args.config)

        if args.stats:
            # ストレージ統計を表示
            stats = notifier.get_storage_stats()
            if stats:
                print("\n=== ストレージ統計 ===")
                print(f"総ファイル数: {stats.get('total_files', 0)}")
                print(f"総サイズ: {stats.get('total_size_mb', 0):.2f} MB")
                print(f"最新ファイル: {stats.get('latest_file', 'N/A')}")
                print(f"最古ファイル: {stats.get('oldest_file', 'N/A')}")
            else:
                print("ストレージ統計の取得に失敗しました")

        elif args.test:
            # テスト通知を送信
            print("テスト通知を送信中...")
            success = notifier.test_notification()
            if success:
                print("✅ テスト通知の送信に成功しました")
            else:
                print("❌ テスト通知の送信に失敗しました")

        elif args.image:
            # 指定された画像で通知を送信
            if not os.path.exists(args.image):
                print(f"❌ 画像ファイルが見つかりません: {args.image}")
                sys.exit(1)

            print(f"画像通知を送信中: {args.image}")
            success = notifier.send_image_notification(
                image_path=args.image, message=args.message
            )

            if success:
                print("✅ 画像通知の送信に成功しました")
            else:
                print("❌ 画像通知の送信に失敗しました")
                sys.exit(1)
        else:
            parser.print_help()

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
