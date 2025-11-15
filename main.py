import os
import threading
from flask import Flask
import discord
from discord.ext import commands

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
    # host='0.0.0.0'で外部からのアクセスを許可
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

# --- 招待リンク生成コマンド ---
@bot.command()
@commands.has_permissions(manage_guild=True) # サーバー管理権限が必要
async def ruru(ctx):
    """実行されたチャンネルに招待リンクを生成して送信する"""
    try:
        # 招待リンクを生成（期限なし・使用回数無制限）
        # create_invite()にはチャンネルの作成権限が必要です
        invite = await ctx.channel.create_invite(max_age=0, max_uses=0)

        await ctx.send(f"招待リンクを作成したよ！\n{invite.url}")
    except discord.Forbidden:
        # ボットに招待を作成する権限がない場合の処理
        await ctx.send("エラー: ボットに招待リンクを作成する権限がありません。権限設定を確認してください。")
    except Exception as e:
        await ctx.send(f"招待リンクの作成中に予期せぬエラーが発生しました: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    # 環境変数からトークンを直接取得
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        keep_alive()  # Keep-alive サーバーを起動
        bot.run(TOKEN) # Discord ボットを起動
