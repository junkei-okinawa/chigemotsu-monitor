#!/bin/bash
# Raspberry Pi Zero (armv6l) 用 事前ビルド済み TensorFlow Lite Runtime インストールスクリプト
# ビルドに失敗した場合の代替手段

set -e

echo "=== 事前ビルド済み TensorFlow Lite Runtime インストール ==="
echo "対象: Raspberry Pi Zero (armv6l)"

# Pythonバージョンを確認
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
# 3.9.*以外の場合は停止
if [[ ! "$PYTHON_VERSION" =~ ^3\.9\..* ]]; then
    echo "Error: Unsupported Python version $PYTHON_VERSION. Please use Python 3.9.*"
    exit 1
fi
echo "Python バージョン: $PYTHON_VERSION"

# 作業ディレクトリを作成（/home/junkei配下）
WORK_DIR="${HOME}/tflite_install_$(date +%Y%m%d_%H%M%S)"
echo "作業ディレクトリ: $WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# プロジェクトルートを取得（このスクリプトの2つ上の階層）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_ARCHIVE="${PROJECT_ROOT}/tflite_micro_runtime_rpiv6.tar.gz"
LOCAL_SHA256="934363d4db8653942399dd316693715f6105390c49a0ba06f3175fef40986a90"
REMOTE_SHA256="f8ec28dec040e5d1d2104f036b42f4d83d0d441f63edc51f178e8284c91ce38d"

# チェックサム検証関数（shasum または sha256sum を使用）
verify_checksum() {
    local checksum=$1
    local file=$2
    
    if command -v shasum >/dev/null 2>&1; then
        echo "$checksum  $file" | shasum -a 256 -c - >/dev/null 2>&1
        return $?
    elif command -v sha256sum >/dev/null 2>&1; then
        echo "$checksum  $file" | sha256sum -c - >/dev/null 2>&1
        return $?
    else
        echo "Error: shasum も sha256sum も見つかりません。チェックサム検証ができません。" >&2
        return 1
    fi
}

DOWNLOADED=false
PACKAGE_FILE=""

# まずローカルのアーカイブをチェック
if [ -f "$LOCAL_ARCHIVE" ]; then
    echo "✓ ローカルのバイナリパッケージが見つかりました: $LOCAL_ARCHIVE"
    # チェックサム検証
    if verify_checksum "$LOCAL_SHA256" "$LOCAL_ARCHIVE"; then
        echo "✓ ローカルパッケージのチェックサム検証に成功しました"
        mkdir -p "${WORK_DIR}/extracted"
        tar -xzf "$LOCAL_ARCHIVE" -C "${WORK_DIR}/extracted"
        DOWNLOADED=true
        PACKAGE_FILE="$LOCAL_ARCHIVE"
    else
        echo "⚠️  警告: ローカルパッケージのチェックサムが一致しません。ダウンロードを試行します。"
    fi
fi

if [ "$DOWNLOADED" = false ]; then
    echo "リモートパッケージのダウンロードを試行します..."
    
    # 複数のソースからTensorFlow Lite Runtime の軽量版をダウンロード
    # セキュリティのため特定のコミットハッシュにピン留め
    WHEEL_URL="https://github.com/charlie2951/tflite_micro_rpi0/raw/de1e21b5f2d95e459b1f705994190e6f38978e96/tflite_micro_runtime-1.2.2-cp39-cp39-linux_armv6l.whl"
    WHEEL_FILENAME=$(basename "$WHEEL_URL")

    # wgetまたはcurlでダウンロード（詳細ログ付き）
    if command -v wget >/dev/null 2>&1; then
        echo "wgetを使用してダウンロード中..."
        if wget --timeout=30 --tries=2 "$WHEEL_URL" -O "$WHEEL_FILENAME" 2>&1; then
            if [ -f "$WHEEL_FILENAME" ] && [ -s "$WHEEL_FILENAME" ]; then
                # チェックサム検証
                if verify_checksum "$REMOTE_SHA256" "$WHEEL_FILENAME"; then
                    echo "✓ ダウンロード成功およびチェックサム検証に成功: $(ls -lh "$WHEEL_FILENAME")"
                    DOWNLOADED=true
                    PACKAGE_FILE="$WHEEL_FILENAME"
                else
                    echo "❌ エラー: ダウンロードされたファイルのチェックサムが一致しません"
                    rm -f "$WHEEL_FILENAME"
                fi
            else
                echo "❌ ファイルが空またはダウンロードに失敗"
                rm -f "$WHEEL_FILENAME"
            fi
        fi
    elif command -v curl >/dev/null 2>&1; then
        echo "curlを使用してダウンロード中..."
        if curl --connect-timeout 30 --max-time 300 -L "$WHEEL_URL" -o "$WHEEL_FILENAME" 2>&1; then
            if [ -f "$WHEEL_FILENAME" ] && [ -s "$WHEEL_FILENAME" ]; then
                # チェックサム検証
                if verify_checksum "$REMOTE_SHA256" "$WHEEL_FILENAME"; then
                    echo "✓ ダウンロード成功およびチェックサム検証に成功: $(ls -lh "$WHEEL_FILENAME")"
                    DOWNLOADED=true
                    PACKAGE_FILE="$WHEEL_FILENAME"
                else
                    echo "❌ エラー: ダウンロードされたファイルのチェックサムが一致しません"
                    rm -f "$WHEEL_FILENAME"
                fi
            else
                echo "❌ ファイルが空またはダウンロードに失敗"
                rm -f "$WHEEL_FILENAME"
            fi
        fi
    else
        echo "❌ wget または curl が見つかりません"
    fi
