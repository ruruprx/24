import os
import threading
from flask import Flask, jsonify
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import datetime, timedelta
import re

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 Gunicorn対応: Flaskアプリの定義を最上位に移動 🚨 ---
# Gunicornはこの 'app' オブジェクトをエントリーポイントとして探します。
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True          # メンバー情報やリアクションロール、挨拶に必須
intents.message_content = True  # on_message (オートモデレーション) に必須
intents.moderation = True
intents.presences = True        # プレゼンス（ステータス）のログに必要

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数から設定を取得
try:
    LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", 0))
    WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", 0))
except ValueError:
    LOG_CHANNEL_ID = 0
    WELCOME_CHANNEL_ID = 0
    logging.warning("環境変数 'LOG_CHANNEL_ID' または 'WELCOME_CHANNEL_ID' が無効な数値です。")

# --- Carl-bot風 データストア (インメモリ/Bot再起動でリセット) ---
# 警告履歴: {user_id: [{id: int, moderator_id: int, reason: str, timestamp: datetime}, ...]}
warn_history = {} 
# リアクションロール設定 (前回と同じ簡易設定)
REACTION_ROLE_MSG_ID = 0
REACTION_ROLE_MAP = {
    "🎮": "ゲーマー",
    "📢": "通知受け取り",
    "💡": "アイデア出し"
}

# --- 警告システム用ヘルパー関数 ---

def get_next_warn_id(user_id):
    """ユーザーの次の警告IDを計算する"""
    if user_id not in warn_history:
        return 1
    # 履歴内の警告IDの最大値 + 1
    return max([w['id'] for w in warn_history[user_id]]) + 1

# ログ送信関数 (色指定を可能に)
async def send_log(guild, title, description, fields, color=discord.Color.blue()):
    """
    指定された情報をログチャンネルに送信します。
    """
    if LOG_CHANNEL_ID != 0:
        if guild is not None:
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
        else:
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            
        if log_channel:
            log_embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now()
            )
            for name, value, inline in fields:
                if value:
                    log_embed.add_field(name=name, value=value, inline=inline)
            
            try:
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                logging.error(f"ログチャンネル ({LOG_CHANNEL_ID}) への送信権限がありません。")

# --- イベントと同期 ---

@bot.event
async def on_ready():
    """ボット起動時に実行される処理。スラッシュコマンドの同期を行います。"""
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/help | Carl-bot風 多機能 Bot")
    )
    logging.info("Bot is ready!")
    
    # --- スラッシュコマンドの同期 (既存ロジック) ---
    GUILD_ID_STR = os.environ.get("GUILD_ID")
    if GUILD_ID_STR:
        try:
            guild_id = int(GUILD_ID_STR)
            guild = bot.get_guild(guild_id)
            if guild:
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                logging.info(f"指定ギルド ({guild.name}) でスラッシュコマンドを同期しました。登録数: {len(synced)}")
            else:
                synced = await bot.tree.sync()
                logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")
        except Exception as e:
            logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")
    else:
        try:
            synced = await bot.tree.sync()
            logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")
        except Exception as e:
            logging.error(f"グローバル同期中にエラーが発生しました: {e}")

# --- Carl-bot風 カスタム挨拶機能 ---

@bot.event
async def on_member_join(member):
    """メンバー参加時のウェルカムメッセージを送信し、ログを記録"""
    if member.guild is None:
        return

    # ログ記録
    await send_log(
        member.guild,
        "メンバー参加ログ",
        f"新しいメンバーが参加しました: {member.mention}",
        [
            ("ユーザー名", member.name, True), 
            ("アカウント作成日", member.created_at.strftime('%Y/%m/%d %H:%M:%S'), False)
        ],
        discord.Color.green()
    )
    
    # カスタム挨拶メッセージ
    if WELCOME_CHANNEL_ID != 0:
        welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            # {user}, {server}, {count} などのプレースホルダーを再現
            welcome_message = (
                f"🎉 **{member.mention}** さん、**{member.guild.name}** へようこそ！ 🎉\n"
                f"あなたはサーバーの**{len(member.guild.members)}**人目のメンバーです。\n"
                "ルールを確認して、楽しい時間を過ごしましょう！"
            )
            try:
                await welcome_channel.send(welcome_message)
            except discord.Forbidden:
                logging.warning("挨拶チャンネルへの送信権限がありません。")

