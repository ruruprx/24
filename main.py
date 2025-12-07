import os
import threading
import discord
from discord.ext import commands
from discord import app_commands # ★ 追加: スラッシュコマンド関連のインポート
from flask import Flask, jsonify
import logging
import asyncio

# ログ設定: Botの動作確認のためINFOレベルも表示
logging.basicConfig(level=logging.INFO)

# --- KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True          
intents.message_content = True 

# Prefixを '!' に設定
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの設定 (省略)
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing.")
except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 🛠️ 管理コマンド (プレフィックスとスラッシュ) ---
# ----------------------------------------------------

# ★ プレフィックスコマンド: !ping
@bot.command(name="ping", help="Botのレイテンシを表示します。")
async def ping_prefix(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! 応答速度: {latency_ms}ms")


# ★ スラッシュコマンド: /ping
@bot.tree.command(name="ping", description="Botのレイテンシを表示します。")
async def ping_slash(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 応答速度: {latency_ms}ms", ephemeral=True)


# プレフィックスコマンド: !kick (変更なし)
@bot.command(name="kick", help="指定したメンバーをサーバーからキックします。")
@commands.has_permissions(kick_members=True)
async def kick_prefix(ctx, member: discord.Member, *, reason="理由なし"):
    # ... (kickコマンドのロジックは変更なし)
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

@kick_prefix.error
async def kick_error_prefix(ctx, error):
    # ... (エラー処理は変更なし)
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行するには「メンバーをキック」権限が必要です。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 使用法: `!kick [ユーザーメンションまたはID] [理由 (任意)]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")

# ★ スラッシュコマンド: /kick
@bot.tree.command(name="kick", description="指定したメンバーをサーバーからキックします。")
@app_commands.describe(member="キックするユーザー", reason="キックする理由")
@app_commands.default_permissions(kick_members=True) # デフォルトで権限が必要であることを指定
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = '理由なし'):
    # 権限チェック (スラッシュコマンドではデコレータだけでは不十分な場合があるため、明示的に確認)
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ このコマンドを実行するには「メンバーをキック」権限が必要です。", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("自分自身をキックすることはできません。", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} をキックしました。理由: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Botにメンバーをキックする権限がありません。Botのロールを上位にしてください。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ キック中にエラーが発生しました: {e}", ephemeral=True)

# プレフィックスコマンド: !ban, !ban.error (省略しますが、前回のコードから変更なし)
# ... (banコマンドのロジックは前回のコードと同じ)

# ★ スラッシュコマンド: /ban (スラッシュコマンドのみ追加)
@bot.tree.command(name="ban", description="指定したメンバーをサーバーから追放（BAN）します。")
@app_commands.describe(member="BANするユーザー", reason="BANする理由")
@app_commands.default_permissions(ban_members=True) # デフォルトで権限が必要であることを指定
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = '理由なし'):
    # 権限チェック
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ このコマンドを実行するには「メンバーをBAN」権限が必要です。", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("自分自身をBANすることはできません。", ephemeral=True)
        return

    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} をBANしました。理由: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ BotにメンバーをBANする権限がありません。Botのロールを上位にしてください。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ BAN中にエラーが発生しました: {e}", ephemeral=True)


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    # ★ 修正点: スラッシュコマンドをDiscordに同期する
    try:
        synced = await bot.tree.sync()
        logging.info(f"スラッシュコマンドを同期しました。コマンド数: {len(synced)}")
    except Exception as e:
        logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")
        
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="サーバーを管理中 | /help または !help")
    )
    logging.info(f"Bot {bot.user} が起動し、管理を開始しました。")

@bot.event
async def on_message(message):
    # ... (on_messageは変更なし)
    if message.author.bot:
        return
        
    await bot.process_commands(message)

# ----------------------------------------------------
# --- KeepAlive Server (省略しますが、前回のコードと同じ) ---
# ----------------------------------------------------
# ... (start_bot関数、bot_thread、@app.route("/")、@app.route("/keep_alive") は前回のコードと同じ)
# ----------------------------------------------------

def start_bot():
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

bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    if bot.is_ready():
        return "Management Bot is running."
    else:
        return "Management Bot is starting up...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    return jsonify({"message": "Alive."}), 200
