import os
import threading
from flask import Flask, jsonify
import discord
from discord.ext import commands
from discord import app_commands # スラッシュコマンドに必要なモジュール
import random
import logging
from colorama import init, Fore as cc
from sys import exit
from datetime import datetime

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
# スラッシュコマンドでもMessage Content Intentが必要です
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True
intents.moderation = True  # モデレーションエベントを有効にする

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix="!", intents=intents)

# ログチャンネルIDを環境変数から取得
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", 0))

# --- イベントと同期 ---

@bot.event
async def on_ready():
    """ボット起動時に実行される処理。スラッシュコマンドの同期を行います。"""
    # ボット起動時のステータス表示を設定
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="友達のサーバーで便利なBot")
    )
    logging.info("Bot is ready!")
    logging.info(f"Logged in as {bot.user}")

    # --- スラッシュコマンドの同期 ---
    GUILD_ID_STR = os.environ.get("GUILD_ID")

    if GUILD_ID_STR:
        try:
            # GUILD_ID環境変数があれば、そのギルドでのみ同期を試みる
            guild_id = int(GUILD_ID_STR)
            guild = bot.get_guild(guild_id)
            if guild:
                # ギルドを指定して同期
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
async def guess_slash(interaction: discord.Interaction, number: int):
    """1から100までの数字を当てるゲームです。"""
    if not 1 <= number <= 100:
        await interaction.response.send_message("1から100までの数字を入力してください。", ephemeral=True)
        return

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

@bot.tree.command(name="fakemessage", description="指定されたユーザーからのフェイクメッセージを送信します。")
@app_commands.describe(user="フェイクメッセージを送信するユーザー", message="送信するメッセージ")
async def fakemessage_slash(interaction: discord.Interaction, user: discord.Member, *, message: str):
    """指定されたユーザーからのフェイクメッセージを送信します。"""
    try:
        webhook = await interaction.channel.create_webhook(name=user.display_name)
        await webhook.send(
            message,
            username=user.display_name,
            avatar_url=user.avatar.url if user.avatar else None
