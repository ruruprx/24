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

# ログ送信関数
async def send_log(guild, title, description, fields):
    if LOG_CHANNEL_ID != 0:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            for name, value, inline in fields:
                log_embed.add_field(name=name, value=value, inline=inline)
            await log_channel.send(embed=log_embed)

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

# --- メッセージ削除ログ ---
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await send_log(
        message.guild,
        "メッセージ削除ログ",
        f"{message.author.mention} がメッセージを削除しました。",
        [("実行者", message.author.mention, True), ("削除されたメッセージ", message.content, False)]
    )

# --- メッセージ編集ログ ---
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    await send_log(
        before.guild,
        "メッセージ編集ログ",
        f"{before.author.mention} がメッセージを編集しました。",
        [("実行者", before.author.mention, True), ("編集前のメッセージ", before.content, False), ("編集後のメッセージ", after.content, False)]
    )

# --- 名前変更ログ ---
@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        await send_log(
            before.guild,
            "名前変更ログ",
            f"{before.mention} の名前が変更されました。",
            [("実行者", before.mention, True), ("変更前の名前", before.nick, False), ("変更後の名前", after.nick, False)]
        )

# --- キックログ ---
@bot.event
async def on_member_remove(member):
    if member.guild.me.top_role.position > member.top_role.position:
        await send_log(
            member.guild,
            "メンバーキックログ",
            f"{member.mention} がキックされました。",
            [("実行者", "不明", True), ("キックされたメンバー", member.mention, False)]
        )

# --- BANログ ---
@bot.event
async def on_member_ban(guild, user):
    await send_log(
        guild,
        "メンバーバンログ",
        f"{user.mention} がBANされました。",
        [("実行者", "不明", True), ("BANされたメンバー", user.mention, False)]
    )

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
    target_member = member or