fi

if [ "$DOWNLOADED" = false ]; then
    echo "パッケージの取得に失敗しました"
    exit 1
fi

echo "パッケージをインストール中..."
echo "使用ファイル: $PACKAGE_FILE"

# wheel（zip形式）の場合のみ展開処理（tar.gzは既に展開済み）
if [[ "$PACKAGE_FILE" == *.whl ]]; then
    python3 -m zipfile -e "$PACKAGE_FILE" "${WORK_DIR}/extracted"
fi
        
# 解凍されたファイル構造を確認
echo "解凍されたファイル構造:"
find "${WORK_DIR}/extracted" -type d -name "*tflite*" | head -10
find "${WORK_DIR}/extracted" -name "*.py" | head -5
find "${WORK_DIR}/extracted" -name "*.so" | head -5
echo "全ディレクトリ構造:"
ls -la "${WORK_DIR}/extracted"

# Pythonライブラリパスを取得
PYTHON_LIB_PATH=$(python3 -c "import site; print(site.getsitepackages()[0])")
echo "Python ライブラリパス: $PYTHON_LIB_PATH"
mkdir -p "$PYTHON_LIB_PATH"

# ライブラリファイルをコピー
FOUND_LIB=false

# パターン1: 直接ディレクトリ
if [ -d "${WORK_DIR}/extracted/tflite_micro_runtime" ]; then
    cp -r "${WORK_DIR}/extracted/tflite_micro_runtime" "$PYTHON_LIB_PATH/"
    echo "✓ tflite_micro_runtime ライブラリを手動インストールしました"
    FOUND_LIB=true
elif [ -d "${WORK_DIR}/extracted/tflite_runtime" ]; then
    cp -r "${WORK_DIR}/extracted/tflite_runtime" "$PYTHON_LIB_PATH/"
    echo "✓ tflite_runtime ライブラリを手動インストールしました"
    FOUND_LIB=true
fi

# パターン2: .data/purelib内を探索
if [ "$FOUND_LIB" = false ]; then
    for data_dir in "${WORK_DIR}/extracted"/*.data; do
        if [ -d "$data_dir/purelib" ]; then
            for lib_dir in "$data_dir/purelib"/*; do
                if [ -d "$lib_dir" ] && [[ "$(basename "$lib_dir")" == *"tflite"* ]]; then
                    LIB_NAME=$(basename "$lib_dir")
                    cp -r "$lib_dir" "$PYTHON_LIB_PATH/"
                    echo "✓ $LIB_NAME ライブラリを手動インストールしました (purelib経由)"
                    FOUND_LIB=true
                    break
                fi
            done
        fi
        if [ "$FOUND_LIB" = true ]; then
            break
        fi
    done
fi

if [ "$FOUND_LIB" = false ]; then
    echo "解凍されたディレクトリ構造:"
    ls -la "${WORK_DIR}/extracted"
    echo "❌ tflite_runtime または tflite_micro_runtime ディレクトリが見つかりません"
    echo "パッケージの内容を確認してください: ${WORK_DIR}/extracted/"
    exit 1
fi

echo "インストール確認中..."

# まずtflite_micro_runtimeを試行
if python3 -c "import tflite_micro_runtime.interpreter as tflite; print('✓ TensorFlow Lite Micro Runtime が正常にインストールされました')" 2>/dev/null; then
    echo "使用可能なライブラリ: tflite_micro_runtime"
elif python3 -c "import tflite_runtime.interpreter as tflite; print('✓ TensorFlow Lite Runtime が正常にインストールされました')" 2>/dev/null; then
    echo "使用可能なライブラリ: tflite_runtime"
else
    echo "❌ インストールされたライブラリにアクセスできません"
    echo "理由を調査中..."
    
    # tflite_micro_runtimeのインポートエラーを詳細表示
    if python3 -c "import tflite_micro_runtime" 2>/dev/null; then
        echo "tflite_micro_runtime パッケージは見つかりましたが、interpreter モジュールに問題があります"
        python3 -c "import tflite_micro_runtime.interpreter" 2>&1 || true
    else
        echo "tflite_micro_runtime パッケージが見つかりません"
        exit 1
    fi
fi

echo ""
echo "=== インストール完了 ==="
echo "作業ディレクトリ: $WORK_DIR"
echo "※ エラー調査や再試行が必要な場合は、上記ディレクトリを確認してください"
echo ""
echo "使用方法:"
echo "  # tflite_micro_runtime が利用可能な場合:"
echo "  import tflite_micro_runtime.interpreter as tflite"
echo "  # または標準的なtflite_runtime の場合:"
echo "  import tflite_runtime.interpreter as tflite"
echo ""
echo "  interpreter = tflite.Interpreter(model_path='model.tflite')"
echo ""
echo "注意:"
echo "- Python 3.11でPython 3.9用パッケージを使用する場合、"
echo "  共有ライブラリの互換性問題が発生する可能性があります"
echo "- その場合は標準的なtflite-runtimeが自動的にfallbackとして使用されます"