@bot.event
async def on_member_remove(member):
    """メンバー脱退時のグッバイメッセージを送信し、ログを記録"""
    if member.guild is None:
        return
    
    # ログ記録
    await send_log(
        member.guild,
        "メンバー脱退ログ",
        f"{member.mention} ({member.id}) がサーバーを去りました。",
        [("ユーザー名", member.name, True)],
        discord.Color.orange()
    )
    
    # カスタムグッバイメッセージ
    if WELCOME_CHANNEL_ID != 0:
        goodbye_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if goodbye_channel:
            goodbye_message = (
                f"👋 **{member.display_name}** さんがサーバーを去りました。\n"
                f"またのご利用をお待ちしています！"
            )
            try:
                await goodbye_channel.send(goodbye_message)
            except discord.Forbidden:
                pass # ログ記録済み

# --- Carl-bot風 詳細ログの維持 (以前のバージョンから継承) ---

@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None: return
    await send_log(message.guild, "メッセージ削除ログ", f"{message.author.mention} がメッセージを削除しました。 (チャンネル: {message.channel.name})",
                   [("実行者", message.author.mention, True), ("削除されたメッセージ", message.content or "（埋め込み、画像など）", False)], discord.Color.blue())

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content or before.guild is None: return
    await send_log(before.guild, "メッセージ編集ログ", f"{before.author.mention} がメッセージを編集しました。 (チャンネル: {before.channel.name})",
                   [("実行者", before.author.mention, True), ("編集前のメッセージ", before.content, False), ("編集後のメッセージ", after.content, False)], discord.Color.gold())

@bot.event
async def on_guild_channel_create(channel):
    await send_log(channel.guild, "チャンネル作成ログ", f"チャンネルが作成されました: {channel.name}",
                   [("チャンネルタイプ", str(channel.type).split('.')[-1].capitalize(), True)], discord.Color.dark_green())

@bot.event
async def on_guild_channel_delete(channel):
    await send_log(channel.guild, "チャンネル削除ログ", f"チャンネルが削除されました: {channel.name}",
                   [("チャンネルID", str(channel.id), True)], discord.Color.dark_red())

@bot.event
async def on_guild_role_create(role):
    await send_log(role.guild, "ロール作成ログ", f"新しいロールが作成されました: {role.name}",
                   [("色", str(role.color), True)], discord.Color.light_grey())

@bot.event
async def on_guild_role_delete(role):
    await send_log(role.guild, "ロール削除ログ", f"ロールが削除されました: {role.name}",
                   [("削除されたロールID", str(role.id), True)], discord.Color.dark_grey())

# --- Carl-bot風 簡易オートモデレーション強化 ---

@bot.event
async def on_message(message):
    """Discord招待リンクとメンションスパムをチェックし、問題があれば削除します。"""
    if message.author.bot:
        return

    # 1. Discord招待リンクの削除
    discord_invite_regex = r'(discord\.(gg|io|me|com\/invite)\/[a-zA-Z0-9]+)'
    if re.search(discord_invite_regex, message.content):
        try:
            await message.delete()
            await send_log(message.guild, "🚨 オートモデレーション警告", 
                           f"{message.author.mention} が禁止されている招待リンクを投稿しました。",
                           [("検知内容", "Discord招待リンク", False)], discord.Color.purple())
            return # 招待リンクを削除したら他のチェックは不要

        except discord.Forbidden:
            logging.warning("Auto-Mod: 権限不足により招待リンクを削除できませんでした。")
    
    # 2. メンションスパムのチェック (例: 5人以上のユーザーをメンション)
    MENTION_SPAM_LIMIT = 5
    if len(message.mentions) >= MENTION_SPAM_LIMIT:
        try:
            await message.delete()
            await send_log(message.guild, "🚨 オートモデレーション警告", 
                           f"{message.author.mention} がメンションスパムの制限を超過しました ({len(message.mentions)}人)。",
                           [("検知内容", "メンションスパム", False)], discord.Color.dark_purple())
            return
            
        except discord.Forbidden:
            logging.warning("Auto-Mod: 権限不足によりメンションスパムメッセージを削除できませんでした。")

    await bot.process_commands(message)


