# R2認証情報のセットアップ

## 設定方法

### r2_credentials.json ファイル

1. **認証情報ファイルを作成**:
```bash
cp production/config/r2_credentials.json.sample production/config/r2_credentials.json
```

2. **認証情報、公開URLを入力**:
公開URLは一度画像をアップロードするとメタデータ画面で確認できます。

```json
{
  "account_id": "0d5673ad0a870c80557a79daf50e68de",
  "access_key_id": "46d41fdddf5034f7d00207e99ec16c1d",
  "secret_access_key": "YOUR_ACTUAL_SECRET_ACCESS_KEY_HERE",
  "bucket_name": "chigemotsu-images",
  "public_url_base": "https://pub-xxxxx.r2.dev"
}
```

## セキュリティ

- `r2_credentials.json` ファイルは `.gitignore` に追加済み
- ファイル権限を適切に設定:
```bash
chmod 600 production/config/r2_credentials.json
```

## 設定の確認

```bash
# R2接続テスト
python3 production/scripts/r2_uploader.py --test

# 設定ファイル確認
python3 -c "
from production.scripts.r2_uploader import R2Uploader
uploader = R2Uploader()
print('✅ R2設定が正常に読み込まれました')
"
```

## 移行前の設定（従来形式）からの変更点

### 変更前 (config.json):
```json
{
  "r2": {
    "account_id": "...",
    "access_key_id": "...",
    "secret_access_key": "...",
    "bucket_name": "..."
  }
}
```

### 変更後 (config.json):
```json
{
  "r2": {
    "credentials_file": "./config/r2_credentials.json"
  }
}
```

認証情報は `r2_credentials.json` ファイルで管理されます。
