import discord
from discord import app_commands
from keep_alive import keep_alive  # ← これでWebサーバーを起動
import os

TOKEN = os.getenv("DISCORD_TOKEN")  # 環境変数にトークンを設定

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.tree.sync()
        print(f"ログインしました：{self.user}")

client = MyClient()

@client.tree.command(name="ruru", description="5回『るる』と言います！")
async def ruru(interaction: discord.Interaction):
    await interaction.response.send_message("るる " * 5)

keep_alive()  # ← Webサーバーを起動してBotを維持
client.run(MTQzNjk1Njk3NTUyNjMxODE4Mw.Gy0m0Y.REoyjB0LM6s2j0wlooz0sBNpQa45WquzmZTuDU)
