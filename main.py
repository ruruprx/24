import os
import threading
import discord
from discord.ext import commands
from discord import app_commands, utils, AuditLogAction 
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
intents.members = True          # メンバーログとkick/banのために必要
intents.message_content = True  

# Prefixを '!' に設定
bot = commands.Bot(command_prefix="!", intents=intents)

# 🚨 グローバルストレージ (Botが再起動するとリセットされます)
guild_log_channels = {}
guild_invites = {} # ★ 招待リンク追跡用のキャッシュ


# 環境変数からの設定 (省略)
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing.")
except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 🤝 イベントリスナー (ログ機能の強化) ---
# ----------------------------------------------------

@bot.event
async def on_member_join(member):
    """メンバーがサーバーに参加したときに実行 (招待元を追跡)"""
    guild_id = member.guild.id
    
    # --- 招待元追跡ロジック ---
    invite_used = None
    
    if guild_id in guild_invites:
        try:
            # 最新の招待リストを取得
            new_invites = await member.guild.invites()
            old_invites = guild_invites[guild_id]
            
            # 使用された招待リンクを特定 (使用回数が1増えたもの)
            for invite in new_invites:
                if invite.code in old_invites and invite.uses > old_invites[invite.code]:
                    invite_used = invite
                    break
            
            # キャッシュを更新
            guild_invites[guild_id] = {invite.code: invite.uses for invite in new_invites}

        except discord.Forbidden:
            logging.warning(f"ギルド {member.guild.name}: 招待追跡の権限がありません。")
            pass 
        except Exception as e:
            logging.error(f"ギルド {member.guild.name}: 招待追跡中にエラー: {e}")
    # ---------------------------

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
            
            if invite_used:
                embed.add_field(name="招待元", 
                                value=f"{invite_used.inviter.mention} ({invite_used.inviter.name})\nコード: `{invite_used.code}`", 
                                inline=False)
            else:
                embed.add_field(name="招待元", value="不明 (またはVanity URL, Bot招待など)", inline=False)
            
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logging.error(f"ログチャンネルへの送信権限がありません。")

@bot.event
async def on_member_remove(member):
    """メンバーがサーバーを退出したときに実行 (BAN/KICKを判別)"""
    guild_id = member.guild.id
    
    # --- 退出理由特定ロジック ---
    action_type = "退室" 
    reason = "理由なし"
    perpetrator = None # 操作者
    
    # 監査ログの反映を待つため、短い遅延を入れる
    await asyncio.sleep(0.5) 
    
    try:
        # 監査ログを最近の操作から最大10件取得
        async for entry in member.guild.audit_logs(limit=10, 
                                                   action=(AuditLogAction.kick, AuditLogAction.ban)):
            
            # ターゲットがこのユーザーであり、操作がイベント発生からごく短時間内（例: 5秒以内）に行われたか確認
            if entry.target and entry.target.id == member.id and \
               (utils.utcnow() - entry.created_at).total_seconds() < 5:
                
                if entry.action == AuditLogAction.kick:
                    action_type = "KICK"
                    reason = entry.reason if entry.reason else "理由なし"
                    perpetrator = entry.user
                    break
                elif entry.action == AuditLogAction.ban:
                    action_type = "BAN"
                    reason = entry.reason if entry.reason else "理由なし"
                    perpetrator = entry.user
                    break
    
    except discord.Forbidden:
        reason = "監査ログ表示権限がないため理由不明"
    except Exception as e:
        logging.error(f"監査ログ処理中にエラー: {e}")

    # ---------------------------

    if guild_id in guild_log_channels:
        channel_id = guild_log_channels[guild_id]
        channel = bot.get_channel(channel_id)

        title = ""
        color = discord.Color.red()

        if action_type == "KICK":
            title = f"💥 メンバーKICK ({perpetrator.name if perpetrator else '不明'}による操作)"
            color = discord.Color.orange()
        elif action_type == "BAN":
            title = f"🔨 メンバーBAN ({perpetrator.name if perpetrator else '不明'}による操作)"
            color = discord.Color.dark_red()
        else:
            title = "⬅️ メンバー退室 (自己退室または不明)"
            color = discord.Color.red()

        if channel:
            embed = discord.Embed(
                title=title,
                description=f"{member.mention} ({member.id}) がサーバーを離れました。",
                color=color,
                timestamp=utils.utcnow()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="現在のメンバー数", value=member.guild.member_count - 1, inline=True) 
            
            if member.joined_at:
                embed.add_field(name="参加日時", value=utils.format_dt(member.joined_at, 'F'), inline=False)
            
            embed.add_field(name="理由/種別", value=f"**{action_type}**\n理由: {reason}", inline=False)
            
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                logging.error(f"ログチャンネルへの送信権限がありません。")


