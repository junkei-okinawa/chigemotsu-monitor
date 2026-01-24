# LINE認証情報のセットアップ

## 概要

このガイドでは、LINE Messaging APIを使用して画像通知を送信するための設定方法を説明します。

## 事前準備

- LINEアカウント
- 通知を送信したいLINEグループまたは個人チャット

## セットアップ手順

### ステップ1：LINE公式アカウントの作成

1. **LINE Official Account Managerにアクセス**:
   - [LINE Official Account Manager](https://manager.line.biz/) にアクセス
   - LINEアカウントでログイン

2. **新規アカウント作成**:
   - 「アカウント」タブ → 「作成」をクリック
   - 以下の設定で作成:
     - アカウント名：お好み（例：「監視通知Bot」など）
     - メールアドレス：任意
     - 業種：個人
     - 運用目的：その他
     - 主な使い方：メッセージ配信用

### ステップ2：Messaging APIの有効化

1. **Messaging API設定**:
   - LINE Official Account Managerで作成したアカウントにログイン
   - 右上の「設定」をクリック
   - 左メニューの「Messaging API」を選択
   - 「Messaging APIを利用する」をクリック

2. **プロバイダー設定**:
   - 新規プロバイダーを作成またはExistingプロバイダーを選択
   - 「同意する」をクリック
   - プライバシーポリシー、利用規約は空欄のまま「OK」をクリック

### ステップ3：アクセストークンとChannel Secretの取得

1. **LINE Developersでの設定**:
   - [LINE Developers](https://developers.line.biz/) にアクセス
   - 「コンソールにログイン」をクリック
   - 作成したプロバイダーとアカウントを選択

2. **認証情報の取得**:
   - 「Messaging API設定」タブをクリック
   - **Channel Secret**をコピー（後で使用）
   - **チャンネルアクセストークン**を発行してコピー（後で使用）

### ステップ4：認証情報ファイルの作成

1. **認証情報ファイルを作成**:
```bash
cp config/line_credentials.json.sample config/line_credentials.json
```

2. **line_access_token を入力**:
line_user_id については後述します。
```diff
{
+  "line_access_token": "your_line_bot_access_token",
  "line_user_id": "your_line_user_id_or_group_id"
}
```

### ステップ5：送信先の設定（個人またはグループ）

#### 個人チャットの場合

1. **User IDの取得**:
   - LINE公式アカウントを友だち追加
   - 何かメッセージを送信
   - LINE Developersコンソールの「Messaging API設定」でWebhookを一時的に設定してUser IDを取得

#### グループチャットの場合

1. **グループ設定の許可**:
   - LINE Developersコンソールで「LINE公式アカウント機能」→「グループトーク・複数人トークへの参加を許可する」を有効化

2. **Group IDの取得方法**:
   
   **方法A: Google Apps Scriptを使用（推奨）**
   
   以下のスクリプトをGoogle Apps Scriptで作成し、一時的にWebhookとして設定：

   ```javascript
   // アクセストークンを設定
   const ACCESS_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN';

   function doPost(e) {
     try {
       var json = JSON.parse(e.postData.contents);
       
       if (json.events && json.events.length > 0) {
         var event = json.events[0];
         var source = event.source;
         
         // グループからのメッセージの場合
         if (source.type === 'group' && source.groupId) {
           var groupId = source.groupId;
           var replyToken = event.replyToken;
           var replyMessage = 'Group ID: ' + groupId;
           
           // 返信
           var url = 'https://api.line.me/v2/bot/message/reply';
           var payload = JSON.stringify({
             "replyToken": replyToken,
             "messages": [{
               "type": "text",
               "text": replyMessage
             }]
           });
           
           var options = {
             "method": "post",
             "contentType": "application/json",
             "headers": {
               "Authorization": "Bearer " + ACCESS_TOKEN
             },
             "payload": payload
           };
           
           UrlFetchApp.fetch(url, options);
         }
       }
     } catch (error) {
       Logger.log("Error: " + error);
     }
     return ContentService.createTextOutput("OK");
   }
   ```

   **方法B: LINE Bot設計図を使用**
   
   - [LINE Bot設計図](https://www.linebotdesigner.com/) などのツールを使用してGroup IDを取得

3. **グループにBotを招待**:
   - 対象のLINEグループに作成した公式アカウントを招待
   - グループ内で何かメッセージを送信してGroup IDを取得

### ステップ6：設定ファイルの更新

取得したUser IDまたはGroup IDを`config.json`に設定：

```diff
{
  "line_access_token": "your_line_bot_access_token",
+  "line_user_id": "your_line_user_id_or_group_id"
}
```

## セキュリティ

- `line_credentials.json` ファイルは `.gitignore` に追加済み
- ファイル権限を適切に設定:
```bash
chmod 600 config/line_credentials.json
```

## 設定の確認

```bash
# LINE接続テスト
python3 scripts/line_image_notifier.py --test

# 設定ファイル確認
python3 -c "
from production.scripts.line_image_notifier import LineImageNotifier
notifier = LineImageNotifier()
print('✅ LINE設定が正常に読み込まれました')
"
```

## トラブルシューティング

### よくある問題

1. **403 Forbidden エラー**:
   - Channel Access Tokenが正しく設定されているか確認
   - Messaging APIが有効化されているか確認

2. **メッセージが届かない**:
   - User ID/Group IDが正しいか確認
   - 公式アカウントがブロックされていないか確認
   - グループの場合、Botがグループに招待されているか確認

3. **Group IDが取得できない**:
   - グループトークへの参加が許可されているか確認
   - Webhookが正しく設定されているか確認

### デバッグ方法

```bash
# ログレベルをDEBUGに変更
# config.jsonのlogging_levelを"DEBUG"に設定してテスト実行
```

## 参考資料

- [LINE Messaging API Documentation](https://developers.line.biz/ja/docs/messaging-api/)
- [LINE Official Account Manager](https://manager.line.biz/)
- [LINE Developers Console](https://developers.line.biz/)
- [LINEグループID取得方法の詳細](https://sananeblog.com/line-group-id/)
