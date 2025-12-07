import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, utils 
from flask import Flask, jsonify
import logging
import asyncio
import random 

# ログ設定
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

# 🚨 グローバルストレージ (Botが再起動するとリセットされます)
guild_log_channels = {}

# 環境変数からの設定 (省略)
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing.")
except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 🛠️ ログ設定スラッシュコマンド (修正部分) ---
# ----------------------------------------------------

# ★ 修正: app_commands.Groupを継承してクラスとしてグループを定義する
class JoinLog(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="joinlog", description="入室/退室ログチャンネルを設定します。")
        self.bot = bot # Botインスタンスを保持

    @app_commands.command(name="set", description="入室・退室ログを送信するチャンネルを設定します。")
    @app_commands.describe(channel="ログを送信するチャンネル")
    @app_commands.default_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """入室/退室ログの送信先を設定する"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドを実行するには「管理者」権限が必要です。", ephemeral=True)
            return

        guild_log_channels[interaction.guild_id] = channel.id
        await interaction.response.send_message(f"✅ 入室・退室ログの送信先を {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="disable", description="入室・退室ログの送信を無効にします。")
    @app_commands.default_permissions(administrator=True)
    async def disable_log_channel(self, interaction: discord.Interaction):
        """入室/退室ログの送信を無効にする"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドを実行するには「管理者」権限が必要です。", ephemeral=True)
            return

        if interaction.guild_id in guild_log_channels:
            del guild_log_channels[interaction.guild_id]
            await interaction.response.send_message("✅ 入室・退室ログの送信を無効にしました。", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 現在、入室・退室ログは設定されていません。", ephemeral=True)


# ----------------------------------------------------
# --- 🤝 イベントリスナー (入室/退室ログ) ---
# ----------------------------------------------------

@bot.event
async def on_member_join(member):
    """メンバーがサーバーに参加したときに実行"""
    guild_id = member.guild.id
    if guild_id in guild_log_channels:
        channel_id = guild_log_channels[guild_id]
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="➡️ メンバー入室",
                description=f"{member.mention} ({member.id}) がサーバーに参加しました。",
                color=discord.Color.green(),
                timestamp=utils.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="現在のメンバー数", value=member.guild.member_count, inline=True)
            
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logging.error(f"ギルド {guild_id} のログチャンネルにメッセージを送信する権限がありません。")

@bot.event
async def on_member_remove(member):
    """メンバーがサーバーを退出したときに実行"""
    guild_id = member.guild.id
    if guild_id in guild_log_channels:
        channel_id = guild_log_channels[guild_id]
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="⬅️ メンバー退室",
                description=f"{member.mention} ({member.id}) がサーバーを退出しました。",
                color=discord.Color.red(),
                timestamp=utils.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="現在のメンバー数", value=member.guild.member_count - 1, inline=True) 
            
            if member.joined_at:
                embed.add_field(name="参加日時", value=utils.format_dt(member.joined_at, 'F'), inline=False)
            
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logging.error(f"ギルド {guild_id} のログチャンネルにメッセージを送信する権限がありません。")

# ----------------------------------------------------
# --- 🛠️ 管理コマンド (プレフィックスとスラッシュ) ---
# ----------------------------------------------------

# プレフィックスコマンド: !ping
@bot.command(name="ping", help="Botのレイテンシを表示します。")
async def ping_prefix(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! 応答速度: {latency_ms}ms")

# スラッシュコマンド: /ping
@bot.tree.command(name="ping", description="Botのレイテンシを表示します。")
async def ping_slash(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 応答速度: {latency_ms}ms", ephemeral=True)


# プレフィックスコマンド: !kick, !ban, スラッシュコマンド: /kick, /ban (省略しますが、前回のコードと同じ)
# ...

# プレフィックスコマンド: !kick
@bot.command(name="kick", help="指定したメンバーをサーバーからキックします。")
@commands.has_permissions(kick_members=True)
async def kick_prefix(ctx, member: discord.Member, *, reason="理由なし"):
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
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行するには「メンバーをキック」権限が必要です。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 使用法: `!kick [ユーザーメンションまたはID] [理由 (任意)]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")

# スラッシュコマンド: /kick
@bot.tree.command(name="kick", description="指定したメンバーをサーバーからキックします。")
@app_commands.describe(member="キックするユーザー", reason="キックする理由")
@app_commands.default_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = '理由なし'):
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

# プレフィックスコマンド: !ban
@bot.command(name="ban", help="指定したメンバーをサーバーから追放（BAN）します。")
@commands.has_permissions(ban_members=True)
async def ban_prefix(ctx, member: discord.Member, *, reason="理由なし"):
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

@ban_prefix.error
async def ban_error_prefix(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ このコマンドを実行するには「メンバーをBAN」権限が必要です。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 使用法: `!ban [ユーザーメンションまたはID] [理由 (任意)]`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 指定されたユーザーが見つかりません。")

# スラッシュコマンド: /ban
@bot.tree.command(name="ban", description="指定したメンバーをサーバーから追放（BAN）します。")
@app_commands.describe(member="BANするユーザー", reason="BANする理由")
@app_commands.default_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = '理由なし'):
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
        await interaction.response.send_message("❌ BotにメンバーをBANする権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ BAN中にエラーが発生しました: {e}", ephemeral=True)


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    # ★ 修正: グループクラスをBotに組み込む
    bot.tree.add_command(JoinLog(bot))
    
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
    """メッセージイベント"""
    if message.author.bot:
        return
        
    await bot.process_commands(message)


# ----------------------------------------------------
# --- KeepAlive Server ---
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
