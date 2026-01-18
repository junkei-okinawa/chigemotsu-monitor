#!/usr/bin/env python3
"""
ちげもつ判別・LINE通知パイプライン
推論処理（integrated_detection.py）とLINE通知（line_image_notifier.py）を組み合わせた統合処理
motion連携用のエントリーポイント
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# プロジェクトパスを追加
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(script_dir))

try:
    from integrated_detection import ChigemotsuDetector
    from line_image_notifier import LineImageNotifier
    from db_manager import DetectionDBManager
except ImportError as e:
    print(f"❌ 必要なモジュールがインポートできません: {e}")
    print("scripts/ディレクトリに integrated_detection.py, line_image_notifier.py, db_manager.py があることを確認してください")
    sys.exit(1)


class ChigemotsuPipeline:
    """ちげもつ判別・LINE通知パイプライン"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス（デフォルト: config/config.json）
        """
        if config_path is None:
            config_path = project_root / "config" / "config.json"

        self.config_path = Path(config_path)
        
        # 設定ファイルの存在確認
        if not self.config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")

        # 設定ファイルを読み込み
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"設定ファイルの読み込みに失敗: {e}")

        # ログ設定
        self._setup_logging()

        # 各コンポーネントを初期化
        try:
            self.detector = ChigemotsuDetector(config_path=config_path)
            self.notifier = LineImageNotifier(config_path=config_path)
            self.db_manager = DetectionDBManager(db_path=str(project_root / "logs" / "detection.db"))
        except Exception as e:
            self.logger.error(f"コンポーネントの初期化に失敗: {e}")
            raise

        # 統計情報
        self.pipeline_stats = {
            "total_processed": 0,
            "successful_detections": 0,
            "notification_sent": 0,
            "start_time": datetime.now(),
        }

        self.logger.info("ちげもつパイプラインが初期化されました")

    def _setup_logging(self):
        """ログ設定"""
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "chigemotsu_pipeline.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def process_motion_image(self, image_path: str) -> bool:
        """
        motion連携用の統合処理
        推論 → 信頼度チェック → LINE通知の一連の流れを実行

        Args:
            image_path: motionで撮影された画像のパス

        Returns:
            bool: 処理成功時True、失敗時False
        """
        try:
            self.logger.info(f"パイプライン処理を開始: {image_path}")
            start_time = time.time()

            # 統計情報を更新
            self.pipeline_stats["total_processed"] += 1

            # Step 1: 推論実行
            self.logger.info("Step 1: ちげもつ判別を実行中...")
            detection_result = self.detector.process_image(image_path)
            
            if not detection_result:
                self.logger.error("推論処理に失敗しました")
                return False

            self.pipeline_stats["successful_detections"] += 1
            
            # Step 2: 信頼度チェック
            confidence_threshold = self.config.get("model", {}).get("threshold", 0.75)
            confidence = detection_result["confidence"]
            class_name = detection_result["class_name"]
            
            self.logger.info(f"推論結果: {class_name} (信頼度: {confidence:.3f})")

            is_notified = False

            if confidence < confidence_threshold:
                self.logger.info(f"信頼度が閾値未満のため通知をスキップ: {confidence:.3f} < {confidence_threshold}")
                # 通知対象外でもDBには記録する（通知フラグFalse）
                self.db_manager.add_detection(class_name, confidence, image_path, is_notified)
                return True  # 処理としては成功

            # Step 3: LINE通知設定の確認
            notification_enabled = self.config.get("line", {}).get("notification_enabled", True)
            if not notification_enabled:
                self.logger.info("LINE通知が無効になっています")
                self.db_manager.add_detection(class_name, confidence, image_path, is_notified)
                return True

            # Step 4: 通知抑制チェック（直近5分以内に同一個体の通知があるか）
            if self.db_manager.get_recent_notification(class_name, minutes=5):
                self.logger.info(f"直近5分以内に {class_name} の通知済みのため、通知をスキップします")
                self.db_manager.add_detection(class_name, confidence, image_path, is_notified)
                return True

            # Step 5: LINE通知送信
            self.logger.info("Step 2: LINE通知を送信中...")

            if class_name in ["chige", "motsu"]:
                # 信頼度をパーセント表示に変換
                confidence_percent = confidence * 100
                
                # クラス名を日本語に変換
                if class_name == "chige":
                    japanese_class_name = "三毛猫（ちげ）"
                elif class_name == "motsu":
                    japanese_class_name = "白黒猫（もつ）"
                else:
                    japanese_class_name = class_name

                # LINE通知送信
                notification_success = self.notifier.send_detection_notification(
                    image_path=image_path,
                    confidence=confidence_percent,
                    class_name=japanese_class_name,
                    cleanup_after_days=self.config.get("motion", {}).get("cleanup_days", 2)
                )

                if notification_success:
                    self.pipeline_stats["notification_sent"] += 1
                    is_notified = True
                    self.logger.info("LINE通知の送信に成功しました")
                else:
                    self.logger.error("LINE通知の送信に失敗しました")
                    # 通知失敗でもパイプライン全体は成功とする
                
                # DBに保存（通知成功時のみ is_notified=True）
                self.db_manager.add_detection(class_name, confidence, image_path, is_notified)

                # 処理時間をログ出力
                total_time = time.time() - start_time
                self.logger.info(f"パイプライン処理完了 (総処理時間: {total_time:.3f}秒)")

                return True
            else:
                self.logger.info(f"検出されたクラスは通知対象外: {class_name}")
                self.db_manager.add_detection(class_name, confidence, image_path, is_notified)
                return True

        except Exception as e:
            self.logger.error(f"パイプライン処理中にエラー: {e}")
            return False

    def send_system_notification(self, message_type: str, custom_message: str = None) -> bool:
        """
        システム通知を送信

        Args:
            message_type: 通知タイプ（startup, error, summary）
            custom_message: カスタムメッセージ（指定しない場合は自動生成）

        Returns:
            bool: 送信成功時True、失敗時False
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if custom_message:
                message = custom_message
            elif message_type == "startup":
                message = (
                    "🚀 ちげもつ検出システム起動\n"
                    f"📅 {timestamp}\n"
                    "🔍 三毛猫・白黒猫の監視を開始しました\n"
                    "📊 TensorFlow Lite推論エンジン稼働中"
                )
            elif message_type == "error":
                message = (
                    "⚠️ ちげもつ検出システムエラー\n"
                    f"📅 {timestamp}\n"
                    "❌ 推論エンジンでエラーが発生しました\n"
                    "🔧 システム管理者に連絡してください"
                )
            elif message_type == "summary":
                stats = self.get_pipeline_stats()
                message = (
                    "📊 ちげもつ検出システム - 日次サマリー\n"
                    f"📅 {timestamp}\n"
                    f"🔍 総処理回数: {stats['total_processed']}回\n"
                    f"✅ 成功検出: {stats['successful_detections']}回\n"
                    f"📱 通知送信: {stats['notification_sent']}回\n"
                    f"⏱️ 稼働時間: {stats['runtime_hours']:.1f}時間"
                )
            else:
                self.logger.error(f"未知の通知タイプ: {message_type}")
                return False

            # システム通知送信
            return self.notifier.send_message(message)

        except Exception as e:
            self.logger.error(f"システム通知送信中にエラー: {e}")
            return False

    def test_pipeline(self) -> bool:
        """
        パイプライン全体のテスト

        Returns:
            bool: テスト成功時True、失敗時False
        """
        try:
            # テスト用画像を探す
            test_image_path = None

            # tests/fixtures から探す
            fixtures_dir = project_root / "tests" / "fixtures"
            if fixtures_dir.exists():
                for image_file in fixtures_dir.glob("*.jpg"):
                    test_image_path = str(image_file)
                    break

            # camera/images から探す（フォールバック）
            if not test_image_path:
                camera_images_dir = project_root.parent / "camera" / "images"
                if camera_images_dir.exists():
                    for image_file in camera_images_dir.glob("*.jpg"):
                        test_image_path = str(image_file)
                        break

            if not test_image_path:
                self.logger.error("テスト用画像が見つかりません")
                return False

            print(f"テスト画像でパイプライン実行: {test_image_path}")
            
            # パイプライン実行
            success = self.process_motion_image(test_image_path)
            
            if success:
                print("✅ パイプラインテストが完了しました")
            else:
                print("❌ パイプラインテストに失敗しました")

            return success

        except Exception as e:
            self.logger.error(f"パイプラインテスト中にエラー: {e}")
            return False

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """パイプライン統計情報を取得"""
        runtime = datetime.now() - self.pipeline_stats["start_time"]

        return {
            "runtime_hours": runtime.total_seconds() / 3600,
            "total_processed": self.pipeline_stats["total_processed"],
            "successful_detections": self.pipeline_stats["successful_detections"],
            "notification_sent": self.pipeline_stats["notification_sent"],
            "start_time": self.pipeline_stats["start_time"].isoformat(),
        }


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="ちげもつ判別・LINE通知パイプライン")
    parser.add_argument(
        "image_path", nargs="?", help="処理する画像のパス（motionから渡される）"
    )
    parser.add_argument("--test", action="store_true", help="パイプライン全体のテスト")
    parser.add_argument("--stats", action="store_true", help="パイプライン統計情報を表示")
    parser.add_argument(
        "--notify", 
        choices=["startup", "error", "summary"], 
        help="システム通知を送信"
    )
    parser.add_argument("--config", "-c", help="設定ファイルのパス")

    args = parser.parse_args()

    try:
        # パイプラインを初期化
        pipeline = ChigemotsuPipeline(config_path=args.config)

        if args.stats:
            # 統計情報を表示
            stats = pipeline.get_pipeline_stats()
            print("\n=== ちげもつパイプライン統計 ===")
            print(f"稼働時間: {stats['runtime_hours']:.2f} 時間")
            print(f"総処理回数: {stats['total_processed']}")
            print(f"成功検出: {stats['successful_detections']}")
            print(f"通知送信: {stats['notification_sent']}")
            print(f"開始時刻: {stats['start_time']}")

        elif args.test:
            # パイプライン全体のテスト
            success = pipeline.test_pipeline()
            sys.exit(0 if success else 1)

        elif args.notify:
            # システム通知送信
            print(f"システム通知を送信中: {args.notify}")
            success = pipeline.send_system_notification(args.notify)
            if success:
                print("✅ システム通知の送信に成功しました")
            else:
                print("❌ システム通知の送信に失敗しました")
                sys.exit(1)

        elif args.image_path:
            # motionから渡された画像を処理
            success = pipeline.process_motion_image(args.image_path)
            if success:
                print("✅ パイプライン処理が完了しました")
            else:
                print("❌ パイプライン処理に失敗しました")
                sys.exit(1)
        else:
            parser.print_help()
            print("\n使用例:")
            print("# motionからの呼び出し")
            print("python chigemotsu_pipeline.py /path/to/image.jpg")
            print("\n# パイプラインテスト")
            print("python chigemotsu_pipeline.py --test")
            print("\n# 統計表示")
            print("python chigemotsu_pipeline.py --stats")
            print("\n# システム通知")
            print("python chigemotsu_pipeline.py --notify startup")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
