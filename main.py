import os
import threading
import discord
from discord import app_commands
from flask import Flask

# --- Flask (Webサーバー) の設定 ---
# Renderでボットを常時稼働させるためのWebサーバー部分
app = Flask('')

@app.route('/')
def home():
    """UptimeRobotからのアクセスに応答し、ボットが生きていることを示す"""
    return "Bot is running and keeping awake!"

def run_flask():
    """Flaskサーバーを別スレッドで起動する関数"""
    # Renderの環境変数PORTがあればそれを使用、なければ5000
    port = os.environ.get('PORT', 5000) 
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Flaskサーバーを起動し、ボットのメイン処理と並行して実行する"""
    t = threading.Thread(target=run_flask)
    t.start()
    print("Keep-alive server started.")

# --- Discord Bot の設定 ---
# サーバー管理機能を使うため、members Intentを有効にします。
# Discord開発者ポータルのBot設定で 'SERVER MEMBERS INTENT' を有効にしてください。
intents = discord.Intents.default()
intents.members = True 
intents.guilds = True # サーバー情報アクセスに必要

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        # スラッシュコマンドをDiscordに登録
        await self.tree.sync() 
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

client = MyClient(intents=intents)

# --- 確認ボタンの実装 (チャンネル削除用) ---

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, category: discord.CategoryChannel):
        super().__init__(timeout=60) # 60秒でタイムアウト
        self.category = category

    @discord.ui.button(label="削除を実行", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 実行ボタンを押したユーザーがコマンド実行者であることを確認
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("この操作はコマンドを実行したユーザーのみが行えます。", ephemeral=True)
            return
        
        # ボタンを無効化
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        await interaction.response.edit_message(content=f"🗑️ 削除を開始します: カテゴリー **{self.category.name}**...")
        
        deleted_count = 0
        
        # チャンネルの削除実行
        for channel in self.category.channels:
            try:
                await channel.delete()
                deleted_count += 1
            except Exception as e:
                print(f"チャンネル {channel.name} の削除中にエラーが発生しました: {e}")
                
        await interaction.followup.edit_message(
            interaction.message.id,
            content=f"✅ 削除完了: カテゴリー **{self.category.name}** 内の **{deleted_count}** 個のチャンネルを削除しました。"
        )
        self.stop()

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("この操作はコマンドを実行したユーザーのみが行えます。", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("操作をキャンセルしました。", ephemeral=True)
        self.stop()

# --- 確認ボタンの実装 (ロール削除用) ---

class ConfirmDeleteRolesView(discord.ui.View):
    def __init__(self, roles_to_delete: list[discord.Role], role_name: str):
        super().__init__(timeout=60)
        self.roles_to_delete = roles_to_delete
        self.role_name = role_name

    @discord.ui.button(label="削除を実行", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("この操作はコマンドを実行したユーザーのみが行えます。", ephemeral=True)
            return
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.edit_message(content=f"🗑️ 削除を開始します: 名前が **{self.role_name}** のロール...")

        deleted_count = 0
        
        for role in self.roles_to_delete:
            try:
                # 削除しようとしているロールがボットより上位でないか、@everyoneでないかを確認
                if role < interaction.guild.me.top_role and role.name != "@everyone":
                    await role.delete()
                    deleted_count += 1
                else:
                    print(f"ロール {role.name} はボットの権限より上位、または @everyone なので削除できませんでした。")
            except Exception as e:
                print(f"ロール {role.name} の削除中にエラーが発生しました: {e}")
                
        await interaction.followup.edit_message(
            interaction.message.id,
            content=f"✅ 削除完了: 名前が **{self.role_name}** のロールを **{deleted_count}** 個削除しました。"
        )
        self.stop()

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("この操作はコマンドを実行したユーザーのみが行えます。", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("操作をキャンセルしました。", ephemeral=True)
        self.stop()

# --- スラッシュコマンドの定義 ---

@client.tree.command(name="cleanup-channels", description="指定されたカテゴリー内の全てのチャンネルを削除します（管理者専用）。")
@app_commands.checks.has_permissions(administrator=True) # 管理者権限を持つユーザーのみ実行可能
async def cleanup_channels_command(interaction: discord.Interaction, category: discord.CategoryChannel):
    """/cleanup-channelsコマンドが実行された時の処理"""
    
    # 確認メッセージを送信
    await interaction.response.send_message(
        f"カテゴリー '{category.name}' ({len(category.channels)}個のチャンネル) の削除を開始します。本当に実行しますか？", 
        view=ConfirmDeleteView(category=category),
        ephemeral=True # 実行者にのみ表示
    )

@client.tree.command(name="cleanup-roles", description="指定された名前を持つ全てのロールを削除します（管理者専用）。")
@app_commands.checks.has_permissions(administrator=True) # 管理者権限を持つユーザーのみ実行可能
async def cleanup_roles_command(interaction: discord.Interaction, role_name: str):
    """/cleanup-rolesコマンドが実行された時の処理"""
    
    # 指定された名前に一致するロールをリストアップ
    roles_to_delete = [
        role for role in interaction.guild.roles 
        if role.name == role_name and role.name != "@everyone"
    ]

    if not roles_to_delete:
        await interaction.response.send_message(f"名前が '{role_name}' のロールは見つかりませんでした。", ephemeral=True)
        return

    await interaction.response.send_message(
        f"名前が '{role_name}' のロール ({len(roles_to_delete)}個) の削除を開始します。本当に実行しますか？", 
        view=ConfirmDeleteRolesView(roles_to_delete=roles_to_delete, role_name=role_name),
        ephemeral=True
    )

# --- メイン実行部分 ---
if __name__ == "__main__":
    # 環境変数からトークンを取得
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if not TOKEN:
        print("エラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        # Webサーバーを別スレッドで起動
        keep_alive()
        
        # Discordボットを起動
        client.run(TOKEN)
