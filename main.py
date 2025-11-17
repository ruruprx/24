import os
import threading
from flask import Flask, jsonify
import discord
from discord.ext import commands
import time
import asyncio
import random
import requests
import logging
from colorama import init, Fore as cc
from os import name as os_name, system
from sys import exit

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- KeepAlive Server for Render & UptimeRobot ---
# Webサーバーを構築するためのFlaskを初期化
app = Flask(__name__)

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return "Bot is running!"

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200

def run_flask():
    """Flaskサーバーを別スレッドで起動する関数"""
    # Renderが設定する環境変数 'PORT' を使用
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting Flask server on port {port}...")
    # 外部からのアクセスを許可するため host='0.0.0.0' を指定
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Webサーバーをメインのボット処理と並行して起動する"""
    t = threading.Thread(target=run_flask)
    t.start()
    logging.info("Keep-alive server started.")

# --- Discord Bot Setup ---
# ⚠️ トークンやプレフィックスは外部ファイルではなく、環境変数とコード内で直接定義
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix="!", intents=intents)

# デフォルトのヘルプコマンドを削除
bot.remove_command("help")

@bot.event
async def on_ready():
    # ボット起動時のステータス表示を設定
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="友達のサーバーで便利なBot")
    )
    logging.info("Bot is ready!")
    logging.info(f"Logged in as {bot.user}")

@bot.event
async def on_guild_join(guild):
    logging.info(f"Joined {guild.name}")

#### PING COMMAND ####
@bot.slash_command(name="ping", description="ボットの遅延 (Ping) を計算しDMで送信するコマンド")
async def ping(ctx):
    """ボットの遅延 (Ping) を計算しDMで送信するコマンド"""
    await ctx.respond("計測中...")
    latency_ms = round(bot.latency * 1000)
    embed=discord.Embed(title="Pong!", description=f'Ping: {latency_ms}ms', color=0x2874A6)
    await ctx.followup.send(embed=embed, ephemeral=True)
    logging.info("Action completed: Server ping")

#### INFO COMMAND ####
@bot.slash_command(name="info", description="指定されたユーザーまたはコマンド実行者の情報を表示するコマンド")
async def info(ctx, member: discord.Member=None):
    """指定されたユーザーまたはコマンド実行者の情報を表示するコマンド"""
    target_member = member or ctx.author
    response = (
        f"**ユーザー名: {target_member.name}**"
        f"\n**ユーザーID: {target_member.id}**"
        f"\n**現在のステータス: {target_member.status}**"
        f"\n**最高の役職: {target_member.top_role}**"
        f"\n**参加日: {target_member.joined_at.strftime('%Y/%m/%d %H:%M:%S')}**"
    )
    await ctx.respond(response, ephemeral=True)
    logging.info("Action completed: User Info")

#### SERVER STATUS COMMAND ####
@bot.slash_command(name="serverstatus", description="サーバーのステータスを表示するコマンド")
async def serverstatus(ctx):
    """サーバーのステータスを表示するコマンド"""
    guild = ctx.guild
    embed = discord.Embed(title=f"サーバーステータス: {guild.name}", color=0x2874A6)
    embed.add_field(name="メンバー数", value=f"{guild.member_count} 人", inline=False)
    embed.add_field(name="テキストチャンネル", value=f"{len(guild.text_channels)} チャンネル", inline=False)
    embed.add_field(name="ボイスチャンネル", value=f"{len(guild.voice_channels)} チャンネル", inline=False)
    embed.add_field(name="役職", value=f"{len(guild.roles)} 役職", inline=False)
    await ctx.respond(embed=embed, ephemeral=True)
    logging.info("Action completed: Server Status")

#### RANDOM NUMBER GAME ####
@bot.slash_command(name="guess", description="1から100までの数字を当てるゲーム")
async def guess(ctx, number: int):
    """1から100までの数字を当てるゲーム"""
    target_number = random.randint(1, 100)
    if number == target_number:
        await ctx.respond(f"おめでとう！あなたの答え {number} は正解です！")
    else:
        await ctx.respond(f"残念！正解は {target_number} でした。次は当たるでしょう！")
    logging.info("Action completed: Guess the Number Game")

#### FAKE MESSAGE COMMAND ####
@bot.slash_command(name="fakemessage", description="指定されたユーザーからのフェイクメッセージを送信するコマンド")
async def fakemessage(ctx, user: discord.Member, *, message: str):
    """指定されたユーザーからのフェイクメッセージを送信するコマンド"""
    webhook = await ctx.channel.create_webhook(name=user.display_name)
    await webhook.send(message, username=user.display_name, avatar_url=user.avatar.url)
    await webhook.delete()
    logging.info(f"Fake message sent from {user.display_name} in {ctx.channel.name}")

# --- Main Execution ---
# ⚠️ このブロックがファイルの**一番最後**に配置されます。
if __name__ == "__main__":
    # 環境変数からトークンを直接取得
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        # 1. Keep-alive サーバーを起動
        keep_alive()

        # 2. Discord ボットを起動
        bot.run(TOKEN)
