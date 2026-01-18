# Makefile for chigemotsu monitor testing

.PHONY: help test test-unit test-integration test-coverage clean install-dev

help:  ## このヘルプを表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-dev:  ## 開発用パッケージをインストール
	uv pip install -e ".[dev,test]"

test: test-unit test-integration  ## 全てのテストを実行

test-unit:  ## ユニットテストのみ実行
	@echo "🧪 Running unit tests..."
	pytest tests/unit/ -v -m "unit" --tb=short

test-integration:  ## インテグレーションテストのみ実行
	@echo "🔗 Running integration tests..."
	pytest tests/integration/ -v -m "integration" --tb=short

test-all:  ## マーカーに関係なく全テスト実行
	@echo "🧪 Running all tests..."
	pytest tests/ -v --tb=short

test-coverage:  ## カバレッジ付きでテスト実行
	@echo "📊 Running tests with coverage..."
	pytest tests/ -v --cov=scripts --cov-report=html --cov-report=term-missing

test-fast:  ## 高速テスト（slowマーカーを除外）
	@echo "⚡ Running fast tests only..."
	pytest tests/ -v -m "not slow" --tb=short

test-slow:  ## 低速テストのみ実行
	@echo "🐌 Running slow tests..."
	pytest tests/ -v -m "slow" --tb=short

test-watch:  ## ファイル変更時に自動でテスト実行
	@echo "👀 Watching for file changes..."
	pytest-watch tests/ -- -v --tb=short

test-parallel:  ## 並列テスト実行（pytest-xdist使用）
	@echo "🚀 Running tests in parallel..."
	pytest tests/ -v -n auto --tb=short

test-debug:  ## デバッグモードでテスト実行
	@echo "🐛 Running tests in debug mode..."
	pytest tests/ -v -s --tb=long --pdb

lint:  ## コードの静的解析
	@echo "🔍 Running linters..."
	black --check scripts/
	flake8 scripts/
	mypy scripts/

format:  ## コードフォーマット
	@echo "💄 Formatting code..."
	black scripts/
	isort scripts/

clean:  ## テスト関連の一時ファイルを削除
	@echo "🧹 Cleaning up..."
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# 特定のテストファイル実行用のパターン
test-file-%:  ## 特定のテストファイルを実行 (例: make test-file-integrated_detection)
	pytest tests/unit/test_$*.py -v --tb=short

test-integration-file-%:  ## 特定のインテグレーションテストファイルを実行
	pytest tests/integration/test_$*.py -v --tb=short

# CI/CD用
ci-test:  ## CI環境用テスト（並列、カバレッジ付き）
	@echo "🤖 Running CI tests..."
	pytest tests/ -v --cov=scripts --cov-report=xml --cov-report=term -n auto

# レポート生成
coverage-report:  ## HTMLカバレッジレポートを生成
	@echo "📈 Generating coverage report..."
	pytest tests/ --cov=scripts --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# デバッグ用
test-info:  ## テスト環境情報を表示
	@echo "📋 Test environment info:"
	@echo "Python version: $$(python --version)"
	@echo "Pytest version: $$(pytest --version)"
	@echo "Current directory: $$(pwd)"
	@echo "Available test files:"
	@find tests/ -name "test_*.py" -type f | sed 's/^/  /'
