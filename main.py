import os
import threading
import discord
from discord.ext import commands
from flask import Flask, jsonify
import logging
import asyncio
# randomモジュールは不要になったため削除

# ログ設定: Botの動作確認のためINFOレベルも表示
logging.basicConfig(level=logging.INFO)

# --- KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
# サーバー管理コマンドのために必要なインテントを設定
intents = discord.Intents.default()
intents.guilds = True
intents.members = True          # kick/banコマンドのために必要
intents.message_content = True  # !コマンドの読み取りのために必要

# 🚨 Prefixを '!' に設定
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing. Please set the environment variable.")

except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 🛠️ 管理コマンド ---
# ----------------------------------------------------

@bot.command(name="ping", help="Botのレイテンシを表示します。")
async def ping(ctx):
    # Botのレイテンシ（応答速度）を計算して送信
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! 応答速度: {latency_ms}ms")

@bot.command(name="kick", help="指定したメンバーをサーバーからキックします。")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="理由なし"):
    """メンバーをキックするコマンド"""
    if member.id == ctx.author.id:
        await ctx.send("自分自身をキックすることはできません。")
        return
    
    try:
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.display_name} をキックしました。理由: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ Botにメンバーをキックする権限がありません。Botのロールを上位にしてください。")
    except Exception as e:
        await ctx.send(f"❌ キック中にエラーが発生しました: {e}")

@kick.error
async def kick_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行するには「メンバーをキック」権限が必要です。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 使用法: `!kick [ユーザーメンションまたはID] [理由 (任意)]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")

@bot.command(name="ban", help="指定したメンバーをサーバーから追放（BAN）します。")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="理由なし"):
    """メンバーをBANするコマンド"""
    if member.id == ctx.author.id:
        await ctx.send("自分自身をBANすることはできません。")
        return
        
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ {member.display_name} をBANしました。理由: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ BotにメンバーをBANする権限がありません。Botのロールを上位にしてください。")
    except Exception as e:
        await ctx.send(f"❌ BAN中にエラーが発生しました: {e}")

@ban.error
async def ban_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行するには「メンバーをBAN」権限が必要です。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 使用法: `!ban [ユーザーメンションまたはID] [理由 (任意)]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="サーバーを管理中 | !help")
    )
    logging.info(f"Bot {bot.user} が起動し、管理を開始しました。")

@bot.event
async def on_message(message):
    """メッセージイベント"""
    if message.author.bot:
        return
        
    await bot.process_commands(message)


# ----------------------------------------------------
# --- KeepAlive Server (Render/Uptime Robot対応) ---
# ----------------------------------------------------

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    global DISCORD_BOT_TOKEN
    if not DISCORD_BOT_TOKEN:
        logging.error("Botの実行をスキップ: トークンが設定されていません。")
    else:
        logging.info("Discord Botを別スレッドで起動中...")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None) 
            
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効です。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

# Botを別スレッドで起動
bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """ヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Management Bot is running."
    else:
        return "Management Bot is starting up...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """冗長的なヘルスチェックエンドポイント"""
    return jsonify({"message": "Alive."}), 200
