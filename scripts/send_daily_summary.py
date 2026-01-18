#!/usr/bin/env python3
"""
日次サマリー通知スクリプト
DBから当日の検出数を集計し、LINEに通知する
"""

import sys
from datetime import datetime
from pathlib import Path

# プロジェクトパスを追加
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.append(str(project_root))
sys.path.append(str(script_dir))

try:
    from line_image_notifier import LineImageNotifier
    from db_manager import DetectionDBManager
except ImportError as e:
    print(f"❌ 必要なモジュールがインポートできません: {e}")
    sys.exit(1)

def main():
    try:
        # コンポーネント初期化
        db_manager = DetectionDBManager(db_path=str(project_root / "logs" / "detection.db"))
        notifier = LineImageNotifier(config_path=project_root / "config" / "config.json")

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

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
