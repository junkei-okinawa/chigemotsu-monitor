#!/usr/bin/env python3
"""
chigemotsu判別＋LINE画像通知スクリプト
motionからの画像パスを受け取り、TFLite推論してLINE通知
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# パッケージリソースアクセス用
try:
    from importlib import resources
except ImportError:
    # Python 3.8以前の場合
    import importlib_resources as resources

# プロジェクトパスを追加
script_dir = Path(__file__).parent
project_root = script_dir.parent

try:
    import numpy as np
    from PIL import Image

    try:
        import tflite_micro_runtime.interpreter as tflite
    except ImportError:
        # 開発環境ではtensorflowのTFLiteを使用
        import tensorflow as tf

        tflite = tf.lite

except ImportError as e:
    print(f"❌ 必要なライブラリがインストールされていません: {e}")
    print("Raspberry Pi: pip3 install pillow numpy tflite-runtime")
    print("開発環境: uv pip install -e '.[dev]'")
    sys.exit(1)


class ChigemotsuDetector:
    """ちげもつ判別システム（motion連携版）"""

    def __init__(self, config_path: Optional[str] = project_root / "config" / "config.json"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス（デフォルト: config/config.json）
        """
        if config_path is None:
            # パッケージリソースから設定ファイルを読み込み
            try:
                config_text = (
                    resources.files("config")
                    .joinpath("config.json")
                    .read_text(encoding="utf-8")
                )
                self.config = json.loads(config_text)
                self.config_path = None  # パッケージリソースを使用
            except (FileNotFoundError, ModuleNotFoundError):
                # フォールバック: 従来の方法
                self.config_path = script_dir.parent / "config" / "config.json"
                if not self.config_path.exists():
                    raise FileNotFoundError(
                        f"設定ファイルが見つかりません: {self.config_path}"
                    )
                self.config = self._load_config()
        else:
            # 相対パスの場合は絶対パスに変換
            config_path = Path(config_path)
            if not config_path.is_absolute():
                self.config_path = Path.cwd() / config_path
            else:
                self.config_path = config_path

            # 設定ファイルの存在確認
            if not self.config_path.exists():
                print(f"❌ 設定ファイルが見つかりません: {self.config_path}")
                raise FileNotFoundError(
                    f"設定ファイルが見つかりません: {self.config_path}"
                )

            self.config = self._load_config()

        # ログ設定
        self._setup_logging()

        # モデル読み込み
        self.class_names = self.config.get("model", {}).get(
            "class_names", ["chige", "motsu", "other"]
        )
        self._load_model()

        # 統計情報
        self.detection_stats = {
            "total_detections": 0,
            "chige_count": 0,
            "motsu_count": 0,
            "start_time": datetime.now(),
        }

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルの読み込み"""
        if self.config_path is None:
            # 既にパッケージリソースから読み込み済み
            return self.config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"設定ファイルの形式が正しくありません: {e}")

    def _setup_logging(self):
        """ログ設定"""
        log_dir = script_dir.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "chigemotsu_detection.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def _load_model(self):
        """TFLiteモデルの読み込み"""
        try:
            # モデルパスを新しい設定形式から取得
            model_path = self.config.get("model", {}).get(
                "model_path", "./models/mobilenet_v2_tensorflow.tflite"
            )

            # 相対パスの場合は絶対パスに変換
            if not os.path.isabs(model_path):
                model_path = project_root / model_path.lstrip("./")
            else:
                model_path = Path(model_path)

            if not model_path.exists():
                raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")

            # TFLiteインタープリターを初期化
            try:
                self.interpreter = tflite.Interpreter(model_path=str(model_path))
                self.interpreter.allocate_tensors()
            except Exception as tflite_error:
                # tflite_micro_runtime特有のエラーをチェック
                if "Hybrid models are not supported" in str(tflite_error):
                    raise RuntimeError(
                        f"TFLite Micro Runtime はハイブリッドモデルをサポートしていません。\n"
                        f"完全に量子化されたモデルを使用するか、標準のtflite-runtimeに変更してください。\n"
                        f"モデル: {model_path}\n"
                        f"詳細: {tflite_error}"
                    )
                else:
                    raise RuntimeError(f"TFLiteモデルの初期化に失敗: {tflite_error}")

            # 入力と出力の詳細を取得
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

            # モデル詳細をログ出力
            input_dtype = self.input_details[0]["dtype"]
            output_dtype = self.output_details[0]["dtype"]
            input_shape = self.input_details[0]["shape"]
            output_shape = self.output_details[0]["shape"]
            
            self.logger.info(f"TFLiteモデルを読み込みました: {model_path}")
            self.logger.info(f"入力: {input_shape}, 型: {input_dtype}")
            self.logger.info(f"出力: {output_shape}, 型: {output_dtype}")
            
            # 量子化パラメータの確認
            if input_dtype in [np.int8, np.uint8]:
                input_scale = self.input_details[0]["quantization_parameters"]["scales"][0]
                input_zero_point = self.input_details[0]["quantization_parameters"]["zero_points"][0]
                self.logger.info(f"入力量子化: scale={input_scale}, zero_point={input_zero_point}")
                
            if output_dtype in [np.int8, np.uint8]:
                output_scale = self.output_details[0]["quantization_parameters"]["scales"][0]
                output_zero_point = self.output_details[0]["quantization_parameters"]["zero_points"][0]
                self.logger.info(f"出力量子化: scale={output_scale}, zero_point={output_zero_point}")

        except Exception as e:
            self.logger.error(f"モデルの読み込みに失敗: {e}")
            raise

    def preprocess_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        画像の前処理

        Args:
            image_path: 画像ファイルのパス

        Returns:
            np.ndarray: 前処理済み画像、失敗時はNone
        """
        try:
            # PILで画像を読み込み
            image = Image.open(image_path)

            # RGBに変換（必要に応じて）
            if image.mode != "RGB":
                image = image.convert("RGB")

            # モデルの入力サイズに合わせてリサイズ
            input_shape = self.input_details[0]["shape"]
            height, width = input_shape[1], input_shape[2]
            image = image.resize((width, height), Image.Resampling.LANCZOS)

            # numpy配列に変換
            image_array = np.array(image, dtype=np.float32)

            # モデルの入力型に応じて前処理を分岐
            input_dtype = self.input_details[0]["dtype"]
            
            # Float32モデルの場合（推奨）
            if input_dtype == np.float32:
                # 正規化（0-1）
                image_array = image_array / 255.0
                self.logger.debug("Float32入力（標準）")
                
            elif input_dtype == np.int8:
                # INT8量子化モデルの場合（レガシー）
                # 正規化（0-1）してから量子化パラメータを適用
                image_array = image_array / 255.0
                
                # 量子化パラメータを取得
                input_scale = self.input_details[0]["quantization_parameters"]["scales"][0]
                input_zero_point = self.input_details[0]["quantization_parameters"]["zero_points"][0]
                
                # INT8に量子化
                image_array = image_array / input_scale + input_zero_point
                image_array = np.clip(image_array, -128, 127).astype(np.int8)
                
                self.logger.debug(f"INT8量子化: scale={input_scale}, zero_point={input_zero_point}")
                
            elif input_dtype == np.uint8:
                # UINT8量子化モデルの場合（レガシー）
                # 正規化（0-1）してから量子化パラメータを適用
                image_array = image_array / 255.0
                
                # 量子化パラメータを取得
                input_scale = self.input_details[0]["quantization_parameters"]["scales"][0]
                input_zero_point = self.input_details[0]["quantization_parameters"]["zero_points"][0]
                
                # UINT8に量子化
                image_array = image_array / input_scale + input_zero_point
                image_array = np.clip(image_array, 0, 255).astype(np.uint8)
                
                self.logger.debug(f"UINT8量子化: scale={input_scale}, zero_point={input_zero_point}")
                
            else:
                # その他のデータ型の場合
                image_array = image_array / 255.0
                self.logger.warning(f"未対応の入力型: {input_dtype}、Float32として処理")

            # バッチ次元を追加
            image_array = np.expand_dims(image_array, axis=0)

            return image_array

        except Exception as e:
            self.logger.error(f"画像前処理中にエラー: {e}")
            return None

    def predict(self, preprocessed_image: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        推論を実行

        Args:
            preprocessed_image: 前処理済み画像

        Returns:
            Dict: 推論結果、失敗時はNone
        """
        try:
            start_time = time.time()

            # 入力データを設定
            self.interpreter.set_tensor(
                self.input_details[0]["index"], preprocessed_image
            )

            # 推論実行
            self.interpreter.invoke()

            # 結果を取得
            raw_predictions = self.interpreter.get_tensor(self.output_details[0]["index"])

            # 出力の型に応じて後処理を分岐
            output_dtype = self.output_details[0]["dtype"]
            
            # Float32出力の場合（推奨）
            if output_dtype == np.float32:
                predictions = raw_predictions
                self.logger.debug("Float32出力（標準）")
                
            elif output_dtype == np.int8 or output_dtype == np.uint8:
                # 量子化出力の場合は逆量子化（レガシー）
                output_scale = self.output_details[0]["quantization_parameters"]["scales"][0]
                output_zero_point = self.output_details[0]["quantization_parameters"]["zero_points"][0]
                
                # 逆量子化してFloat32に変換
                predictions = (raw_predictions.astype(np.float32) - output_zero_point) * output_scale
                
                # ソフトマックスを適用（分類問題の場合）
                exp_predictions = np.exp(predictions - np.max(predictions, axis=1, keepdims=True))
                predictions = exp_predictions / np.sum(exp_predictions, axis=1, keepdims=True)
                
                self.logger.debug(f"量子化出力を逆量子化: scale={output_scale}, zero_point={output_zero_point}")
                
            else:
                # その他の型
                predictions = raw_predictions
                self.logger.warning(f"未対応の出力型: {output_dtype}、Float32として処理")

            inference_time = time.time() - start_time

            # 結果を解析
            predicted_class = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class])

            # クラス名の範囲チェック
            if predicted_class >= len(self.class_names):
                self.logger.warning(
                    f"予測されたクラス番号 {predicted_class} がクラス名リストの範囲外です。クラス数: {len(self.class_names)}"
                )
                class_name = "unknown"
            else:
                class_name = self.class_names[predicted_class]

            result = {
                "is_cat": True,  # 両クラス共に猫
                "class_name": class_name,
                "confidence": confidence,
                "inference_time": inference_time,
                "predictions": predictions[0].tolist(),
            }

            self.logger.info(
                f"推論結果: {class_name} (信頼度: {confidence:.3f}, "
                f"処理時間: {inference_time:.3f}秒)"
            )

            return result

        except Exception as e:
            self.logger.error(f"推論中にエラー: {e}")
            return None

    def process_image(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        画像を推論、信頼度チェック、統計情報更新して結果を返す

        Args:
            image_path: motionで撮影された画像のパス
        Returns:
            Dict[str, Any]: 画像の推論結果
        """
        try:
            self.logger.info(f"画像処理を開始: {image_path}")

            # 画像ファイルの存在確認
            if not os.path.exists(image_path):
                self.logger.error(f"画像ファイルが見つかりません: {image_path}")
                return False

            # 画像前処理
            preprocessed_image = self.preprocess_image(image_path)
            if preprocessed_image is None:
                return False

            # 推論実行
            result = self.predict(preprocessed_image)
            if not result:
                return False

            return result

        except Exception as e:
            self.logger.error(f"画像処理中にエラー: {e}")
            return False

    def _update_stats(self, result: Dict[str, Any]):
        """統計情報を更新"""
        self.detection_stats["total_detections"] += 1

        if result["class_name"] == "chige":
            self.detection_stats["chige_count"] += 1
        elif result["class_name"] == "motsu":
            self.detection_stats["motsu_count"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        runtime = datetime.now() - self.detection_stats["start_time"]

        return {
            "runtime_hours": runtime.total_seconds() / 3600,
            "total_detections": self.detection_stats["total_detections"],
            "chige_count": self.detection_stats["chige_count"],
            "motsu_count": self.detection_stats["motsu_count"],
            "start_time": self.detection_stats["start_time"].isoformat(),
        }


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="ちげもつ判別システム")
    parser.add_argument(
        "image_path", nargs="?", help="処理する画像のパス（motionから渡される）"
    )
    parser.add_argument("--stats", action="store_true", help="統計情報を表示")
    parser.add_argument("--test", action="store_true", help="テスト画像で動作確認")
    parser.add_argument("--config", "-c", help="設定ファイルのパス")

    args = parser.parse_args()

    try:
        # システムを初期化
        detector = ChigemotsuDetector(config_path=args.config)

        if args.stats:
            # 統計情報を表示
            stats = detector.get_stats()
            print("\n=== ちげもつ検出統計 ===")
            print(f"稼働時間: {stats['runtime_hours']:.2f} 時間")
            print(f"総検出回数: {stats['total_detections']}")
            print(f"ちげ検出: {stats['chige_count']} 回")
            print(f"もつ検出: {stats['motsu_count']} 回")
            print(f"開始時刻: {stats['start_time']}")

        elif args.test:
            # テスト用画像で動作確認
            camera_images_dir = script_dir.parent.parent / "camera" / "images"
            test_image_path = None

            if camera_images_dir.exists():
                for image_file in camera_images_dir.glob("*.jpg"):
                    test_image_path = str(image_file)
                    break

            if test_image_path:
                print(f"テスト画像で動作確認: {test_image_path}")
                success = detector.process_image(test_image_path)
                if success:
                    print("✅ テスト処理が完了しました")
                else:
                    print("❌ テスト処理に失敗しました")
                    sys.exit(1)
            else:
                print("❌ テスト用画像が見つかりません")
                sys.exit(1)

        elif args.image_path:
            # motionから渡された画像を処理
            success = detector.process_image(args.image_path)
            if success:
                print("✅ 画像処理が完了しました")
            else:
                print("❌ 画像処理に失敗しました")
                sys.exit(1)
        else:
            parser.print_help()
            print("\n使用例:")
            print("# motionからの呼び出し")
            print("chigemotsu-detect /path/to/image.jpg")
            print("\n# テスト実行")
            print("chigemotsu-detect --test")
            print("\n# 統計表示")
            print("chigemotsu-detect --stats")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
