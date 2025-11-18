import os
import threading
from flask import Flask, jsonify
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import datetime
from sys import exit

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True
intents.moderation = True  # モデレーションエベントを有効にする

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix="!", intents=intents)

# ログチャンネルIDを環境変数から取得
try:
    LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", 0))
except ValueError:
    LOG_CHANNEL_ID = 0
    logging.warning("環境変数 'LOG_CHANNEL_ID' が無効な数値です。")


# --- イベントと同期 ---

@bot.event
async def on_ready():
    """ボット起動時に実行される処理。スラッシュコマンドの同期を行います。"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/help | 友達のサーバーで便利なBot")
    )
    logging.info("Bot is ready!")
    logging.info(f"Logged in as {bot.user}")

    # --- スラッシュコマンドの同期 ---
    GUILD_ID_STR = os.environ.get("GUILD_ID")

    if GUILD_ID_STR:
        try:
            guild_id = int(GUILD_ID_STR)
            guild = bot.get_guild(guild_id)
            if guild:
                # 指定ギルドで同期を強制実行
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                logging.info(f"指定ギルド ({guild.name}) でスラッシュコマンドを同期しました。登録数: {len(synced)}")
            else:
                logging.warning(f"GUILD_ID ({GUILD_ID_STR}) に対応するギルドが見つかりませんでした。グローバル同期を試みます。")
                synced = await bot.tree.sync()
                logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")

        except Exception as e:
            logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")
    else:
        # GUILD_IDが設定されていない場合は、グローバル同期を試みる
        try:
            synced = await bot.tree.sync()
            logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")
        except Exception as e:
            logging.error(f"グローバル同期中にエラーが発生しました: {e}")

@bot.event
async def on_guild_join(guild):
    logging.info(f"Joined {guild.name}")


# --- スラッシュコマンドの定義 ---

@bot.tree.command(name="help", description="利用可能なコマンド一覧を表示します。")
async def help_slash(interaction: discord.Interaction):
    """コマンド一覧を表示します。"""
    embed = discord.Embed(
        title="🤖 Botコマンドヘルプ",
        description="ひめ鯖専用Botの機能一覧です。",
        color=0x3498DB
    )
    
    commands_list = [
        ("`/help`", "このヘルプを表示します。"),
        ("`/ping`", "ボットの応答速度（Ping）を測定します。"),
        ("`/info`", "ユーザーの詳細情報を表示します。"),
        ("`/serverstatus`", "サーバーの統計情報を表示します。"),
        ("`/guess <数字>`", "1から100までの数字を当てるゲームです。"),
        ("`/fakemessage`", "指定ユーザーになりすましてメッセージを送信します。"),
        ("`/kick <メンバー> <理由>`", "指定メンバーをキックします。（権限が必要）")
    ]
    
    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)
        
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info("Action completed: Slash Help")


@bot.tree.command(name="ping", description="ボットの遅延 (Ping) を計算します。")
async def ping_slash(interaction: discord.Interaction):
    """ボットの遅延 (Ping) を計算し、結果を一時的なメッセージとして送信します。"""
    latency_ms = round(bot.latency * 1000)

    embed = discord.Embed(title="Pong!", description=f'Ping: {latency_ms}ms', color=0x2874A6)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info("Action completed: Slash Ping")


@bot.tree.command(name="info", description="指定されたユーザーの情報を表示します。")
@app_commands.describe(member="情報を表示するメンバーを指定 (省略可)")
async def info_slash(interaction: discord.Interaction, member: discord.Member = None):
    """指定されたユーザーまたはコマンド実行者の情報を表示します。"""
    target_member = member or interaction.user

    embed = discord.Embed(
        title=f"{target_member.display_name} の情報",
        color=target_member.color if target_member.color != discord.Color.default() else 0x2874A6
    )
    embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else None)

    embed.add_field(name="ユーザー名", value=target_member.name, inline=True)
    embed.add_field(name="ユーザーID", value=target_member.id, inline=True)
    embed.add_field(name="ステータス", value=str(target_member.status).capitalize(), inline=True)
    embed.add_field(name="最高の役職", value=target_member.top_role.name, inline=True)
    embed.add_field(name="参加日時", value=target_member.joined_at.strftime('%Y/%m/%d %H:%M:%S'), inline=False)

    await interaction.response.send_message(embed=embed)
    logging.info("Action completed: Slash User Info")


@bot.tree.command(name="serverstatus", description="サーバーのステータスを表示します。")
async def serverstatus_slash(interaction: discord.Interaction):
    """サーバーのステータスを表示するコマンドです。"""
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("このコマンドはサーバー内でのみ実行できます。", ephemeral=True)
        return

    embed = discord.Embed(title=f"サーバー情報: {guild.name}", color=0x2874A6)
    embed.add_field(name="メンバー数", value=f"{guild.member_count}人", inline=False)
    embed.add_field(name="テキストチャンネル", value=f"{len(guild.text_channels)}", inline=True)
    embed.add_field(name="ボイスチャンネル", value=f"{len(guild.voice_channels)}", inline=True)
    embed.add_field(name="役職数", value=f"{len(guild.roles)}", inline=True)
    embed.add_field(name="サーバーオーナー", value=guild.owner.display_name if guild.owner else "不明", inline=False)
    embed.add_field(name="地域", value=str(guild.preferred_locale).upper(), inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    await interaction.response.send_message(embed=embed)
    logging.info("Action completed: Slash Server Status")


@bot.tree.command(name="guess", description="1から100までの数字を当てるゲームです。")
@app_commands.describe(number="1から100までの数字")
async def guess_slash(interaction: discord.Interaction, number: app_commands.Range[int, 1, 100]):
    """1から100までの数字を当てるゲームです。"""
    # app_commands.Range[int, 1, 100] を再導入し、入力値のバリデーションをDiscordに任せます。

    target_number = random.randint(1, 100)

    embed = discord.Embed(color=0x2874A6)

    if number == target_number:
        embed.title = "🎉 おめでとうございます！ 🎉"
        embed.description = f"正解です！あなたが当てた数字は **{target_number}** でした！"
    else:
        embed.title = "残念..."
        embed.description = f"ハズレです。正解の数字は **{target_number}** でした。もう一度挑戦してみてください！"

    await interaction.response.send_message(embed=embed)
    logging.info("Action completed: Guess the Number Game")


@bot.tree.command(name="fakemessage", description="指定されたユーザーになりすましてメッセージを送信します (Webhookを使用)。")
@app_commands.describe(
    user="なりすますユーザーを指定", 
    message="送信するメッセージ内容"
)
async def fakemessage_slash(interaction: discord.Interaction, user: discord.Member, message: str):
    """指定されたユーザーからのフェイクメッセージを送信するコマンドです。"""
    
    try:
        # Webhook作成前に、処理中であることを通知
        await interaction.response.defer(ephemeral=True)
        
        webhook = await interaction.channel.create_webhook(name=user.display_name)
        await webhook.send(
            message, 
            username=user.display_name, 
            avatar_url=user.avatar.url if user.avatar else None # 修正：アバターURLを取得
        )
        await webhook.delete()
        
        await interaction.followup.send("フェイクメッセージを送信しました。", ephemeral=True)
        
        logging.info(f"Fake message sent from {user.display_name} in {interaction.channel.name} via slash command.")

    except discord.Forbidden:
        await interaction.followup.send("エラー: Webhookを作成または管理する権限がありません。", ephemeral=True)
        logging.error("Missing webhook permissions for fakemessage command.")
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)
        logging.error(f"Error in slash fakemessage: {e}")


@bot.tree.command(name="kick", description="指定されたメンバーをサーバーからキックします。")
@app_commands.describe(member="キックするメンバー", reason="キックする理由 (省略可)")
@commands.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    """指定されたメンバーをサーバーからキックします。"""
    
    # 実行者より上位の役職や自分自身をキックできないようにするチェック
    if member.top_role >= interaction.user.top_role and member != interaction.user:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーをキックすることはできません。", ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message("自分自身をキックすることはできません。", ephemeral=True)
        return
    
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} をキックしました。理由: {reason}")
        
        # ログチャンネルへの送信
        if LOG_CHANNEL_ID != 0:
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="メンバーキックログ",
                    description=f"{member.display_name} (ID: {member.id}) がキックされました。",
                    color=discord.Color.red()
                )
                log_embed.add_field(name="実行者", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="理由", value=reason, inline=True)
                log_embed.timestamp = datetime.now()
                await log_channel.send(embed=log_embed)

    except discord.Forbidden:
        await interaction.response.send_message("エラー: キックする権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

# --- KeepAlive Server & Main Execution (Render安定化) ---

# Webサーバーを構築するためのFlaskを初期化
app = Flask(__name__)

# Discord Botを別スレッドで起動する関数
def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    
    if not TOKEN:
        logging.error("致命的なエラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        # トークンが取得できた場合（デバッグログ）
        token_preview = TOKEN[:5] + "..." + TOKEN[-5:]
        logging.info(f"DISCORD_TOKENを読み込みました (Preview: {token_preview})")
        
        try:
            # Botを実行
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効、または必要なインテントが不足しています。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

# GunicornがFlaskアプリを起動する直前にBotスレッドを起動
bot_thread = threading.Thread(target=start_bot)
bot_thread.start()


@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    # Botがオンラインであることを確認できる簡単なメッセージ
    if bot.is_ready():
        return "Bot is running and ready!"
    else:
        return "Bot is starting up..."

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200