# --- スラッシュコマンドの定義 (省略 - 変更なし) ---

@bot.tree.command(name="help", description="利用可能なコマンド一覧を表示します。")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Botコマンドヘルプ (Carl-bot風)",
        description="モデレーションとコミュニティ機能が充実しています。",
        color=0x3498DB
    )

    commands_list = [
        ("--- モデレーション ---", "Carl-botの核となるモデレーション機能"),
        ("`/warn <メンバー> <理由>`", "指定メンバーに警告を付与し、履歴に記録します。"),
        ("`/warns <メンバー>`", "指定メンバーの警告履歴を一覧表示します。"),
        ("`/unwarn <メンバー>`", "指定メンバーの最新の警告を1つ削除します。"),
        ("`/timeout <メンバー> <分>`", "メンバーに一時的なタイムアウトを課します。"),
        ("`/kick <メンバー> <理由>`", "メンバーをキックします。"),
        ("`/clear <件数>`", "メッセージを一括削除します。"),
        ("--- コミュニティ＆ユーティリティ ---", "エンゲージメントと情報表示"),
        ("`/rr_setup`", "リアクションロールの設定メッセージを送信します。"),
        ("`/poll <質問> <選択肢>`", "簡易投票を作成します。"),
        ("`/info`", "ユーザーの詳細情報を表示します。"),
        ("`/serverstatus`", "サーバーの統計情報を表示します。"),
        ("`/ping`", "Botの遅延を計算します。"),
    ]

    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info("Action completed: Slash Help")


# --- Carl-bot風 警告システムコマンド ---

@bot.tree.command(name="warn", description="指定されたメンバーに警告を付与します。")
@app_commands.describe(member="警告するメンバー", reason="警告の理由")
@commands.has_permissions(moderate_members=True)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str):
    """メンバーに警告を付与し、インメモリの履歴に記録します。"""
    global warn_history
    
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーに警告を付与することはできません。", ephemeral=True)
        return

    # 警告レコードを作成
    warn_id = get_next_warn_id(member.id)
    new_warn = {
        'id': warn_id,
        'moderator_id': interaction.user.id,
        'reason': reason,
        'timestamp': datetime.now()
    }

    if member.id not in warn_history:
        warn_history[member.id] = []
    
    warn_history[member.id].append(new_warn)
    
    total_warns = len(warn_history[member.id])

    # 応答
    await interaction.response.send_message(f"⚠️ {member.display_name} に警告を付与しました。 (警告数: **{total_warns}**) 理由: `{reason}`")

    # ログ送信
    await send_log(
        interaction.guild,
        "メンバー警告ログ (Warn)",
        f"{member.display_name} に警告が発行されました。",
        [
            ("実行者", interaction.user.mention, True), 
            ("対象ユーザー", member.mention, True),
            ("理由", reason, False),
            ("合計警告数", str(total_warns), True)
        ],
        discord.Color.orange()
    )
    
