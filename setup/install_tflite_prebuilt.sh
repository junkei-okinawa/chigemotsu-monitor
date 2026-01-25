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

# ローカルの事前ビルド済み TensorFlow Lite Runtime アーカイブ
# - ファイル名: tflite_micro_runtime_rpiv6.tar.gz
# - 期待される配置場所: プロジェクトルート直下（${PROJECT_ROOT}/tflite_micro_runtime_rpiv6.tar.gz）
# - 期待される内部構造:
#     アーカイブ直下に tflite_micro_runtime/ ディレクトリが存在すること。
#     (例: tar -tf ファイル名 -> tflite_micro_runtime/...)
# - 用途:
#     - Raspberry Pi Zero (armv6l) 向けに別環境でビルドしたランタイムを、
#       ネットワーク不要で素早くインストールするためのローカルキャッシュとして利用します。
# - 任意のファイルです:
#     - このファイルが存在しない場合、またはチェックサム検証に失敗した場合は、
#       スクリプトは自動的にリモートから公式配布物をダウンロードします。
# - 更新方法:
#     - 新しいアーカイブを作成または取得した場合は、対応する SHA256 を計算し、
#       LOCAL_SHA256 をその値に更新してください。
#     - 同様に、リモート配布物を更新した場合は REMOTE_SHA256 も更新してください。
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
        TAR_ERR_LOG="${WORK_DIR}/tar_extract_local.err"
        if ! tar -xzf "$LOCAL_ARCHIVE" -C "${WORK_DIR}/extracted" 2> "${TAR_ERR_LOG}"; then
            echo "⚠️  警告: ローカルパッケージの展開に失敗しました。ダウンロードを試行します。"
            if [ -s "${TAR_ERR_LOG}" ]; then
                echo "    詳細 (tar エラー):" >&2
                cat "${TAR_ERR_LOG}" >&2
            fi
            rm -f "${TAR_ERR_LOG}"
            rm -rf "${WORK_DIR}/extracted"
            DOWNLOADED=false
        else
            rm -f "${TAR_ERR_LOG}"
            # 構造の簡易検証
            if [ -d "${WORK_DIR}/extracted/tflite_micro_runtime" ] || [ -d "${WORK_DIR}/extracted/tflite_runtime" ]; then
                DOWNLOADED=true
                PACKAGE_FILE="$LOCAL_ARCHIVE"
            else
                echo "⚠️  警告: ローカルパッケージの構造が不正です（期待されるディレクトリが見つかりません）。ダウンロードを試行します。"
                rm -rf "${WORK_DIR}/extracted"
                DOWNLOADED=false
            fi
        fi
    else
        # verify_checksum が失敗した場合、チェックサムツールの有無を確認する
        if ! command -v shasum >/dev/null 2>&1 && ! command -v sha256sum >/dev/null 2>&1; then
            echo "⚠️  重要: チェックサム検証ツール (shasum / sha256sum) が見つかりません。"
            echo "          この環境ではローカルアーカイブの整合性検証ができないため、セキュリティ保証が弱くなります。"
            echo "          必要に応じてこれらのツールをインストールしてから再実行してください。"
        fi
        echo "⚠️  警告: ローカルパッケージのチェックサムが一致しない、または検証に失敗しました。ダウンロードを試行します。"
    fi
fi

