# 🚀 Raspberry Pi Zero デプロイメント手順書

## 📋 事前準備チェックリスト

### ローカル環境での事前確認

```bash
# productionディレクトリに移動
cd production/

# デプロイメントチェック実行
python3 scripts/check_deployment.py
```

### 必要な情報・ファイル

- [ ] LINE Bot Access Token
- [ ] LINE User ID または Group ID  
- [ ] 学習済みONNXモデルファイル
- [ ] Raspberry Pi ZeroのIPアドレス・SSH接続情報

## 🛠 Step 1: Raspberry Pi Zero基本セットアップ

### OSインストール・初期設定

```bash
# Raspberry Pi OS Lite をmicroSDに書き込み
# SSH有効化、Wi-Fi設定を事前に済ませる

# 初回SSH接続
ssh pi@[PI_IP_ADDRESS]

# システム更新
sudo apt update && sudo apt upgrade -y

# 必要パッケージインストール
sudo apt install -y git rsync
```

### カメラ設定

```bash
# カメラ有効化
sudo raspi-config
# Interface Options -> Camera -> Enable

# 再起動
sudo reboot

# カメラ動作確認
lsusb
ls /dev/video*
```

## 📦 Step 2: Production環境デプロイ

### ファイル転送

```bash
# ローカルからRaspberry Piにproductionディレクトリを転送
scp -r production/ pi@[PI_IP_ADDRESS]:/home/pi/

# Raspberry Piにログイン
ssh pi@[PI_IP_ADDRESS]
```

### 自動インストール実行

```bash
# productionディレクトリに移動
cd /home/pi/production

# インストールスクリプト実行権限付与
chmod +x install.sh

# インストール実行
./install.sh
```

## ⚙️ Step 3: 設定ファイル編集

### LINE認証情報設定

```bash
# LINE Bot情報を設定
nano /home/pi/cat_detection/config/line_credentials.json

# 以下のように編集
{
  "line_access_token": "YOUR_ACTUAL_LINE_BOT_ACCESS_TOKEN",
  "line_user_id": "YOUR_ACTUAL_LINE_USER_ID_OR_GROUP_ID"
}
```

### メイン設定調整（必要に応じて）

```bash
# メイン設定ファイル編集
nano /home/pi/cat_detection/config/config.json

# 主要調整項目:
# - model.threshold: 検出閾値（0.75推奨）
# - motion.cleanup_days: 画像保持日数（2日推奨）
# - logging.rotation_days: ログローテーション（14日推奨）
```

## 🧠 Step 4: ONNXモデル配置

### モデルファイル転送

```bash
# 学習済みONNXモデルを転送（ローカルから実行）
rsync -av /path/to/your/mobilenet_v2_pruning_*.onnx pi@[PI_IP_ADDRESS]:/home/pi/cat_detection/models/

# Raspberry Piでファイル確認
ls -la /home/pi/cat_detection/models/
```

### モデル推論テスト

```bash
# 仮想環境アクティベート
source /home/pi/cat_detection/venv/bin/activate

# テスト画像で推論確認
cd /home/pi/cat_detection
python3 scripts/onnx_inference.py /path/to/test_image.jpg
```

## 🔧 Step 5: システムテスト

### Motion設定確認

```bash
# Motion設定確認
sudo nano /etc/motion/motion.conf

# Motion手動起動テスト
sudo motion -n -c /etc/motion/motion.conf
# Ctrl+Cで停止
```

### LINE通知テスト

```bash
# LINE通知手動テスト
cd /home/pi/cat_detection
echo "デプロイメントテスト" | python3 scripts/line_notifier.py --message "🐱 猫検出システム起動テスト"
```

### ヘルスモニターテスト

```bash
# システム監視テスト
python3 scripts/health_monitor.py
```

## 🚀 Step 6: システム起動

### 本格運用開始

```bash
# 猫検出システム開始
/home/pi/cat_detection/start.sh

# システム状態確認
systemctl status motion

# ログ確認
tail -f /home/pi/cat_detection/logs/cat_detection_motion.log
```

### 自動起動設定（オプション）

```bash
# 起動時自動実行設定
crontab -e

# 以下を追加
@reboot sleep 30 && /home/pi/cat_detection/start.sh
```

## 📊 Step 7: 運用監視セットアップ

### 定期ヘルスチェック

```bash
# 1時間毎のヘルスチェック設定
crontab -e

# 以下を追加
0 * * * * cd /home/pi/cat_detection && ./venv/bin/python3 scripts/health_monitor.py
```

### 週次メンテナンス

```bash
# 週次クリーンアップ設定
crontab -e

# 以下を追加（毎週日曜日3時に実行）
0 3 * * 0 /home/pi/cat_detection/maintenance.sh
```

## 🔍 Step 8: 動作確認・調整

### 検出精度確認

```bash
# カメラ前で動いて検出テスト
# ログで検出結果確認
tail -f /home/pi/cat_detection/logs/cat_detection_motion.log

# 検出統計
grep "Detection:" /home/pi/cat_detection/logs/cat_detection_motion.log | tail -10
```

### 閾値調整（必要に応じて）

```bash
# 誤検出が多い場合: 閾値を上げる（0.8-0.9）
# 検出漏れが多い場合: 閾値を下げる（0.6-0.7）
nano /home/pi/cat_detection/config/config.json

# 設定変更後は再起動
/home/pi/cat_detection/stop.sh
/home/pi/cat_detection/start.sh
```

## 🚨 トラブルシューティング

### よくある問題と対処法

#### カメラが認識されない
```bash
# USB接続確認
lsusb
# カメラデバイス確認  
ls /dev/video*
# Motion設定のvideodeviceパス確認
grep videodevice /etc/motion/motion.conf
```

#### 推論が失敗する
```bash
# ONNXランタイム確認
python3 -c "import onnxruntime; print(onnxruntime.__version__)"
# モデルファイル確認
ls -la /home/pi/cat_detection/models/
# 手動推論テスト
python3 scripts/onnx_inference.py [test_image.jpg]
```

#### LINE通知が送信されない
```bash
# ネットワーク確認
ping -c 3 api.line.me
# 認証情報確認
cat /home/pi/cat_detection/config/line_credentials.json
# 手動通知テスト
echo "test" | python3 scripts/line_notifier.py --message "テスト"
```

#### ディスク容量不足
```bash
# 使用量確認
df -h
# 古いファイル削除
find /home/pi/cat_detection/temp -name "*.jpg" -mtime +2 -delete
find /home/pi/cat_detection/logs -name "*.log.*" -mtime +14 -delete
```

## ✅ デプロイメント完了チェックリスト

- [ ] Raspberry Pi Zero基本セットアップ完了
- [ ] カメラ動作確認
- [ ] Production環境インストール完了  
- [ ] LINE認証情報設定
- [ ] ONNXモデル配置・推論テスト
- [ ] Motion設定・動作確認
- [ ] LINE通知テスト
- [ ] システム起動・ログ確認
- [ ] ヘルスモニター動作確認
- [ ] 検出精度確認・調整
- [ ] 自動起動設定（オプション）
- [ ] 定期メンテナンス設定

全チェック完了で、Raspberry Pi Zero猫検出システムの運用開始です！ 🎉

## 📞 サポート・メンテナンス

### 定期確認項目

- **毎日**: ログ確認、検出状況チェック
- **毎週**: ディスク使用量、システム温度チェック  
- **毎月**: システム更新、設定見直し

### パフォーマンス最適化

- 検出閾値の調整
- Motion設定の微調整
- 不要ファイルの定期削除
- システムリソース監視

運用中の問題や改善案があれば、ログを確認して適切に対応してください。