@bot.tree.command(name="warns", description="指定されたメンバーの警告履歴を表示します。")
@app_commands.describe(member="履歴を表示するメンバー")
@commands.has_permissions(moderate_members=True)
async def warns_slash(interaction: discord.Interaction, member: discord.Member):
    """メンバーの警告履歴を一覧表示します。"""
    global warn_history
    
    warns = warn_history.get(member.id, [])
    
    if not warns:
        await interaction.response.send_message(f"✅ {member.display_name} には警告履歴がありません。", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"⚠️ {member.display_name} の警告履歴 (合計: {len(warns)}件)",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    
    for warn in warns:
        mod_user = interaction.guild.get_member(warn['moderator_id'])
        mod_name = mod_user.display_name if mod_user else "不明なモデレーター"
        
        embed.add_field(
            name=f"Warn ID: #{warn['id']} (日付: {warn['timestamp'].strftime('%Y/%m/%d')})",
            value=f"**理由:** `{warn['reason']}`\n**担当:** {mod_name}",
            inline=False
        )
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unwarn", description="指定されたメンバーの最新の警告を1つ削除します。")
@app_commands.describe(member="警告を削除するメンバー")
@commands.has_permissions(moderate_members=True)
async def unwarn_slash(interaction: discord.Interaction, member: discord.Member):
    """メンバーの最新の警告を1つ削除します。"""
    global warn_history
    
    if member.id not in warn_history or not warn_history[member.id]:
        await interaction.response.send_message(f"⚠️ {member.display_name} には削除できる警告履歴がありません。", ephemeral=True)
        return

    # 最新の警告 (リストの末尾) を削除
    removed_warn = warn_history[member.id].pop()
    
    remaining_warns = len(warn_history[member.id])
    
    # 履歴が空になったらキーを削除
    if not warn_history[member.id]:
        del warn_history[member.id]

    # 応答
    await interaction.response.send_message(
        f"✅ {member.display_name} の最新の警告 **(ID: #{removed_warn['id']})** を削除しました。\n"
        f"現在の警告数: **{remaining_warns}**件"
    )

    # ログ送信
    await send_log(
        interaction.guild,
        "メンバー警告削除ログ (Unwarn)",
        f"{member.display_name} の警告が削除されました。",
        [
            ("実行者", interaction.user.mention, True), 
            ("対象ユーザー", member.mention, True),
            ("削除されたID", str(removed_warn['id']), True),
            ("削除された理由", removed_warn['reason'], False)
        ],
        discord.Color.blue()
    )


# --- 既存モデレーションコマンドの維持 (機能は以前のバージョンと同じ) ---

@bot.tree.command(name="kick", description="指定されたメンバーをサーバーからキックします。")
@app_commands.describe(member="キックするメンバー", reason="キックする理由 (省略可)")
@commands.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーをキックすることはできません。", ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message("自分自身をキックすることはできません。", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} をキックしました。理由: {reason}")
        await send_log(interaction.guild, "メンバーキックログ (実行)", f"{member.display_name} がキックされました。",
                       [("実行者", interaction.user.mention, True), ("対象ユーザー", member.mention, True), ("理由", reason, False)], discord.Color.red())
    except discord.Forbidden:
        await interaction.response.send_message("エラー: キックする権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

@bot.tree.command(name="timeout", description="メンバーに一時的なタイムアウトを課します。")
@app_commands.describe(member="タイムアウトするメンバー", minutes="タイムアウト時間 (1分〜40320分/4週間)", reason="理由 (省略可)")
@commands.has_permissions(moderate_members=True)
async def timeout_slash(interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "理由なし"):
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーにタイムアウトを課すことはできません。", ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message("自分自身にタイムアウトを課すことはできません。", ephemeral=True)
        return
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"⏸️ {member.display_name} に {minutes} 分間のタイムアウトを課しました。理由: {reason}")
        await send_log(interaction.guild, "メンバータイムアウトログ", f"{member.display_name} がタイムアウトされました。",
                       [("実行者", interaction.user.mention, True), ("期間", f"{minutes} 分間", True), ("理由", reason, False)], discord.Color.dark_teal())
    except discord.Forbidden:
        await interaction.response.send_message("エラー: タイムアウトを課す権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="指定された件数のメッセージを削除します (最大100件)。")
@app_commands.describe(count="削除するメッセージの件数 (1～100)")
@commands.has_permissions(manage_messages=True)
async def clear_slash(interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=count)
        await send_log(interaction.guild, "メッセージ一括削除ログ", f"{interaction.user.display_name} がメッセージを一括削除しました。",
                       [("実行者", interaction.user.mention, True), ("削除件数", str(len(deleted)), True)], discord.Color.dark_red())
        await interaction.followup.send(f"✅ {len(deleted)} 件のメッセージを削除しました。", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("エラー: メッセージを管理する権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

# --- 簡易リアクションロール設定 (/rr_setup) とイベントハンドラ (以前のバージョンと同じ) ---

@bot.tree.command(name="rr_setup", description=f"リアクションロールの設定メッセージを送信します。マップ: {', '.join(REACTION_ROLE_MAP.keys())}")
@commands.has_permissions(manage_roles=True)
async def rr_setup_slash(interaction: discord.Interaction):
    global REACTION_ROLE_MSG_ID
    description_lines = [
        "**📚 ロール自動付与ステーション 📚**",
        "欲しいロールに対応するリアクションをクリックしてください。",
        ""
    ]
    for emoji, role_name in REACTION_ROLE_MAP.items():
        description_lines.append(f"{emoji} で **{role_name}** ロールが付与/剥奪されます。")
    embed = discord.Embed(title="リアクションロール設定", description="\n".join(description_lines), color=discord.Color.purple())
    await interaction.response.defer(thinking=True)
    rr_message = await interaction.channel.send(embed=embed)
    REACTION_ROLE_MSG_ID = rr_message.id
    for emoji in REACTION_ROLE_MAP.keys():
        await rr_message.add_reaction(emoji)
    await interaction.followup.send(f"✅ リアクションロールメッセージを送信し、設定しました。メッセージID: `{REACTION_ROLE_MSG_ID}`", ephemeral=True)

@bot.event
async def on_raw_reaction_add(payload):
    global REACTION_ROLE_MSG_ID
    if payload.message_id != REACTION_ROLE_MSG_ID or payload.user_id == bot.user.id: return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member: return
    emoji_name = str(payload.emoji)
    if emoji_name in REACTION_ROLE_MAP:
        role_name_or_id = REACTION_ROLE_MAP[emoji_name]
        role_to_give = discord.utils.get(guild.roles, name=role_name_or_id)
        if not role_to_give and isinstance(role_name_or_id, str) and role_name_or_id.isdigit():
             role_to_give = guild.get_role(int(role_name_or_id))
        if role_to_give:
            try: await member.add_roles(role_to_give)
            except discord.Forbidden: logging.warning(f"Failed to give role {role_to_give.name}: Missing permissions.")

@bot.event
async def on_raw_reaction_remove(payload):
    global REACTION_ROLE_MSG_ID
    if payload.message_id != REACTION_ROLE_MSG_ID or payload.user_id == bot.user.id: return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member: return
    emoji_name = str(payload.emoji)
    if emoji_name in REACTION_ROLE_MAP:
        role_name_or_id = REACTION_ROLE_MAP[emoji_name]
        role_to_remove = discord.utils.get(guild.roles, name=role_name_or_id)
        if not role_to_remove and isinstance(role_name_or_id, str) and role_name_or_id.isdigit():
             role_to_remove = guild.get_role(int(role_name_or_id))
        if role_to_remove:
            try: await member.remove_roles(role_to_remove)
            except discord.Forbidden: logging.warning(f"Failed to remove role {role_to_remove.name}: Missing permissions.")

# --- KeepAlive Server & Main Execution (Render安定化) ---

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logging.error("致命的なエラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        token_preview = TOKEN[:5] + "..." + TOKEN[-5:]
        logging.info(f"DISCORD_TOKENを読み込みました (Preview: {token_preview})")
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効、または必要なインテントが不足しています。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

# Gunicornがメインプロセスで起動するときに、Botは別スレッドで起動します。
# Gunicornは 'app' オブジェクトをロードした後、このスレッド実行を許可します。
bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Bot is running and ready!"
    else:
        # Botの起動失敗時や起動中の状態も捕捉
        return "Bot is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200


