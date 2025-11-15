import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- Load .env ---
load_dotenv()

# --- KeepAlive Server for Render & UptimeRobot ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def keep_alive():
    def run():
        port = int(os.environ.get("PORT", 5000))  # Render uses PORT env var
        app.run(host="0.0.0.0", port=port)
    threading.Thread(target=run).start()

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# --- Dangerous Command: Delete All Channels ---
@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except Exception:
            pass
    await ctx.send("サーバー内のチャンネルを全削除しました！")

# --- Main Execution ---
if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        keep_alive()  # Start keep-alive server
        bot.run(TOKEN)

