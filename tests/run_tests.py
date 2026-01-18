#!/usr/bin/env python3
"""
テスト実行用スクリプト
unittest と pytest の両方をサポート
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_unittest_tests(test_type=None, verbose=False):
    """unittestでテストを実行"""
    print("🧪 Running tests with unittest...")
    
    # テストディレクトリ
    test_dir = Path(__file__).parent
    
    # テストパターンを設定
    if test_type == "unit":
        pattern = "test_*.py"
        start_dir = test_dir / "unit"
    elif test_type == "integration":
        pattern = "test_*.py"
        start_dir = test_dir / "integration"
    else:
        pattern = "test_*.py"
        start_dir = test_dir
    
    # unittestコマンドを構築
    cmd = [
        sys.executable, "-m", "unittest", "discover",
        "-s", str(start_dir),
        "-p", pattern
    ]
    
    if verbose:
        cmd.append("-v")
    
    # テストを実行
    try:
        result = subprocess.run(cmd, cwd=test_dir.parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running unittest: {e}")
        return False


def run_pytest_tests(test_type=None, verbose=False, coverage=False):
    """pytestでテストを実行"""
    print("🧪 Running tests with pytest...")
    
    # テストディレクトリ
    test_dir = Path(__file__).parent
    
    # pytestコマンドを構築
    cmd = [sys.executable, "-m", "pytest"]
    
    # テストタイプによるフィルタリング
    if test_type == "unit":
        cmd.extend(["-m", "unit", str(test_dir / "unit")])
    elif test_type == "integration":
        cmd.extend(["-m", "integration", str(test_dir / "integration")])
    else:
        cmd.append(str(test_dir))
    
    # オプション設定
    if verbose:
        cmd.extend(["-v", "-s"])
    
    if coverage:
        cmd.extend([
            "--cov=scripts",
            "--cov-report=html:tests/coverage_html",
            "--cov-report=term-missing"
        ])
    
    # 並列実行（オプション）
    # cmd.extend(["-n", "auto"])  # pytest-xdist が必要
    
    # テストを実行
    try:
        result = subprocess.run(cmd, cwd=test_dir.parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running pytest: {e}")
        return False


def check_dependencies():
    """テスト実行に必要な依存関係をチェック"""
    print("🔍 Checking test dependencies...")
    
    required_packages = [
        "pytest",
        "pytest-cov",
        "pytest-mock",
        "numpy",
        "Pillow",
        "boto3",
        "requests"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("💡 Install with: uv pip install -e '.[test]'")
        return False
    
    print("✅ All test dependencies are available")
    return True


def run_specific_test(test_path, runner="pytest", verbose=False):
    """特定のテストファイルまたはメソッドを実行"""
    print(f"🎯 Running specific test: {test_path}")
    
    test_dir = Path(__file__).parent
    
    if runner == "pytest":
        cmd = [sys.executable, "-m", "pytest", test_path]
        if verbose:
            cmd.extend(["-v", "-s"])
    else:
        # unittest用
        # test_path を モジュール形式に変換
        module_path = test_path.replace("/", ".").replace(".py", "")
        cmd = [sys.executable, "-m", "unittest", module_path]
        if verbose:
            cmd.append("-v")
    
    try:
        result = subprocess.run(cmd, cwd=test_dir.parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Chigemotsu Test Runner")
    parser.add_argument(
        "--type", "-t",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--runner", "-r",
        choices=["unittest", "pytest", "both"],
        default="pytest",
        help="Test runner to use"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run with coverage (pytest only)"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check test dependencies"
    )
    parser.add_argument(
        "--specific", "-s",
        help="Run specific test file or method"
    )
    parser.add_argument(
        "--no-deps-check",
        action="store_true",
        help="Skip dependency check"
    )
    
    args = parser.parse_args()
    
    # 依存関係チェック
    if not args.no_deps_check and not args.check_deps:
        if not check_dependencies():
            print("\n💡 Use --no-deps-check to skip dependency check")
            sys.exit(1)
    
    if args.check_deps:
        check_dependencies()
        return
    
    # 特定のテストを実行
    if args.specific:
        success = run_specific_test(args.specific, args.runner, args.verbose)
        sys.exit(0 if success else 1)
    
    # テストタイプの正規化
    test_type = None if args.type == "all" else args.type
    
    success = True
    
    # テストランナーを実行
    if args.runner == "unittest":
        success = run_unittest_tests(test_type, args.verbose)
    elif args.runner == "pytest":
        success = run_pytest_tests(test_type, args.verbose, args.coverage)
    elif args.runner == "both":
        print("=" * 60)
        success1 = run_unittest_tests(test_type, args.verbose)
        print("=" * 60)
        success2 = run_pytest_tests(test_type, args.verbose, args.coverage)
        success = success1 and success2
    
    # 結果表示
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    # カバレッジレポートの表示
    if args.coverage and args.runner in ["pytest", "both"]:
        coverage_html = Path(__file__).parent / "coverage_html" / "index.html"
        if coverage_html.exists():
            print(f"\n📊 Coverage report: {coverage_html}")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