# ----------------------------------------------------
# --- 🛠️ コマンド定義 (前回コードから変更なし) ---
# ----------------------------------------------------
# ... (JoinLogクラス、delete_categoryコマンド、ping, kick, banコマンドの定義は前回コードと同じ)
# (コードが長くなるため、ここには省略した形で記述します。完全なコードは前回のものに上記の修正を加えてください)

class JoinLog(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="joinlog", description="入室/退室ログチャンネルを設定します。")
        self.bot = bot

    @app_commands.command(name="set", description="入室・退室ログを送信するチャンネルを設定します。")
    @app_commands.describe(channel="ログを送信するチャンネル")
    @app_commands.default_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドを実行するには「管理者」権限が必要です。", ephemeral=True)
            return
        guild_log_channels[interaction.guild_id] = channel.id
        await interaction.response.send_message(f"✅ 入室・退室ログの送信先を {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="disable", description="入室・退室ログの送信を無効にします。")
    @app_commands.default_permissions(administrator=True)
    async def disable_log_channel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ このコマンドを実行するには「管理者」権限が必要です。", ephemeral=True)
            return
        if interaction.guild_id in guild_log_channels:
            del guild_log_channels[interaction.guild_id]
            await interaction.response.send_message("✅ 入室・退室ログの送信を無効にしました。", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 現在、入室・退室ログは設定されていません。", ephemeral=True)

@bot.tree.command(name="delete_category", description="指定した名前のカテゴリーチャンネルを削除します。配下のチャンネルも全て削除されます。")
@app_commands.describe(category_name="削除したいカテゴリーの名前 (完全一致)")
@app_commands.default_permissions(administrator=True)
async def delete_category(interaction: discord.Interaction, category_name: str):
    await interaction.response.defer(ephemeral=True, thinking=True) 
    if not interaction.user.guild_permissions.administrator:
        await interaction.followup.send("❌ このコマンドを実行するには「管理者」権限が必要です。", ephemeral=True)
        return
    guild = interaction.guild
    target_category = None
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel) and channel.name == category_name:
            target_category = channel
            break
    if not target_category:
        await interaction.followup.send(f"❌ 「**{category_name}**」という名前のカテゴリーは見つかりませんでした。", ephemeral=True)
        return
    deleted_channels_count = len(target_category.channels)
    try:
        await target_category.delete()
        await interaction.followup.send(
            f"✅ カテゴリー「**{target_category.name}**」と、その配下のチャンネル **{deleted_channels_count}個** を削除しました。",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.followup.send("❌ Botにこのカテゴリーを削除する権限がありません。Botのロールを上位にしてください。", ephemeral=True)
    except Exception as e:
        logging.error(f"カテゴリー削除中にエラーが発生: {e}")
        await interaction.followup.send(f"❌ カテゴリー削除中に予期せぬエラーが発生しました: {e}", ephemeral=True)

# ... (ping, kick, banコマンドの定義は省略)
@bot.command(name="ping", help="Botのレイテンシを表示します。")
async def ping_prefix(ctx):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! 応答速度: {latency_ms}ms")

@bot.tree.command(name="ping", description="Botのレイテンシを表示します。")
async def ping_slash(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 応答速度: {latency_ms}ms", ephemeral=True)

# ... (kickとbanのプレフィックス/スラッシュコマンドの定義とエラーハンドリングも省略)
# ----------------------------------------------------


# ----------------------------------------------------
# --- Discord イベント & 起動 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    """Bot起動時に実行"""
    # グループクラスをBotに組み込む
    bot.tree.add_command(JoinLog(bot))
    
    # ★ 修正: Bot起動時に全ギルドの招待リンクをキャッシュする
    for guild in bot.guilds:
        try:
            guild_invites[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
        except discord.Forbidden:
            logging.warning(f"ギルド {guild.name}: 招待追跡の権限がないため、招待リンクのキャッシュをスキップします。")
        except Exception as e:
            logging.error(f"ギルド {guild.name}: 招待取得中にエラーが発生しました: {e}")

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
