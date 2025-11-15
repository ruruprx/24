import os
import threading
from flask import Flask
import discord
from discord.ext import commands
# ⚠️ 注意: Renderでは環境変数にトークンを設定するため、
# 以下の dotenv の行は削除しました。
# from dotenv import load_dotenv 
# load_dotenv()

# --- KeepAlive Server for Render & UptimeRobot ---
app = Flask(__name__)

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答"""
    return "Bot is running!"

def run_flask():
    """Flaskサーバーを別スレッドで起動する"""
    # Renderが設定する環境変数 'PORT' を使用する
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Webサーバーをメインのボット処理と並行して起動する"""
    t = threading.Thread(target=run_flask)
    t.start()
    print("Keep-alive server started.")

# --- Discord Bot Setup ---
# プレフィックスコマンドを使うため、Message Content Intentが必要です
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# --- ⚠️ チャンネル削除コマンド ---
# 警告: このコマンドはサーバー内のチャンネルをすべて削除します。
@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):
    # すべてのチャンネルを削除するロジック
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except Exception:
            # 権限不足などで削除できなかったチャンネルがあっても処理を継続
            pass
            
    # このコマンドは危険な操作なので、実行したことを明確に伝えます
    await ctx.send("サーバー内のチャンネルを全削除しました！")

# --- Main Execution ---
if __name__ == "__main__":
    # 環境変数からトークンを直接取得
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        keep_alive()  # Keep-alive サーバーを起動
        bot.run(TOKEN) # Discord ボットを起動
