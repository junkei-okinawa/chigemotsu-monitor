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
sudo apt install -y git openssl libssl-dev libbz2-dev libreadline-dev libsqlite3-dev python3-pip motion screen

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

# Motionサービス有効化と停止
sudo systemctl enable motion
sudo systemctl stop motion

# screenとlibcamerifyでmotionを起動
# セッションにはアタッチせず、バックグラウンドで実行
# セッション名は "motion" とする
echo "Starting motion in a detached screen session..."
if screen -list | grep -q "motion"; then
    echo "Screen session 'motion' already exists. Stopping it..."
    screen -S motion -X quit
fi
screen -dmS motion libcamerify motion

echo "Setup completed!"
echo ""
echo "Next steps:"
echo "1. Copy your ONNX model to ${MODELS_DIR}/"
echo "   scp your_tflite_micro_model.tflite ${USER}@raspberrypi:${MODELS_DIR}/mobilenet_v2_tflite_micro.tflite"
echo ""
echo "2. Edit LINE credentials:"
echo "   nano ${CONFIG_DIR}/line_credentials.json"
echo ""
echo "3. Start the system:"
echo "   ${BASE_DIR}/start.sh"
echo ""
echo "4. Check logs:"
echo "   tail -f ${LOGS_DIR}/cat_detection_motion.log"
echo ""
echo "5. Stop the system:"
echo "   ${BASE_DIR}/stop.sh"
echo ""
echo "Configuration files:"
echo "  - Main config: ${CONFIG_DIR}/config.json"
echo "  - LINE config: ${CONFIG_DIR}/line_credentials.json"
echo "  - Motion config: /etc/motion/motion.conf"
