# リファレンス & 詳細マニュアル

本ドキュメントでは、Chigemotsu Monitorのシステム構成、各コマンドの使用方法、設定詳細について解説します。

## 🏗️ システム構成

```
production/
├── 📁 config/                        # 設定ファイル
│   ├── config.json                   # メイン設定
│   ├── line_credentials.json         # LINE認証情報
│   └── r2_credentials.json           # Cloudflare R2認証情報
├── 📁 scripts/                       # 実行スクリプト
│   ├── integrated_detection.py       # TensorFlow Lite推論エンジン
│   ├── line_image_notifier.py        # LINE通知システム
│   ├── r2_uploader.py                # R2アップローダー
│   ├── chigemotsu_pipeline.py        # 推論→通知統合パイプライン
│   ├── test_line_notification.py     # 通知テストツール
│   ├── chigemotsu_detect.sh          # motion連携シェルスクリプト
│   ├── setup_line_notifications.sh   # LINE設定補助スクリプト
│   └── run_tests.py                  # テスト実行ランナー
├── 📁 models/                        # AIモデル
│   └── mobilenet_v2_micro_float32.tflite  # 軽量判別モデル
├── 📁 tests/                         # テストスイート
│   ├── fixtures/                     # テスト用画像
│   ├── unit/                         # ユニットテスト
│   └── integration/                  # 統合テスト
├── 📁 logs/                          # ログファイル
├── 📁 docs/                          # ドキュメント
├── 📁 setup/                         # セットアップスクリプト
│   ├── install.sh                    # 自動インストールスクリプト
│   └── install_tflite_prebuilt.sh    # TensorFlow Lite Runtime セットアップ
├── 📁 tools/                         # 開発・変換ツール
├── pyproject.toml                    # 依存関係設定
└── Makefile                          # Makeコマンド定義
```

## 📋 コマンドリファレンス

### 統合パイプライン（推奨）
```bash
# motionからの自動呼び出し（通常は手動実行不要）
python scripts/chigemotsu_pipeline.py /path/to/image.jpg

# パイプライン全体のテスト
python scripts/chigemotsu_pipeline.py --test

# パイプライン統計情報表示
python scripts/chigemotsu_pipeline.py --stats

# システム通知送信
python scripts/chigemotsu_pipeline.py --notify startup
python scripts/chigemotsu_pipeline.py --notify error
python scripts/chigemotsu_pipeline.py --notify summary
```

### TensorFlow Lite推論エンジン
```bash
# 単一画像の推論のみ（通知なし）
python scripts/integrated_detection.py /path/to/image.jpg

# 推論エンジンのテスト
python scripts/integrated_detection.py --test

# 推論統計情報表示
python scripts/integrated_detection.py --stats
```

### LINE通知システム
```bash
# 画像付き通知送信
python scripts/line_image_notifier.py --image /path/to/image.jpg --message "メッセージ"

# テスト通知
python scripts/line_image_notifier.py --test

# ストレージ統計
python scripts/line_image_notifier.py --stats
```

### Cloudflare R2アップローダー
```bash
# 画像アップロード
python scripts/r2_uploader.py upload --image /path/to/image.jpg

# 画像一覧表示
python scripts/r2_uploader.py list

# 古い画像削除（7日以上）
python scripts/r2_uploader.py cleanup --days 7

# バケット統計
python scripts/r2_uploader.py stats
```

### 通知テストツール
```bash
# 全機能テスト
python scripts/test_line_notification.py --test all

# 三毛猫検出テスト
python scripts/test_line_notification.py --test chige

# 白黒猫検出テスト
python scripts/test_line_notification.py --test motsu

# システム通知テスト
python scripts/test_line_notification.py --test startup
python scripts/test_line_notification.py --test error
python scripts/test_line_notification.py --test summary
```

## 🔧 設定詳細

### config/config.json

```json
{
  "model": {
    "model_path": "./models/mobilenet_v2_micro_float32.tflite",
    "class_names": ["chige", "motsu", "other"],
    "threshold": 0.75,
    "timeout_seconds": 60
  },
  "line": {
    "credentials_file": "./line_credentials.json",
    "api_url": "https://api.line.me/v2/bot/message/push",
    "timeout_seconds": 15,
    "retry_count": 3,
    "notification_enabled": true,
    "include_confidence": true
  },
  "r2": {
    "credentials_file": "./r2_credentials.json",
    "upload_enabled": true,
    "public_url_enabled": true
  },
  "motion": {
    "image_formats": [".jpg", ".jpeg", ".png"],
    "cleanup_days": 2,
    "max_file_size_mb": 10,
    "filename_pattern": "正規表現パターン"
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "file": "./logs/detection.log",
    "rotation_days": 14,
    "max_log_files": 30
  }
}
```

