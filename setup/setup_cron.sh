#!/bin/bash
# 自動タスク（サマリー通知・リブート）のCron設定スクリプト

set -e

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="${BASE_DIR}/scripts"
PYTHON_EXEC="${BASE_DIR}/.venv/bin/python3"

# 仮想環境のPythonが存在しない場合はシステムのPythonを使用
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="python3"
fi

echo "=== Cron自動タスク設定 ==="
echo "以下のタスクをcrontabに追加します:"
echo "1. 毎日 23:50 - 日次サマリー通知"
echo "2. 毎日 23:59 - システムリブート"

# 現在のcrontabをバックアップ
crontab -l > mycron.backup 2>/dev/null || true

# 既存の設定を削除（重複防止）
if [ -s mycron.backup ]; then
    tmpfile="$(mktemp)"
    sed -e '/send_daily_summary.py/d' -e '/sudo reboot/d' mycron.backup > "$tmpfile"
    mv "$tmpfile" mycron.backup
fi

# 新しい設定を追加
echo "50 23 * * * ${PYTHON_EXEC} ${SCRIPTS_DIR}/send_daily_summary.py >> ${BASE_DIR}/logs/cron_summary.log 2>&1" >> mycron.backup
echo "59 23 * * * sudo reboot" >> mycron.backup

# 新しいcrontabを適用
crontab mycron.backup
rm mycron.backup

echo ""
echo "✅ Cron設定が完了しました"
echo "現在の設定:"
crontab -l | tail -n 5

echo ""
echo "⚠️ 注意: 'sudo reboot' がパスワードなしで実行できることを確認してください。"
echo "確認コマンド: sudo -n reboot --dry-run"
