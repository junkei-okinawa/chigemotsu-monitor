#!/bin/bash
# Systemd Timers (Daily Summary & Reboot) Install Script

set -e

# 定数定義
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SYSTEMD_DIR="${BASE_DIR}/systemd"
TARGET_DIR="/etc/systemd/system"
CURRENT_USER=$(whoami)

echo "Installing Systemd Timers for Chigemotsu Monitor..."

# 必要なファイルリスト
FILES=(
    "chigemotsu_daily_summary.service"
    "chigemotsu_daily_summary.timer"
    "chigemotsu_daily_reboot.service"
    "chigemotsu_daily_reboot.timer"
)

for FILE in "${FILES[@]}"; do
    SRC="${SYSTEMD_DIR}/${FILE}"
    DST="${TARGET_DIR}/${FILE}"

    if [ -f "$SRC" ]; then
        echo "Installing $FILE..."
        sudo cp "$SRC" "$DST"

        # プレースホルダーの置換
        # パスにスラッシュが含まれるため、区切り文字に | を使用
        sudo sed -i "s|<USER>|$CURRENT_USER|g" "$DST"
        sudo sed -i "s|<BASE_DIR>|$BASE_DIR|g" "$DST"
    else
        echo "Error: Source file $SRC not found."
        exit 1
    fi
done

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling and starting timers..."
# Service自体はenableせず、Timerのみenableにする
sudo systemctl enable --now chigemotsu_daily_summary.timer
sudo systemctl enable --now chigemotsu_daily_reboot.timer

echo "Checking timer status..."
sudo systemctl list-timers --all | grep chigemotsu

echo "Systemd timers setup completed!"
