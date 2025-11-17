Import os
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
# INFOレベルでログを出力
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
    # 注: Renderの推奨デプロイ方法 (Gunicorn) ではこの関数は使わず、
    # 'gunicorn main:app' コマンドで実行されます。
    # ただし、threadingを使ったこの方式でも動作は可能です。
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Webサーバーをメインのボット処理と並行して起動する"""
    t = threading.Thread(target=run_flask)
    t.start()
    logging.info("Keep-alive server started.")

# --- Discord Bot Setup ---
# 必要なインテントを設定
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

# ボットのクライアントオブジェクトを初期化。プレフィックスは '!'
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
    # ボットが認識しているサーバー数をログに出力
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    logging.info(f"Currently in {len(bot.guilds)} guilds.")

@bot.event
async def on_guild_join(guild):
    logging.info(f"Joined {guild.name}")

#### PING COMMAND ####
# エラーの原因となっていた @bot.slash_command を @bot.command に修正
@bot.command(name="ping", description="ボットの遅延 (Ping) を計算しDMで送信するコマンド")
async def ping(ctx):
    """ボットの遅延 (Ping) を計算しDMで送信するコマンド (!ping)"""
    # コマンドメッセージを削除 (オプション)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        logging.warning("Failed to delete message: Missing 'manage_messages' permission.")
        
    member = ctx.message.author

    # bot.latency を使って、より正確なAPI遅延を取得 (秒単位 -> ミリ秒単位)
    latency_ms = round(bot.latency * 1000)

    embed=discord.Embed(title="Pong!", description=f'Ping: {latency_ms}ms', color=0x2874A6)
    
    # 応答をユーザーのDMに送信
    try:
        await member.send(embed=embed)
        # DM送信後、コマンドが実行されたチャンネルに一時的な通知を送る
        await ctx.send("Pingの結果をDMに送信しました。", delete_after=5)
    except discord.Forbidden:
        await ctx.send("DMがブロックされているか、DMが無効になっています。", delete_after=10)
        
    logging.info("Action completed: Server ping")

#### INFO COMMAND ####
@bot.command(name="info", description="指定されたユーザーまたはコマンド実行者の情報を表示するコマンド")
async def info(ctx, member: discord.Member=None):
    """指定されたユーザーまたはコマンド実行者の情報を表示するコマンド (!info <@user>)"""
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass # 削除権限がない場合は無視
        
    # ターゲットメンバーを定義
    target_member = member or ctx.author

    # 埋め込みメッセージを使用して見やすくする
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
    
    # 応答をチャンネルに送信
    await ctx.send(embed=embed, delete_after=20)
    logging.info("Action completed: User Info")

#### SERVER STATUS COMMAND ####
@bot.command(name="serverstatus", description="サーバーのステータスを表示するコマンド")
async def serverstatus(ctx):
    """サーバーのステータスを表示するコマンド (!serverstatus)"""
    guild = ctx.guild
    embed = discord.Embed(title=f"サーバー情報: {guild.name}", color=0x2874A6)
    embed.add_field(name="メンバー数", value=f"{guild.member_count}人", inline=False)
    embed.add_field(name="テキストチャンネル", value=f"{len(guild.text_channels)}", inline=True)
    embed.add_field(name="ボイスチャンネル", value=f"{len(guild.voice_channels)}", inline=True)
    embed.add_field(name="役職数", value=f"{len(guild.roles)}", inline=True)
    embed.add_field(name="サーバーオーナー", value=guild.owner.display_name if guild.owner else "不明", inline=False)
    embed.add_field(name="地域", value=str(guild.preferred_locale).upper(), inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)
    logging.info("Action completed: Server Status")

#### RANDOM NUMBER GAME ####
@bot.command(name="guess", description="1から100までの数字を当てるゲーム")
async def guess(ctx, number: int):
    """1から100までの数字を当てるゲーム (!guess <数字>)"""
    if not 1 <= number <= 100:
        await ctx.send("1から100までの数字を入力してください。", delete_after=10)
        return
        
    target_number = random.randint(1, 100)
    
    embed = discord.Embed(color=0x2874A6)

    if number == target_number:
        embed.title = "🎉 おめでとうございます！ 🎉"
        embed.description = f"正解です！あなたが当てた数字は **{target_number}** でした！"
    else:
        embed.title = "残念..."
        embed.description = f"ハズレです。正解の数字は **{target_number}** でした。もう一度挑戦してみてください！"
        
    await ctx.send(embed=embed)
    logging.info("Action completed: Guess the Number Game")

#### FAKE MESSAGE COMMAND ####
@bot.command(name="fakemessage", description="指定されたユーザーからのフェイクメッセージを送信するコマンド")
async def fakemessage(ctx, user: discord.Member, *, message: str):
    """指定されたユーザーからのフェイクメッセージを送信するコマンド (!fakemessage <@user> <メッセージ>)"""
    
    # チャンネルにWebhookを作成し、メッセージを送信後、すぐに削除する
    try:
        webhook = await ctx.channel.create_webhook(name=user.display_name)
        await webhook.send(
            message, 
            username=user.display_name, 
            avatar_url=user.avatar.url if user.avatar else None
        )
        await webhook.delete()
        
        # 元のコマンドメッセージを削除
        await ctx.message.delete()
        
        logging.info(f"Fake message sent from {user.display_name} in {ctx.channel.name}")

    except discord.Forbidden:
        await ctx.send("エラー: Webhookを作成または管理する権限がありません。", delete_after=10)
        logging.error("Missing webhook permissions for fakemessage command.")
    except Exception as e:
        await ctx.send(f"エラーが発生しました: {e}", delete_after=10)
        logging.error(f"Error in fakemessage: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    # 環境変数からトークンを直接取得
    # Render環境では、DISCORD_TOKENを環境変数として設定する必要があります。
    TOKEN = os.environ.get("DISCORD_TOKEN")

    if not TOKEN:
        # トークンがない場合はエラーを出力して終了
        logging.error("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
        # sys.exit(1) # Renderでビルドが成功したため、実行時にエラーを出すのみ
    else:
        # 1. Keep-alive サーバーを起動
        # 注: Renderで推奨されるGunicornを使用する場合、このthreadingによる起動は不要ですが、
        # アプリケーションを単純に 'python main.py' で実行する場合は必要です。
        # Renderの推奨設定に合わせて、threadingではなくgunicornで実行することを前提とします。
        # したがって、このkeep_alive()呼び出しは、もしRenderの実行コマンドが単純な 'python main.py' でない限り、コメントアウトしても安全です。
        # keep_alive() 

        # 2. Discord ボットを起動
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logging.error("ログインに失敗しました。Discord Bot Tokenが間違っている可能性があります。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

