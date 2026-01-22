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
    echo "⚠️ セキュリティ上の注意:" >&2
    echo "  以下の設定を追加すると、指定したユーザーがパスワードなしでシステムを再起動できるようになります。" >&2
    echo "  これは利便性と引き換えに権限が緩くなる設定です。運用ポリシーやセキュリティ要件を確認のうえ適用してください。" >&2
    echo "  必要に応じて、対象ユーザー名やホストを限定したり、再起動専用のユーザーを作成することを検討してください。" >&2
    echo "  また、sudoers のコマンド指定ではワイルドカード (*) を使わず、下記のように必要なコマンドのみに限定することを推奨します。" >&2
    echo "" >&2
    echo "推奨設定例 (visudo で追加):" >&2
    echo "    $USER ALL=(root) NOPASSWD: /sbin/reboot" >&2
    echo "" >&2
    echo "設定後に、次のコマンドがエラーなく終了することを確認してください:" >&2
    echo "    sudo -n true" >&2
    echo "" >&2
    echo "sudoers の設定が完了したら、このスクリプトを再実行してください。" >&2
    exit 1
fi

# 現在のcrontabをバックアップ
BACKUP_FILE="$(mktemp)" || {
    echo "ERROR: バックアップ用一時ファイルの作成に失敗しました。" >&2
    exit 1
}
crontab -l > "$BACKUP_FILE" 2>/dev/null || true

# 既存の設定を削除（重複防止）
if [ -s "$BACKUP_FILE" ]; then
    tmpfile="$(mktemp)" || {
        echo "ERROR: 一時ファイルの作成に失敗しました。" >&2
        rm -f "$BACKUP_FILE"
        exit 1
    }
    trap 'rm -f "$tmpfile" "$BACKUP_FILE"' EXIT INT TERM
    sed -e '/send_daily_summary.py/d' -e '/sudo .*reboot/d' "$BACKUP_FILE" > "$tmpfile"
    mv "$tmpfile" "$BACKUP_FILE"
    trap - EXIT INT TERM
fi

# 設定ファイルの存在確認
CONFIG_PATH="${BASE_DIR}/config/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "WARNING: 設定ファイルが見つかりません: ${CONFIG_PATH}" >&2
    echo "デフォルト設定で動作する可能性がありますが、確認してください。" >&2
fi

# 新しい設定を追加
# パスにスペースが含まれる可能性を考慮してクォートする
# サマリー通知はリブート(23:59)の十分前(23:50)に実行する
echo "50 23 * * * \"${PYTHON_EXEC}\" \"${SCRIPTS_DIR}/send_daily_summary.py\" --config \"${CONFIG_PATH}\" >> \"${BASE_DIR}/logs/cron_summary.log\" 2>&1" >> "$BACKUP_FILE"
echo "59 23 * * * sudo /sbin/reboot" >> "$BACKUP_FILE"

# 新しいcrontabを適用
crontab "$BACKUP_FILE"
rm -f "$BACKUP_FILE"

echo ""
echo "✅ Cron設定が完了しました"
echo "現在の設定:"
crontab -l | tail -n 5

echo ""
echo "⚠️ 注意: 'sudo reboot' がパスワードなしで実行できることを確認してください。"
echo "確認コマンド: sudo -n true (または実際の再起動テスト)"
