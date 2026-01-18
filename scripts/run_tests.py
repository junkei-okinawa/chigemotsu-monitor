#!/usr/bin/env python3
"""
テスト実行スクリプト
pytestの様々な実行パターンを提供
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str = "") -> int:
    """コマンドを実行して結果を返す"""
    if description:
        print(f"🚀 {description}")
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Chigemotsu test runner")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "all", "coverage", "fast", "slow"],
        help="実行するテストの種類"
    )
    parser.add_argument(
        "--file", "-f",
        help="特定のテストファイルを実行"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細出力"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="デバッグモード"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="並列実行"
    )

    args = parser.parse_args()

    # ベースコマンド
    cmd = ["pytest"]

    # テストタイプに応じた設定
    if args.test_type == "unit":
        cmd.extend(["tests/unit/", "-m", "unit"])
    elif args.test_type == "integration":
        cmd.extend(["tests/integration/", "-m", "integration"])
    elif args.test_type == "all":
        cmd.append("tests/")
    elif args.test_type == "coverage":
        cmd.extend([
            "tests/",
            "--cov=scripts",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    elif args.test_type == "fast":
        cmd.extend(["tests/", "-m", "not slow"])
    elif args.test_type == "slow":
        cmd.extend(["tests/", "-m", "slow"])

    # 特定のファイル指定
    if args.file:
        if args.test_type in ["unit"]:
            cmd = ["pytest", f"tests/unit/test_{args.file}.py"]
        elif args.test_type in ["integration"]:
            cmd = ["pytest", f"tests/integration/test_{args.file}.py"]
        else:
            cmd = ["pytest", f"tests/**/test_{args.file}.py"]

    # オプションの追加
    if args.verbose:
        cmd.append("-v")
    
    if args.debug:
        cmd.extend(["-s", "--tb=long", "--pdb"])
    else:
        cmd.append("--tb=short")

    if args.parallel and args.test_type != "coverage":
        cmd.extend(["-n", "auto"])

    # テスト実行
    return run_command(cmd, f"Running {args.test_type} tests")


if __name__ == "__main__":
    sys.exit(main())
