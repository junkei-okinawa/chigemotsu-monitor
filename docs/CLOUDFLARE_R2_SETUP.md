# Cloudflare R2とLINE画像通知の実装

## 概要

Cloudflare R2ストレージを使用してLINE通知に画像を含める機能を実装しました。この実装により、物体検出結果を画像付きでLINE通知できるようになります。

## 実装されたファイル

### 1. R2アップローダー (`r2_uploader.py`)
- Cloudflare R2へのS3互換API経由での画像アップロード
- 公開URLの生成
- 古い画像の自動削除
- バケット統計の取得

### 2. LINE画像通知システム (`line_image_notifier.py`)
- R2Uploaderと連携した画像付きLINE通知
- 検出結果付き通知
- エラーハンドリングとリトライ機能

### 3. 統合検出システム (`integrated_detection.py`)
- カメラ撮影、推論、LINE通知の統合
- TFLiteモデルを使用した物体検出
- 連続監視機能

## 設定

### config.json
```json
{
  "line": {
    "access_token": "YOUR_LINE_ACCESS_TOKEN",
    "user_id": "YOUR_USER_ID",
    "api_url": "https://api.line.me/v2/bot/message/push",
    "timeout_seconds": 15,
    "retry_count": 3
  },
  "image_upload": {
    "method": "r2"
  },
  "r2": {
    "credentials_file": "./config/r2_credentials.json"
  }
}
```

### r2_credentials.json
```json
{
  "account_id": "0d5673ad0a870c80557a79daf50e68de",
  "access_key_id": "46d41fdddf5034f7d00207e99ec16c1d",
  "secret_access_key": "YOUR_SECRET_ACCESS_KEY",
  "bucket_name": "chigemotsu-images"
}
```

## 使用方法

### 1. セットアップ（Raspberry Pi Zero）
```bash
# メインのインストールスクリプトを実行（依存関係やサービスが登録されます）
./setup/install.sh
```

### 2. R2接続テスト
```bash
python3 scripts/r2_uploader.py test
```

### 3. LINE通知テスト
```bash
# シンプルなテスト
python3 scripts/test_line_notification.py --test simple

# 画像付き通知テスト
python3 scripts/line_image_notifier.py --test
```

### 4. 画像通知の送信
```bash
# 単体で画像通知を送信
python3 scripts/line_image_notifier.py --image /path/to/image.jpg --message "検出結果です"

# テスト画像で通知
python3 scripts/line_image_notifier.py --test

# ストレージ統計を確認
python3 scripts/line_image_notifier.py --stats
```

### 5. 統合検出システム
```bash
# 単発検出（撮影→推論→通知）
python3 scripts/integrated_detection.py --single

# 連続監視（30秒間隔）
python3 scripts/integrated_detection.py --monitor --interval 30

# 統計情報表示
python3 scripts/integrated_detection.py --stats
```

## プログラム内での使用

### LineImageNotifierの使用例
```python
from line_image_notifier import LineImageNotifier

# 初期化
notifier = LineImageNotifier()

# 画像通知を送信
success = notifier.send_image_notification(
    image_path="/path/to/image.jpg",
    message="猫を検出しました！",
    cleanup_after_days=7
)

# 検出結果付き通知
success = notifier.send_detection_notification(
    image_path="/path/to/image.jpg",
    confidence=0.85,
    class_name="chige"
)
```

### R2Uploaderの直接使用
```python
from r2_uploader import R2Uploader

# 初期化
uploader = R2Uploader()

# 画像をアップロード
result = uploader.upload_image("/path/to/image.jpg")
if result:
    public_url = result['public_url']
    print(f"画像URL: {public_url}")
```

## 特徴

### セキュリティ
- 認証情報は設定ファイルで管理
- S3互換APIによる安全なアップロード
- 古い画像の自動削除でストレージ管理

### 信頼性
- リトライ機能付きのLINE API呼び出し
- エラーハンドリングとログ出力
- 接続失敗時のフォールバック処理

### Raspberry Pi Zero対応
- ARMv6L アーキテクチャに対応
- 軽量なTFLiteモデルを使用
- 省メモリ設計

### 運用性
- systemdサービス対応
- ログローテーション設定
- 統計情報の追跡

## 依存関係

### Python パッケージ
```bash
pip3 install boto3 botocore requests opencv-python tensorflow numpy
```

### システム要件
- Python 3.7+
- OpenCV（カメラ機能用）
- TensorFlow Lite（推論用）

## ログファイル

- `/opt/chigemotsu/chigemotsu-monitor/logs/line_image_notifier.log`
- `/opt/chigemotsu/chigemotsu-monitor/logs/r2_uploader.log`
- `/opt/chigemotsu/chigemotsu-monitor/logs/integrated_detection.log`

## トラブルシューティング

### R2接続エラー
1. 認証情報の確認
2. ネットワーク接続の確認
3. バケット名の確認

### LINE通知エラー
1. アクセストークンの確認
2. ユーザーIDの確認
3. ネットワーク接続の確認

### 画像アップロードエラー
1. 画像ファイルの存在確認
2. ファイル権限の確認
3. ストレージ容量の確認

## 制限事項

### Cloudflare R2
- アップロード上限: 5TB
- 無料枠: 10GB/月
- リクエスト制限あり

### LINE Messaging API
- 画像サイズ上限: 10MB
- 対応形式: JPEG, PNG
- レート制限あり

## セキュリティ考慮事項

1. **認証情報の保護**
   - r2_credentials.jsonの権限設定（600推奨）
   - Gitリポジトリからの除外（.gitignore設定済み）

2. **画像の自動削除**
   - 古い画像の定期削除
   - ストレージコスト削減

3. **ログの管理**
   - 個人情報を含まないログ設計
   - ローテーション設定
