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
- [ ] 学習済みTFLite Microモデルファイル
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
# (chigemotsu-monitor ディレクトリ直下に配置されるよう、末尾スラッシュ付きでrsyncを使用)
rsync -avz production/ pi@[PI_IP_ADDRESS]:/home/pi/chigemotsu-monitor/

# Raspberry Piにログイン
ssh pi@[PI_IP_ADDRESS]
```

### 自動インストール実行

```bash
# chigemotsu-monitorディレクトリに移動
cd /home/pi/chigemotsu-monitor

# インストールスクリプト実行権限付与
chmod +x setup/install.sh

# インストール実行 (Systemdサービスとタイマーも自動登録されます)
./setup/install.sh
```

## ⚙️ Step 3: 設定ファイル編集

### LINE認証情報設定

```bash
# LINE Bot情報を設定
cp config/line_credentials.json.sample config/line_credentials.json
nano config/line_credentials.json

# 以下のように編集
{
  "line_access_token": "YOUR_ACTUAL_LINE_BOT_ACCESS_TOKEN",
  "line_user_id": "YOUR_ACTUAL_LINE_USER_ID_OR_GROUP_ID"
}
```

### メイン設定調整（必要に応じて）

```bash
# メイン設定ファイル編集
nano config/config.json

# 主要調整項目:
# - model.threshold: 検出閾値（0.75推奨）
# - motion.cleanup_days: 画像保持日数（2日推奨）
# - logging.rotation_days: ログローテーション（14日推奨）
```

## 🧠 Step 4: モデル配置

### モデルファイル転送

```bash
# 学習済みTFLite Microモデルを転送（ローカルから実行）
rsync -av /path/to/your/mobilenet_v2_micro_float32.tflite pi@[PI_IP_ADDRESS]:/home/pi/chigemotsu-monitor/models/

# Raspberry Piでファイル確認
ls -la /home/pi/chigemotsu-monitor/models/
```

### モデル推論テスト

```bash
# 仮想環境アクティベート
source /home/pi/chigemotsu-monitor/.venv/bin/activate

# テスト画像で推論確認
cd /home/pi/chigemotsu-monitor
python3 scripts/integrated_detection.py --test
```

## 🔧 Step 5: システムテスト

### LINE通知テスト

```bash
# LINE通知手動テスト
cd /home/pi/chigemotsu-monitor
python3 scripts/line_image_notifier.py --test
```

### パイプライン全体テスト

```bash
# 統合テスト実行
python3 scripts/chigemotsu_pipeline.py --test
```

## 🚀 Step 6: システム起動と状態確認

### サービスの状態確認
インストールスクリプトにより、システムは既に起動しています。

```bash
# 猫検出システム（Motion + libcamerify）の確認
sudo systemctl status libcamerify_motion

# 定期タスク（日次サマリー、リブート）の確認
sudo systemctl list-timers --all | grep chigemotsu
```

### ログ確認

```bash
# サービスログ（Systemd）
sudo journalctl -u libcamerify_motion -f

# アプリケーションログ（パイプライン全体のログ）
tail -f /home/pi/chigemotsu-monitor/logs/chigemotsu_pipeline.log

# 検出・推論処理の詳細ログ
tail -f /home/pi/chigemotsu-monitor/logs/chigemotsu_detection.log
```

## 📊 Step 7: 運用監視・メンテナンス

### 定期タスクについて
Systemd Timersにより以下のタスクが自動実行されます：
- **毎日 23:50**: 日次サマリー通知 (`chigemotsu_daily_summary.timer`)
- **毎日 23:59**: システムリブート (`chigemotsu_daily_reboot.timer`)

タイマーのログ確認：
```bash
sudo journalctl -u chigemotsu_daily_summary.service
```

### 手動メンテナンス

```bash
# システムの停止
sudo systemctl stop libcamerify_motion

# システムの起動
sudo systemctl start libcamerify_motion

# システムの再起動
sudo systemctl restart libcamerify_motion
```

## 🔍 Step 8: 動作確認・調整

### 検出精度確認

```bash
# カメラ前で動いて検出テスト
# ログで検出結果確認
tail -f /home/pi/chigemotsu-monitor/logs/chigemotsu_detection.log
```

### 閾値調整（必要に応じて）

```bash
# 誤検出が多い場合: 閾値を上げる（0.8-0.9）
# 検出漏れが多い場合: 閾値を下げる（0.6-0.7）
nano /home/pi/chigemotsu-monitor/config/config.json

# 設定変更後はサービスを再起動
sudo systemctl restart libcamerify_motion
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
# 仮想環境とtflite_micro_runtimeの確認
source .venv/bin/activate
python3 -c "import tflite_micro_runtime; print('OK')"
# モデルファイル確認
ls -la /home/pi/chigemotsu-monitor/models/
```

#### LINE通知が送信されない
```bash
# ネットワーク確認
ping -c 3 api.line.me
# 認証情報確認
cat /home/pi/chigemotsu-monitor/config/line_credentials.json
```

#### ディスク容量不足
```bash
# 使用量確認
df -h
# ログファイルが肥大化していないか確認
du -sh /home/pi/chigemotsu-monitor/logs/*
```

## ✅ デプロイメント完了チェックリスト

- [ ] Raspberry Pi Zero基本セットアップ完了
- [ ] カメラ動作確認
- [ ] Production環境インストール完了 (`./setup/install.sh` 実行)
- [ ] LINE認証情報設定 (`line_credentials.json`)
- [ ] モデル配置・推論テスト
- [ ] Systemdサービス (`libcamerify_motion`) 起動確認
- [ ] Systemdタイマー (`chigemotsu_daily_*`) 登録確認
- [ ] LINE通知テスト
- [ ] ログ確認

全チェック完了で、Raspberry Pi Zero猫検出システムの運用開始です！ 🎉

## 📞 サポート・メンテナンス

### 定期確認項目

- **毎日**: ログ確認、検出状況チェック
- **毎週**: ディスク使用量、システム温度チェック  
- **毎月**: システム更新、設定見直し