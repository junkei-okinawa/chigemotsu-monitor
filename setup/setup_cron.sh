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

# ログディレクトリを作成（Cron実行時に存在しないとエラーになるため）
mkdir -p "${BASE_DIR}/logs"

# sudo reboot がパスワードなしで実行できるか事前に検証
if ! sudo -n true >/dev/null 2>&1; then
    echo "ERROR: パスワードなしで sudo コマンドを実行できるように sudoers を設定してください。" >&2
    echo "" >&2
    echo "推奨設定 (visudo で追加):" >&2
    echo "    $USER ALL=(root) NOPASSWD: /sbin/reboot, /usr/sbin/reboot, /bin/systemctl reboot, /usr/bin/systemctl reboot" >&2
    echo "" >&2
    echo "設定後に、次のコマンドがエラーなく終了することを確認してください:" >&2
    echo "    sudo -n true" >&2
    echo "" >&2
    echo "sudoers の設定が完了したら、このスクリプトを再実行してください。" >&2
    exit 1
fi

# 現在のcrontabをバックアップ
crontab -l > mycron.backup 2>/dev/null || true

# 既存の設定を削除（重複防止）
if [ -s mycron.backup ]; then
    tmpfile="$(mktemp)" || { echo "Error: failed to create temporary file." >&2; exit 1; }
    trap 'rm -f "$tmpfile"' EXIT
    sed -e '/send_daily_summary.py/d' -e '/sudo reboot/d' mycron.backup > "$tmpfile"
    mv "$tmpfile" mycron.backup
    trap - EXIT
fi

# 設定ファイルの存在確認
CONFIG_PATH="${BASE_DIR}/config/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "WARNING: 設定ファイルが見つかりません: ${CONFIG_PATH}" >&2
    echo "デフォルト設定で動作する可能性がありますが、確認してください。" >&2
fi

# 新しい設定を追加
# パスにスペースが含まれる可能性を考慮してクォートする
echo "50 23 * * * \"${PYTHON_EXEC}\" \"${SCRIPTS_DIR}/send_daily_summary.py\" >> \"${BASE_DIR}/logs/cron_summary.log\" 2>&1" >> mycron.backup
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
echo "確認コマンド: sudo -n true (または実際の再起動テスト)"
