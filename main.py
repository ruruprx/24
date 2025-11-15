import os
import threading
import discord
from discord import app_commands
from flask import Flask

# --- Flask (Webサーバー) の設定 ---
app = Flask('')

# ヘルスチェック用のシンプルなルート
@app.route('/')
def home():
    # UptimeRobotからのアクセスに応答し、ボットが生きていることを示す
    return "Bot is running and keeping awake!"

def run_flask():
    """Flaskサーバーを別スレッドで起動する関数"""
    # Render.comの環境変数PORTが設定されていない場合は5000を使用
    port = os.environ.get('PORT', 5000) 
    print(f"Starting Flask server on port {port}...")
    # host='0.0.0.0'で外部からのアクセスを許可
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Flaskサーバーを起動し、ボットのメイン処理と並行して実行する"""
    t = threading.Thread(target=run_flask)
    t.start()
    print("Keep-alive server started.")

# --- Discord Bot の設定 ---
# Intentsの設定（必要な権限を有効にする）
intents = discord.Intents.default()
# スラッシュコマンドのみを使う場合は、メッセージ内容のIntentは不要なことが多いです。
# intents.message_content = True 

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # コマンドツリーの同期用
        self.tree = app_commands.CommandTree(self)

    # サーバーに参加した時などにスラッシュコマンドをDiscordに登録
    async def on_ready(self):
        await self.tree.sync()
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

# MyClientインスタンスを作成
client = MyClient(intents=intents)

# --- スラッシュコマンドの定義 ---
@client.tree.command(name="hello", description="ボットが挨拶します。")
async def hello_command(interaction: discord.Interaction):
    """/helloコマンドが実行された時の処理"""
    await interaction.response.send_message(f"こんにちは！ {interaction.user.display_name}さん。", ephemeral=False)

# --- メイン実行部分 ---
if __name__ == "__main__":
    # 1. 環境変数からトークンを取得
    # Render.comで設定した環境変数名に合わせてください
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        # 2. Webサーバーを別スレッドで起動
        keep_alive()
        
        # 3. Discordボットを起動
        client.run(TOKEN)
