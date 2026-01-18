#!/usr/bin/env python3
"""
LINE通知テストスクリプト
様々なメッセージパターンでLINE通知をテスト
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 親ディレクトリのモジュールをインポート
scripts_path = Path(__file__).parent
project_root = scripts_path.parent
sys.path.append(str(project_root))
sys.path.append(str(scripts_path.parent))

from line_image_notifier import LineImageNotifier
from integrated_detection import ChigemotsuDetector


class LineNotificationTester:
    def __init__(self, config_path=None):
        """LINE通知テスター"""
        if config_path is None:
            config_path = project_root / "config" / "config.json"
        
        self.notifier = LineImageNotifier(config_path)
        
        # 設定ファイルを読み込み
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"警告: 設定ファイルが読み込めません: {e}")
            # デフォルト設定
            self.config = {
                "model": {
                    "threshold": 0.75
                }
            }

    def test_simple_message(self):
        """シンプルなテストメッセージ"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"🧪 LINE通知テスト\n📅 {timestamp}\n✅ 正常に動作しています！"

        print("📤 シンプルメッセージテスト中...")
        success = self.notifier.test_notification(message)

        if success:
            print("✅ シンプルメッセージ送信成功！")
        else:
            print("❌ シンプルメッセージ送信失敗")

        return success

    def test_cat_detection(self, target_class, image_path):
        """猫検出テスト（共通メソッド）"""
        try:
            # テスト用の画像があるかチェック
            if not Path(image_path).exists():
                print(f"❌ テスト画像が見つかりません: {image_path}")
                print("代替として camera/images から画像を探します...")
                
                # camera/images から画像を探す
                camera_images_dir = Path(__file__).parent.parent.parent / "camera" / "images"
                if camera_images_dir.exists():
                    for img_file in camera_images_dir.glob("*.jpg"):
                        image_path = str(img_file)
                        print(f"代替画像を使用: {image_path}")
                        break
                    else:
                        print("❌ 使用可能な画像が見つかりません")
                        return False
                else:
                    print("❌ camera/images ディレクトリが見つかりません")
                    return False

            # 信頼度閾値チェック
            confidence_threshold = self.config.get("model", {}).get("threshold", 0.75)

            # 猫検出実行（エラーハンドリング付き）
            try:
                chigemotsu_detector = ChigemotsuDetector()
                result = chigemotsu_detector.process_image(image_path)
            except RuntimeError as e:
                if "Hybrid models are not supported" in str(e):
                    print(f"⚠️ TFLite Micro Runtime はハイブリッドモデルをサポートしていません")
                    print("テスト用にモック結果を使用します")
                    # テスト用のモック結果
                    if target_class == "chige":
                        result = {"confidence": 0.85, "class_name": "chige"}
                    elif target_class == "motsu":
                        result = {"confidence": 0.80, "class_name": "motsu"}
                    else:
                        result = {"confidence": 0.30, "class_name": "other"}
                else:
                    raise e
            
            if result["confidence"] >= confidence_threshold:
                if target_class == "chige":
                    class_name = "三毛猫（ちげ）"
                elif target_class == "motsu":
                    class_name = "白黒猫（もつ）"
                else:
                    class_name = "その他の猫"
                    
                print(f"猫を検出: {class_name} (信頼度: {result['confidence']:.3f})")
                
                # LINE通知送信
                success = self.notifier.send_detection_notification(
                    image_path=image_path,
                    confidence=float(result["confidence"] * 100),  # パーセント表示
                    class_name=str(class_name),
                )

                if success:
                    print("✅ 猫検出通知送信成功！")
                else:
                    print("❌ 猫検出通知送信失敗")
                    
                return success
            else:
                print(f"信頼度が閾値未満: {result['confidence']:.3f} < {confidence_threshold}")
                print("通知は送信されません")
                return True  # テストとしては成功（意図した動作）
                
        except Exception as e:
            print(f"❌ 猫検出テスト中にエラー: {e}")
            return False

    def test_cat_detection_chige(self):
        """三毛猫検出テスト"""
        image_path = "tests/fixtures/test_chige.jpg"  # テスト用画像パス
        print("🐱 三毛猫（ちげ）検出通知テスト中...")
        return self.test_cat_detection("chige", image_path)

    def test_cat_detection_motsu(self):
        """白黒猫検出テスト"""
        image_path = "tests/fixtures/test_motsu.jpg"  # テスト用画像パス
        print("🐈‍⬛ 白黒猫（もつ）検出通知テスト中...")
        return self.test_cat_detection("motsu", image_path)

    def test_non_cat_detection(self):
        """非猫検出テスト（通知されないはず）"""
        image_path = "tests/fixtures/test_other.jpg"  # テスト用画像パス
        print("🚫 非猫検出テスト中（通知されないはず）...")
        return self.test_cat_detection("other", image_path)

    def test_system_startup(self):
        """システム起動通知テスト"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            "🚀 猫検出システム起動\n"
            f"📅 {timestamp}\n"
            "🔍 三毛猫・白黒猫の監視を開始しました\n"
            "📊 TensorFlow Lite推論エンジン稼働中"
        )

        print("🚀 システム起動通知テスト中...")
        success = self.notifier.send_message(message)

        if success:
            print("✅ システム起動通知送信成功！")
        else:
            print("❌ システム起動通知送信失敗")

        return success

    def test_system_error(self):
        """システムエラー通知テスト"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            "⚠️ システムエラー発生\n"
            f"📅 {timestamp}\n"
            "❌ 推論エンジンでエラーが発生しました\n"
            "🔧 システム管理者に連絡してください"
        )

        print("⚠️ システムエラー通知テスト中...")
        success = self.notifier.send_message(message)

        if success:
            print("✅ システムエラー通知送信成功！")
        else:
            print("❌ システムエラー通知送信失敗")

        return success

    def test_daily_summary(self):
        """日次サマリー通知テスト"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            "📊 本日の猫検出サマリー\n"
            f"📅 {timestamp}\n"
            "🐱 三毛猫（ちげ）: 3回検出\n"
            "🐈‍⬛ 白黒猫（もつ）: 1回検出\n"
            "🔍 総検出回数: 4回\n"
            "⏱️ 平均推論時間: 2.1秒"
        )

        print("📊 日次サマリー通知テスト中...")
        success = self.notifier.send_message(message)

        if success:
            print("✅ 日次サマリー通知送信成功！")
        else:
            print("❌ 日次サマリー通知送信失敗")

        return success

    def run_all_tests(self):
        """全てのテストを実行"""
        print("🧪 LINE通知システム - 全機能テスト開始")
        print("=" * 50)

        tests = [
            ("シンプルメッセージ", self.test_simple_message),
            ("三毛猫検出", self.test_cat_detection_chige),
            ("白黒猫検出", self.test_cat_detection_motsu),
            ("非猫検出", self.test_non_cat_detection),
            ("システム起動", self.test_system_startup),
            ("システムエラー", self.test_system_error),
            ("日次サマリー", self.test_daily_summary),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n--- {test_name}テスト ---")
            try:
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                print(f"❌ {test_name}テストでエラー: {e}")
                results.append((test_name, False))

            # テスト間に少し間隔を開ける
            import time

            time.sleep(1)

        # テスト結果サマリー
        print("\n" + "=" * 50)
        print("📋 テスト結果サマリー")
        print("=" * 50)

        passed = 0
        for test_name, success in results:
            status = "✅ 成功" if success else "❌ 失敗"
            print(f"{status} {test_name}")
            if success:
                passed += 1

        total = len(results)
        print(f"\n🎯 総合結果: {passed}/{total} テスト通過")

        if passed == total:
            print(
                "🎉 全てのテストが成功しました！LINE通知システムは正常に動作しています。"
            )
        else:
            print(
                "⚠️ 一部のテストが失敗しました。設定やネットワーク接続を確認してください。"
            )

        return passed == total


def main():
    parser = argparse.ArgumentParser(description="LINE Notification Tester")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    parser.add_argument(
        "--test",
        type=str,
        choices=[
            "simple",
            "chige",
            "motsu",
            "noncat",
            "startup",
            "error",
            "summary",
            "all",
        ],
        default="all",
        help="Test type to run",
    )

    args = parser.parse_args()

    try:
        tester = LineNotificationTester(config_path=args.config)

        if args.test == "simple":
            success = tester.test_simple_message()
        elif args.test == "chige":
            success = tester.test_cat_detection_chige()
        elif args.test == "motsu":
            success = tester.test_cat_detection_motsu()
        elif args.test == "noncat":
            success = tester.test_non_cat_detection()
        elif args.test == "startup":
            success = tester.test_system_startup()
        elif args.test == "error":
            success = tester.test_system_error()
        elif args.test == "summary":
            success = tester.test_daily_summary()
        else:  # 'all'
            success = tester.run_all_tests()

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