if [ "$DOWNLOADED" = false ]; then
    echo "リモートパッケージのダウンロードを試行します..."
    
    # GitHubリポジトリからTensorFlow Lite Runtime の軽量版をダウンロード
    # セキュリティのため特定のコミットハッシュにピン留め
    # Commit: de1e21b5f2d95e459b1f705994190e6f38978e96 - tflite_micro_runtime 1.2.2 (cp39, linux_armv6l)
    # Commit ページ: https://github.com/charlie2951/tflite_micro_rpi0/commit/de1e21b5f2d95e459b1f705994190e6f38978e96
    #   - 上記リンク先でコミット日時や変更内容を確認できます。
    #   - 新しいバージョンを使用する場合の手順:
    #       1. リポジトリ (https://github.com/charlie2951/tflite_micro_rpi0) で目的のコミットまたはリリースを選択
    #       2. 対応する .whl ファイル名 (バージョン / Python / アーキテクチャ) を確認
    #       3. 下記 URL 中のコミットハッシュおよび .whl ファイル名を更新
    #       4. REMOTE_SHA256 などのチェックサムを新しい .whl に合わせて更新
    #       5. このコメントに新しいコミットハッシュ / 用途 / 更新理由を追記
    WHEEL_URL="https://github.com/charlie2951/tflite_micro_rpi0/raw/de1e21b5f2d95e459b1f705994190e6f38978e96/tflite_micro_runtime-1.2.2-cp39-cp39-linux_armv6l.whl"
    WHEEL_FILENAME=$(basename "$WHEEL_URL")
    WHEEL_FULLPATH="${WORK_DIR}/${WHEEL_FILENAME}"

    # wgetまたはcurlでダウンロード（詳細ログ付き）
    if command -v wget >/dev/null 2>&1; then
        echo "wgetを使用してダウンロード中..."
        if wget --timeout=30 --tries=2 "$WHEEL_URL" -O "$WHEEL_FULLPATH"; then
            if [ -f "$WHEEL_FULLPATH" ] && [ -s "$WHEEL_FULLPATH" ]; then
                # チェックサム検証
                if verify_checksum "$REMOTE_SHA256" "$WHEEL_FULLPATH"; then
                    echo "✓ ダウンロード成功およびチェックサム検証に成功: $(ls -lh "$WHEEL_FULLPATH")"
                    DOWNLOADED=true
                    PACKAGE_FILE="$WHEEL_FULLPATH"
                else
                    echo "❌ エラー: ダウンロードされたファイルのチェックサムが一致しません"
                    rm -f "$WHEEL_FULLPATH"
                fi
            else
                echo "❌ ファイルが空またはダウンロードに失敗"
                rm -f "$WHEEL_FULLPATH"
            fi
        fi
    elif command -v curl >/dev/null 2>&1; then
        echo "curlを使用してダウンロード中..."
        # -f/--fail オプションを追加して HTTP エラー時に非ゼロステータスを返すようにする
        if curl --connect-timeout 30 --max-time 300 -f -L "$WHEEL_URL" -o "$WHEEL_FULLPATH"; then
            if [ -f "$WHEEL_FULLPATH" ] && [ -s "$WHEEL_FULLPATH" ]; then
                # チェックサム検証
                if verify_checksum "$REMOTE_SHA256" "$WHEEL_FULLPATH"; then
                    echo "✓ ダウンロード成功およびチェックサム検証に成功: $(ls -lh "$WHEEL_FULLPATH")"
                    DOWNLOADED=true
                    PACKAGE_FILE="$WHEEL_FULLPATH"
                else
                    echo "❌ エラー: ダウンロードされたファイルのチェックサムが一致しません"
                    rm -f "$WHEEL_FULLPATH"
                fi
            else
                echo "❌ ファイルが空またはダウンロードに失敗"
                rm -f "$WHEEL_FULLPATH"
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
    echo "wheel を安全に展開中..."
    if ! python3 - "$PACKAGE_FILE" "${WORK_DIR}/extracted" << 'PY'; then
import os
import sys
import zipfile

def is_within_directory(directory: str, target: str) -> bool:
    directory = os.path.realpath(directory)
    target = os.path.realpath(target)
    try:
        return os.path.commonpath([directory, target]) == directory
    except ValueError:
        return False

