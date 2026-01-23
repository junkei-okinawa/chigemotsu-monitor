#!/bin/bash
# Raspberry Pi Zero用猫検出システムインストールスクリプト

set -e

# 定数定義
BASE_DIR="${HOME}/chigemotsu-monitor"
CONFIG_DIR="${BASE_DIR}/config"
SCRIPTS_DIR="${BASE_DIR}/scripts"
MODELS_DIR="${BASE_DIR}/models"
LOGS_DIR="${BASE_DIR}/logs"
TEMP_DIR="${BASE_DIR}/temp"

echo "Installing Cat Detection System for Raspberry Pi Zero..."

# システム更新
sudo apt update && sudo apt upgrade -y

# 必要パッケージインストール
sudo apt install -y git openssl libssl-dev libbz2-dev libreadline-dev libsqlite3-dev python3-pip motion

# ディレクトリ作成
sudo mkdir -p "${BASE_DIR}"/{models,scripts,config,logs,temp}

# 現在のユーザーに所有権を変更
sudo chown -R $USER:$USER "${BASE_DIR}"

# ディレクトリ権限確認
echo "Directory permissions:"
ls -la "${BASE_DIR}/"

# pyenvをインストール
if ! command -v pyenv &> /dev/null; then
    echo "Installing pyenv..."
    git clone https://github.com/yyuu/pyenv.git ~/.pyenv
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
    echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
    source ~/.bashrc
    pyenv install 3.9.19
    pyenv global 3.9.19
else
    echo "pyenv is already installed."
fi

# uv をインストール
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    pip install uv
else
    echo "uv is already installed."
fi

# Python仮想環境作成
echo "Creating Python virtual environment..."
cd "${BASE_DIR}"
echo "3.9.19" > .python-version
uv sync --python-version .python-version
source .venv/bin/activate

# 最適化されたtflite Micro Runtimeをインストール
if ! ls .venv/lib/python3.9/site-packages/tflite_micro_runtime > /dev/null; then
    echo "Installing tflite_micro_runtime..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    bash "${SCRIPT_DIR}/install_tflite_prebuilt.sh"
else
    echo "tflite_micro_runtime is already installed."
fi

# Motion設定バックアップと更新
if [ -f /etc/motion/motion.conf ]; then
    sudo cp /etc/motion/motion.conf /etc/motion/motion.conf.backup
    echo "Motion config backed up"
fi

# Motion基本設定を追記
sudo tee -a /etc/motion/motion.conf > /dev/null << EOF
##############################################################
# Add Settings
##############################################################
# SYSTEM
daemon off
log_file /tmp/motion.log
target_dir /tmp

# VIDEO
videodevice /dev/video0
# norm 1
# v4l2_palette 8
width 1920
height 1920
# framerate 30

# STREAM
stream_localhost off
# stream_maxrate 30
# stream_quality 50

# DETECTION
threshold 10000
# locate_motion_mode on
# locate_motion_style redbox

picture_type jpeg

picture_output on
movie_output off
# framerate 50
event_gap 2
output_pictures best
rotate 180
pre_capture 1

on_picture_save $BASE_DIR/scripts/chigemotsu_detect.sh %f
EOF

# Motion設定確認
echo "Motion configuration updated"

# Systemdサービスの設定 (libcamerify_motion)
SERVICE_FILE="${BASE_DIR}/systemd/libcamerify_motion.service"
TARGET_SERVICE_FILE="/etc/systemd/system/libcamerify_motion.service"

if [ -f "$SERVICE_FILE" ]; then
    echo "Setting up systemd service..."
    
    # 標準のMotionサービス有効化と停止（競合を防ぐため）
    # libcamerify版が存在する場合のみ実行
    sudo systemctl stop motion
    sudo systemctl disable motion
    
    sudo cp "$SERVICE_FILE" "$TARGET_SERVICE_FILE"
    
    # USERとGROUPプレースホルダの置き換え（他のsystemd設定と統一）
    CURRENT_USER=$(whoami)
    CURRENT_GROUP=$(id -gn)
    
    # sed の置換文字列で特別な意味を持つ文字 (\, &, |) をエスケープ
    ESCAPED_USER=$(printf '%s' "$CURRENT_USER" | sed 's/[\&|]/\\&/g')
    ESCAPED_GROUP=$(printf '%s' "$CURRENT_GROUP" | sed 's/[\&|]/\\&/g')
    
    sudo sed -i "s|<USER>|$ESCAPED_USER|g" "$TARGET_SERVICE_FILE"
    sudo sed -i "s|<GROUP>|$ESCAPED_GROUP|g" "$TARGET_SERVICE_FILE"
    
    # 置換が成功したことを確認
    if grep -q '<USER>\|<GROUP>' "$TARGET_SERVICE_FILE"; then
        echo "Error: Placeholder replacement failed in $TARGET_SERVICE_FILE"
        exit 1
    fi
    
    # 新しいサービスの有効化と起動
    sudo systemctl daemon-reload
    sudo systemctl enable libcamerify_motion
    sudo systemctl restart libcamerify_motion
    
    echo "libcamerify_motion service started."
else
    echo "Error: Service file not found at $SERVICE_FILE"
    echo "Skipping service installation."
fi

# 自動タスク（日次サマリー・リブート）のタイマー設定
if [ -f "${BASE_DIR}/setup/setup_systemd_timers.sh" ]; then
    echo "Setting up systemd timers..."
    bash "${BASE_DIR}/setup/setup_systemd_timers.sh"
else
    echo "Warning: setup_systemd_timers.sh not found."
fi

echo "Setup completed!"
echo ""
echo "Next steps:"
echo "1. Copy your ONNX model to ${MODELS_DIR}/"
echo "   scp your_tflite_micro_model.tflite ${USER}@raspberrypi:${MODELS_DIR}/mobilenet_v2_tflite_micro.tflite"
echo ""
echo "2. Edit LINE credentials:"
echo "   nano ${CONFIG_DIR}/line_credentials.json"
echo ""
echo "3. Check service status:"
echo "   sudo systemctl status libcamerify_motion"
echo "   sudo systemctl list-timers --all | grep chigemotsu"
echo ""
echo "4. Check logs:"
echo "   # Service logs"
echo "   sudo journalctl -u libcamerify_motion -f"
echo "   # Python app logs"
echo "   tail -f ${LOGS_DIR}/cat_detection_motion.log"
echo ""
echo "5. Stop/Start the system:"
echo "   sudo systemctl stop libcamerify_motion"
echo "   sudo systemctl start libcamerify_motion"
echo ""
echo "Configuration files:"
echo "  - Main config: ${CONFIG_DIR}/config.json"
echo "  - LINE config: ${CONFIG_DIR}/line_credentials.json"
echo "  - Motion config: /etc/motion/motion.conf"
echo "  - Service definition: /etc/systemd/system/libcamerify_motion.service"