### 主要パラメータ

- **threshold**: 検出信頼度閾値（0.0-1.0、デフォルト: 0.75）
- **timeout_seconds**: モデル推論タイムアウト時間
- **retry_count**: LINE API リトライ回数
- **cleanup_days**: 古い画像の自動削除日数
- **max_file_size_mb**: 処理可能な最大画像サイズ

## 🧪 テスト機能

### 自動テストスイート

```bash
# pytest実行
make test

# カバレッジ付きテスト
make test-cov

# 並列テスト実行
make test-parallel

# 統合テスト
make test-integration
```

### 手動テスト

```bash
# パイプライン全体の統合テスト
python scripts/chigemotsu_pipeline.py --test

# 通知システム全機能テスト
python scripts/test_line_notification.py --test all

# 期待される出力:
# ✅ 成功 シンプルメッセージ
# ✅ 成功 三毛猫検出  
# ✅ 成功 白黒猫検出
# ✅ 成功 非猫検出
# ✅ 成功 システム起動
# ✅ 成功 システムエラー
# ✅ 成功 日次サマリー
# 🎯 総合結果: 7/7 テスト通過
```

## 📊 ログとモニタリング

### ログファイル

- `logs/chigemotsu_pipeline.log` - 統合パイプラインログ
- `logs/chigemotsu_detection.log` - TensorFlow Lite推論ログ
- `logs/line_image_notifier.log` - LINE通知ログ  
- `logs/r2_uploader.log` - R2アップロードログ
- `logs/motion_integration.log` - Motion連携ログ

### 統計情報

```bash
# パイプライン統計表示（推奨）
python scripts/chigemotsu_pipeline.py --stats

# 出力例:
# === ちげもつパイプライン統計 ===
# 稼働時間: 24.5 時間
# 総処理回数: 42
# 成功検出: 38
# 通知送信: 15

# TensorFlow Lite推論エンジン統計
python scripts/integrated_detection.py --stats
```

## 🏭 本番運用

### Motion連携設定

1. **motion.conf編集**
```bash
sudo vim /etc/motion/motion.conf
```

2. **設定追加**
```
# ちげもつ判別連携
on_picture_save /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh %f
```

3. **権限設定**
```bash
chmod +x scripts/chigemotsu_detect.sh
```

### systemdサービス設定

```bash
# motionサービス確認
sudo systemctl status motion

# 自動起動設定
sudo systemctl enable motion
```

### 監視とメンテナンス

```bash
# パイプラインログ監視（推奨）
tail -f logs/chigemotsu_pipeline.log

# Motion連携ログ監視
tail -f logs/motion_integration.log

# 全ログ同時監視
tail -f logs/*.log

# ディスク使用量チェック
du -sh logs/ models/ tests/fixtures/

# 古いログファイル削除
find logs/ -name "*.log*" -mtime +30 -delete
```

## 🔧 トラブルシューティング

### よくある問題

1. **TensorFlow Lite Runtime エラー**
```bash
# 再インストール
./setup/install_tflite_prebuilt.sh
```

2. **パイプライン全体の動作確認**
```bash
# 統合テスト実行
python scripts/chigemotsu_pipeline.py --test
```

3. **LINE通知失敗**
```bash
# 認証情報確認
python scripts/test_line_notification.py --test simple
```

4. **R2アップロード失敗**
```bash
# 認証情報とネットワーク確認
python scripts/r2_uploader.py stats
```

5. **Segmentation Fault**
```bash
# NumPy バージョン確認
pip install "numpy>=1.21.0,<2.0.0"
```

### デバッグモード

```bash
# パイプライン詳細ログ出力
export PYTHONPATH=/path/to/production
python -v scripts/chigemotsu_pipeline.py --test

# 推論エンジン詳細ログ
python -v scripts/integrated_detection.py --test
```

## 依存関係

### 本番環境（Raspberry Pi Zero）
- Python 3.9+
- tflite_micro_runtime 1.2.2+
- numpy <2.0.0
- Pillow 9.0+
- boto3 1.26+
- requests 2.28+

### 開発環境
- すべての本番依存関係
- tensorflow 2.14+
- pytest 7.0+
- black, flake8, mypy