def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: safe_extract_wheel.py <wheel_path> <extract_dir>", file=sys.stderr)
        return 1

    wheel_path = sys.argv[1]
    extract_dir = sys.argv[2]

    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(wheel_path, "r") as zf:
            for member in zf.infolist():
                member_name = member.filename
                # Construct the destination path for this member
                dest_path = os.path.join(extract_dir, member_name)
                if not is_within_directory(extract_dir, dest_path):
                    print(f"Error: Unsafe path detected in wheel: {member_name}", file=sys.stderr)
                    return 1
            # All paths are safe; perform extraction
            zf.extractall(path=extract_dir)
    except Exception as e:
        print(f"Error: Failed to extract wheel: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
PY
    then
        echo "Error: wheel の展開に失敗しました: $PACKAGE_FILE"
        exit 1
    fi

    # 展開結果のディレクトリが存在し、空でないことを確認
    if [ ! -d "${WORK_DIR}/extracted" ] || [ -z "$(ls -A "${WORK_DIR}/extracted" 2>/dev/null)" ]; then
        echo "Error: wheel の展開結果が見つからないか空です: ${WORK_DIR}/extracted"
        exit 1
    fi
fi
        
# 解凍されたファイル構造を確認
echo "解凍されたファイル構造:"
find "${WORK_DIR}/extracted" -type d -name "*tflite*" | head -10
find "${WORK_DIR}/extracted" -name "*.py" | head -5
find "${WORK_DIR}/extracted" -name "*.so" | head -5
echo "全ディレクトリ構造:"
ls -la "${WORK_DIR}/extracted"

# Pythonライブラリパスを取得
PYTHON_LIB_PATH=$(python3 -c "import site; paths = site.getsitepackages(); print(paths[0] if paths else '')" 2>/dev/null || echo "")

# 取得したパスの妥当性を確認
if [ -z "$PYTHON_LIB_PATH" ]; then
    echo "Error: Python ライブラリパスを取得できませんでした。Python 環境を確認してください。"
    exit 1
fi

# 想定外のパスへの書き込みを防ぐため、絶対パスかつ親ディレクトリが書き込み可能かチェック
if [[ "$PYTHON_LIB_PATH" != /* ]]; then
    echo "Error: 予期しない Python ライブラリパスが検出されました (絶対パスではありません): $PYTHON_LIB_PATH"
    echo "       Python 環境が正しく構成されているか確認してください。"
    exit 1
fi
PARENT_DIR=$(dirname "$PYTHON_LIB_PATH")
if [ ! -d "$PARENT_DIR" ] || [ ! -w "$PARENT_DIR" ]; then
    echo "Error: Python ライブラリパスの親ディレクトリに書き込めません: $PARENT_DIR"
    echo "       権限または Python 環境を確認してください。"
    exit 1
fi

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
    # サブシェル内で nullglob を有効にして、マッチしない場合にループをスキップするようにする
    # 見つかった場合は exit 0 で成功を返し、親シェルで FOUND_LIB を true にする
    if (
        shopt -s nullglob
        for data_dir in "${WORK_DIR}/extracted"/*.data; do
            if [ -d "$data_dir/purelib" ]; then
                for lib_dir in "$data_dir/purelib"/*; do
                    if [ -d "$lib_dir" ] && [[ "$(basename "$lib_dir")" == *"tflite"* ]]; then
                        LIB_NAME=$(basename "$lib_dir")
                        cp -r "$lib_dir" "$PYTHON_LIB_PATH/"
                        echo "✓ $LIB_NAME ライブラリを手動インストールしました (purelib経由)"
                        exit 0
                    fi
                done
            fi
        done
        exit 1
    ); then
        FOUND_LIB=true
    fi
fi

if [ "$FOUND_LIB" = true ]; then
    # インストールしたファイルのパーミッションを適正化（ディレクトリは実行可能、ファイルは読み取り専用）
    find "$PYTHON_LIB_PATH"/tflite* -type d -exec chmod 755 {} +
    find "$PYTHON_LIB_PATH"/tflite* -type f -exec chmod 644 {} +
    echo "✓ インストールしたファイルのパーミッションを適正化しました"
else
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
