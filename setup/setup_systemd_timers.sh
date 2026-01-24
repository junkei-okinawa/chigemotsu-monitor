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
        # sed の置換文字列で特別な意味を持つ文字 (\, &, |) をエスケープ
        ESCAPED_USER=$(printf '%s' "$CURRENT_USER" | sed 's/[\\&|]/\\&/g')
        ESCAPED_BASE_DIR=$(printf '%s' "$BASE_DIR" | sed 's/[\\&|]/\\&/g')

        sudo sed -i "s|<USER>|$ESCAPED_USER|g" "$DST"
        sudo sed -i "s|<BASE_DIR>|$ESCAPED_BASE_DIR|g" "$DST"

        # 置換が成功したことを確認（プレースホルダーが残っていないかチェック）
        if grep -q '<USER>\|<BASE_DIR>' "$DST"; then
            echo "Error: Placeholder replacement failed in $DST"
            exit 1
        fi
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
sudo systemctl list-timers --all | grep chigemotsu || true

echo "Systemd timers setup completed!"
