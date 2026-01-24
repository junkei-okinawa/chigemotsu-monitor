#!/bin/bash
# motion連携用ちげもつ判別スクリプト
# motionのon_picture_saveから呼び出される

# 引数として画像パスを受け取る
IMAGE_PATH="$1"

# 本実行ファイルのパス
SCRIPT_PATH="$(realpath "$0")"

# プロジェクトディレクトリのパス。SCRIPT_PATHの2階層上
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"

# ログファイル
LOG_FILE="$PROJECT_DIR/logs/motion_integration.log"

# 引数チェック
if [ -z "$IMAGE_PATH" ]; then
    echo "$(date): Error: No image path provided" >> "$LOG_FILE"
    exit 1
fi

# 画像ファイルの存在確認
if [ ! -f "$IMAGE_PATH" ]; then
    echo "$(date): Error: Image file not found: $IMAGE_PATH" >> "$LOG_FILE"
    exit 1
fi

# 現在時刻をログに記録
echo "$(date): Motion detected, processing image: $IMAGE_PATH" >> "$LOG_FILE"

# ちげもつ判別・LINE通知パイプラインを実行
cd "$PROJECT_DIR"
sudo "$PROJECT_DIR/.venv/bin/python3" scripts/chigemotsu_pipeline.py "$IMAGE_PATH" >> "$LOG_FILE" 2>&1

# 実行結果をログに記録
if [ $? -eq 0 ]; then
    echo "$(date): Pipeline completed successfully for $IMAGE_PATH" >> "$LOG_FILE"
else
    echo "$(date): Pipeline failed for $IMAGE_PATH" >> "$LOG_FILE"
    exit 1
fi
