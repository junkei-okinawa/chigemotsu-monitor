#!/usr/bin/env python3
"""
日次サマリー通知スクリプト
DBから当日の検出数を集計し、LINEに通知する
"""

import sys
import argparse
import traceback
import sqlite3
from datetime import datetime
from pathlib import Path

# プロジェクトパスを追加
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(script_dir))

import_error = None
try:
    from line_image_notifier import LineImageNotifier
    from db_manager import DetectionDBManager
except ImportError as e:
    # インポートエラーは記録するが、テストコレクションを妨げないようここでは終了しない
    LineImageNotifier = None
    DetectionDBManager = None
    import_error = e

def main():
    if LineImageNotifier is None or DetectionDBManager is None:
        print(f"❌ 必要なモジュールがインポートされていないため実行できません: {import_error}")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="日次サマリー通知スクリプト")
    parser.add_argument("--config", "-c", help="設定ファイルのパス")
    args = parser.parse_args()

    config_path = args.config if args.config else project_root / "config" / "config.json"

    try:
        # コンポーネント初期化
        db_path = project_root / "logs" / "detection.db"
        db_manager = DetectionDBManager(db_path=str(db_path))
        notifier = LineImageNotifier(config_path=config_path)

        # 今日の統計取得
        stats = db_manager.get_daily_stats()
        
        # 0件の場合は0を設定
        chige_count = stats.get("chige", 0)
        motsu_count = stats.get("motsu", 0)
        other_count = stats.get("other", 0)
        total_count = sum(stats.values())

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # メッセージ作成
        message = (
            "📊 本日の検出サマリー\n"
            f"📅 {timestamp}\n\n"
            f"🐈 三毛猫（ちげ）: {chige_count}回\n"
            f"🐈‍⬛ 白黒猫（もつ）: {motsu_count}回\n"
            f"❓ その他: {other_count}回\n"
            f"📈 合計検出数: {total_count}回\n\n"
            "本日の監視を終了します。おやすみなさい💤"
        )

        # 送信
        if notifier.send_message(message):
            print("✅ 日次サマリーの送信に成功しました")
        else:
            print("❌ 日次サマリーの送信に失敗しました")
            sys.exit(1)

    except (sqlite3.Error, FileNotFoundError) as e:
        print(f"❌ エラーが発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"❌ 予期せぬエラーが発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
