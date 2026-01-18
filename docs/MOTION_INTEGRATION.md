# Motion連携セットアップガイド

motionの動体検知と連携してchigemotsu判別＋LINE通知を実行する設定方法です。

## 前提条件

- Raspberry Pi Zero上でmotionが動作していること
- chigemotsu判別システムがインストール済みであること

## motion.conf設定

### 1. 基本設定
```conf
# カメラ設定
width 640
height 480
framerate 15

# 動体検知設定
threshold 1500
noise_level 32

# 画像保存設定
output_pictures on
picture_type jpeg
picture_quality 75

# 画像保存先
target_dir /home/pi/motion_images

# ファイル名形式
picture_filename %Y%m%d%H%M%S-%q
```

### 2. chigemotsu判別の呼び出し設定
```conf
# 画像保存時にchigemotsu判別を実行
on_picture_save /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh %f
```

## chigemotsu_detect.shスクリプト作成

motion.confから呼び出されるシェルスクリプトを作成します：

```bash
#!/bin/bash
# /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh

# 引数として画像パスを受け取る
IMAGE_PATH="$1"

# ログファイル
LOG_FILE="/home/pi/chigemotsu/chigemotsu-monitor/logs/motion_integration.log"

# 現在時刻をログに記録
echo "$(date): Motion detected, processing image: $IMAGE_PATH" >> "$LOG_FILE"

# 仮想環境をアクティベート（必要に応じて）
cd /home/pi/chigemotsu/chigemotsu-monitor
source .venv/bin/activate

# chigemotsu判別を実行
python3 scripts/integrated_detection.py "$IMAGE_PATH" >> "$LOG_FILE" 2>&1

# 実行結果をログに記録
if [ $? -eq 0 ]; then
    echo "$(date): Detection completed successfully" >> "$LOG_FILE"
else
    echo "$(date): Detection failed" >> "$LOG_FILE"
fi
```

## セットアップ手順

### 1. スクリプトの作成と権限設定
```bash
# スクリプトを作成
sudo nano /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh

# 実行権限を付与
chmod +x /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh

# ログディレクトリを作成
mkdir -p /home/pi/chigemotsu/chigemotsu-monitor/logs
```

### 2. motion.confの編集
```bash
# motion設定ファイルを編集
sudo nano /etc/motion/motion.conf

# 上記の設定を追加
```

### 3. motionの再起動
```bash
sudo systemctl restart motion
sudo systemctl status motion
```

## 動作確認

### 1. 手動テスト
```bash
# テスト画像で動作確認
cd /home/pi/chigemotsu/chigemotsu-monitor
python3 scripts/integrated_detection.py --test

# 特定の画像で確認
python3 scripts/integrated_detection.py /path/to/test/image.jpg
```

### 2. motionとの連携テスト
```bash
# motionのログを確認
sudo tail -f /var/log/motion/motion.log

# chigemotsu統合ログを確認
tail -f /home/pi/chigemotsu/chigemotsu-monitor/logs/motion_integration.log

# 統計情報を確認
python3 scripts/integrated_detection.py --stats
```

## トラブルシューティング

### よくある問題

1. **権限エラー**
   ```bash
   # スクリプトに実行権限を付与
   chmod +x /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh
   ```

2. **Python環境の問題**
   ```bash
   # 仮想環境のパスを確認
   which python3
   
   # 依存関係を確認
   pip3 list | grep -E "(tflite|numpy|PIL)"
   ```

3. **ファイルパスの問題**
   ```bash
   # 画像保存ディレクトリの権限確認
   ls -la /home/pi/motion_images/
   
   # 設定ファイルの確認
   cat /home/pi/chigemotsu/chigemotsu-monitor/config/config.json
   ```

### ログ確認

- **Motion統合ログ**: `/home/pi/chigemotsu/chigemotsu-monitor/logs/motion_integration.log`
- **chigemotsu検出ログ**: `/home/pi/chigemotsu/chigemotsu-monitor/logs/chigemotsu_detection.log`
- **LINE通知ログ**: `/home/pi/chigemotsu/chigemotsu-monitor/logs/line_image_notifier.log`
- **R2アップロードログ**: `/home/pi/chigemotsu/chigemotsu-monitor/logs/r2_uploader.log`

## パフォーマンス調整

### 1. motion設定の最適化
```conf
# CPU負荷軽減
framerate 10           # フレームレート下げる
threshold 2000         # 閾値を上げて誤検知を減らす
minimum_motion_frames 3  # 最小検出フレーム数

# 画像サイズ調整
width 320
height 240
```

### 2. chigemotsu処理の最適化
```json
{
  "model": {
    "threshold": 0.85,     // 信頼度閾値を上げる
    "timeout_seconds": 30  // タイムアウト設定
  }
}
```

## 運用監視

### systemdサービス化（オプション）
```bash
# サービスファイルを作成
sudo nano /etc/systemd/system/chigemotsu-motion.service
```

```ini
[Unit]
Description=Chigemotsu Motion Integration Service
After=motion.service

[Service]
Type=simple
User=pi
ExecStart=/bin/bash -c "tail -f /home/pi/motion_images/*.jpg | while read file; do /home/pi/chigemotsu/chigemotsu-monitor/scripts/chigemotsu_detect.sh \"$file\"; done"
Restart=always

[Install]
WantedBy=multi-user.target
```

これでmotionの動体検知と完全に連携したchigemotsu判別システムが構築できます。
