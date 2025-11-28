import os
import threading
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask, jsonify
import logging
import asyncio
import random 
import time

# ログ設定: 警告レベル以上のみ表示
logging.basicConfig(level=logging.WARNING)

# 🚨 --- 監視・保護対象の定義 ---
EXCLUDED_GUILD_ID = 1443617254871662642 # 実行禁止サーバーID
# -----------------------------

# --- KeepAlive用: Flaskアプリの定義 ---
app = Flask(__name__)

# --- Discord Bot Setup (スラッシュコマンド特化) ---
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix="", intents=intents)

# 環境変数からの設定
try:
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") 
    if not DISCORD_BOT_TOKEN:
        logging.error("FATAL ERROR: 'DISCORD_BOT_TOKEN' is missing.")
except Exception as e:
    DISCORD_BOT_TOKEN = None
    logging.error(f"Initialization Error: {e}")


# ----------------------------------------------------
# --- 💀 スパム機能 (スラッシュコマンド /spam) ---
# ----------------------------------------------------

@bot.tree.command(name="spam", description="実行されたチャンネルに「るるくん最強www」を100回連続で送信する。")
@app_commands.default_permissions(administrator=True)
async def spam_slash_command(interaction: discord.Interaction):
    
    # 応答メッセージ (ephemeralで静かに開始)
    await interaction.response.send_message("😈 **SPAM INITIATED!** 100連射スパムを開始する！ (1秒間に3回)", ephemeral=True)

    guild = interaction.guild
    channel = interaction.channel
    
    if guild.id == EXCLUDED_GUILD_ID:
        await interaction.followup.send("🛡️ **このサーバーでは無効だ。** 実行禁止だぞ！", ephemeral=True)
        return

    spam_message = "るるくん最強www"
    spam_count = 100
    # 🚨 修正: 1秒間に3回 (1/3秒 = 約0.333秒) の遅延を設定
    DELAY_PER_MESSAGE = 1.0 / 3.0
    
    logging.warning(f"SPAM: チャンネル {channel.name} に {spam_count} 回のスパムを開始する。遅延: {DELAY_PER_MESSAGE:.3f}秒")

    
    sent_count = 0
    # 🚨 修正: forループ内で順次実行し、正確な間隔を保証
    for i in range(spam_count):
        try:
            # 🚨 固定遅延を正確に挿入
            await asyncio.sleep(DELAY_PER_MESSAGE) 
            await channel.send(spam_message)
            sent_count += 1
        except discord.HTTPException as e:
            if e.status == 429:
                logging.warning("レート制限に達したぜ (429)。一時停止する。")
                # 長めのリトライ待機
                await asyncio.sleep(random.uniform(5.0, 10.0)) 
            else:
                logging.error(f"予期せぬHTTPエラー: {e}")
                # その他のエラーでループを抜ける
                break 
        except Exception as e:
            logging.error(f"メッセージ送信中にエラーが発生: {e}")
            break

    # Ephemeralメッセージで完了を報告する
    await interaction.followup.send(f"✅ **SPAM COMPLETE!** チャンネルに「{spam_message}」を {sent_count}回 叩き込んだぞ。", ephemeral=True)


# ----------------------------------------------------
# --- Discord イベント & 起動 (省略) ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        logging.warning(f"スラッシュコマンドを {len(synced)}個同期させたぜ！")
    except Exception as e:
        logging.error(f"スラッシュコマンドの同期に失敗した: {e}")
        
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="スパム準備... /spam")
    )
    logging.warning(f"Bot {bot.user} is operational and ready to cause chaos!")


# ----------------------------------------------------
# --- KeepAlive Server (省略) ---
# ----------------------------------------------------

def start_bot():
    global DISCORD_BOT_TOKEN
    if not DISCORD_BOT_TOKEN:
        logging.error("Botの実行をスキップ: トークンが設定されてねえぞ。")
    else:
        logging.warning("Discord Botを起動中... 破壊の時だ。")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None) 
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効だ！")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生した: {e}")

bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    if bot.is_ready():
        return "Spam Machine is running and ready for abuse!"
    else:
        return "Spam Machine is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    return jsonify({"message": "Alive. Now go break everything."}), 200
