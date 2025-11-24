import os
import threading
import json
import time
import asyncio
from flask import Flask, jsonify
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import random
import logging
from datetime import datetime, timedelta
import re
import requests 
from bs4 import BeautifulSoup # 🚨 Akinator用にBeautifulSoupを追加

# ログの設定
logging.basicConfig(level=logging.INFO)

# ----------------------------------------------------
# --- 🤖 Akinator クラスの統合 (ご提示いただいたコード) ---
# ----------------------------------------------------

class AkinatorError(Exception):
    pass
    
class Akinator():
    def __init__(self,theme:str="characters",lang:str="jp",child_mode:bool=False) -> None:
        self.ENDPOINT=f"https://{lang}.akinator.com/"
        self.name=None
        self.description=None
        self.photo=None
        self.answer_id=None
        self.akitude=None
        if theme=="characters":
            sid=1
        elif theme=="objects":
            sid=2
        elif theme=="animals":
            sid=14
        else:
            raise AkinatorError("the theme must be 'characters' / 'objects' / 'animals'")
        self.json={
            "step":0,
            "progression":0.0,
            "sid":sid,
            "cm":child_mode,
            "answer":0,
        }

    def start_game(self):
        self.name=None
        self.description=None
        self.photo=None
        self.answer_id=None
        self.akitude="https://en.akinator.com/assets/img/akitudes_670x1096/defi.png"
        
        # Akinatorは日本のテーマでゲーム開始時にJSONではなくHTMLを返すため、リクエストを調整
        game=requests.post(f"{self.ENDPOINT}game",json={"sid":self.json["sid"],"cm":self.json["cm"]}).text
        soup = BeautifulSoup(game,"html.parser")
        askSoundlike=soup.find(id="askSoundlike")
        
        # 要素が見つからない場合のフォールバック処理
        if not askSoundlike:
            raise AkinatorError("Akinator game initialization failed. Could not find required session data in response.")

        question_label = soup.find(id="question-label").get_text() if soup.find(id="question-label") else "Could not retrieve question."
        session_id=askSoundlike.find(id="session").get("value")
        signature_id=askSoundlike.find(id="signature").get("value")
        
        self.json["session"]=session_id
        self.json["signature"]=signature_id
        self.step=0
        self.progression=0.0
        self.question=question_label
        return question_label

    def post_answer(self,answer:str):
        if answer=="y":
            self.json["answer"]=0
        elif answer=="n":
            self.json["answer"]=1
        elif answer=="idk":
            self.json["answer"]=2
        elif answer=="p":
            self.json["answer"]=3
        elif answer=="pn":
            self.json["answer"]=4
        else:
            raise AkinatorError("the answer must be 'y' / 'n' / 'idk' / 'p' / 'pn'")
        try:
            # 常に 'answer' エンドポイントを使用
            progression=requests.post(f"{self.ENDPOINT}answer",json=self.json)
            progression=progression.json()
            
            if progression.get("completion")=="KO":
                raise AkinatorError("completion : KO")
            elif progression.get("completion")=="SOUNDLIKE":
                raise AkinatorError("completion : SOUNDLIKE")
                
            if "name_proposition" in progression:
                # 推測結果
                self.name=progression["name_proposition"]
                self.description=progression["description_proposition"]
                self.photo=progression["photo"]
                self.answer_id=progression["id_proposition"]
                self.json["step_last_proposition"]=int(self.json["step"])
            else:
                # 次の質問
                self.json["step"]=int(progression["step"])
                self.json["progression"]=float(progression["progression"])
                self.step=int(progression["step"])
                self.progression=float(progression["progression"])
                self.question=progression["question"]
                self.question_id=progression["question_id"]
                self.akitude=f"https://en.akinator.com/assets/img/akitudes_670x1096/{progression['akitude']}"
                
            return progression
        except Exception as e:
            # logging.error(f"Akinator post_answer error: {e}, Response: {progression}")
            raise AkinatorError(f"Akinator API Error: {e}")

    def go_back(self):
        self.name=None
        self.description=None
        self.photo=None
        self.answer_id=None
        if self.json["step"]==0:
            raise AkinatorError("it's first question")
        if "answer" in self.json:
            del self.json["answer"]
        try:
            goback=requests.post(f"{self.ENDPOINT}cancel_answer",json=self.json)
            goback=goback.json()
            self.json["step"]=int(goback["step"])
            self.json["progression"]=float(goback["progression"])
            self.step=int(goback["step"])
            self.progression=float(goback["progression"])
            self.question=goback["question"]
            self.question_id=goback["question_id"]
            self.akitude=f"https://en.akinator.com/assets/img/akitudes_670x1096/{goback['akitude']}"
            return goback
        except Exception as e:
            raise AkinatorError(f"Akinator go_back error: {e}")

    def exclude(self):
        self.name=None
        self.description=None
        self.photo=None
        self.answer_id=None
        if "answer" in self.json:
            del self.json["answer"]
        try:
            exclude=requests.post(f"{self.ENDPOINT}exclude",json=self.json)
            exclude=exclude.json()
            self.json["step"]=int(exclude["step"])
            self.json["progression"]=float(exclude["progression"])
            self.step=int(exclude["step"])
            self.progression=float(exclude["progression"])
            self.question=exclude["question"]
            self.question_id=exclude["question_id"]
            self.akitude=f"https://en.akinator.com/assets/img/akitudes_670x1096/{exclude['akitude']}"
            return exclude
        except Exception as e:
            raise AkinatorError(f"Akinator exclude error: {e}")

# ----------------------------------------------------
# --- Bot Setup (Flask, Intents, Globals) ---
# ----------------------------------------------------

# ... (既存のFlaskアプリ、Intents、Bot設定、環境変数処理のコードが続きます)

app = Flask(__name__)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True          
intents.message_content = True  
intents.moderation = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの初期設定 (省略)

# --- 🧑‍💻 コマンド実行許可ユーザーID (指定されたIDのみ) ---
ALLOWED_USER_IDS = [
    1420826924145442937, 
]


# ----------------------------------------------------
# --- 🎮 Akinator ゲーム状態管理 ---
# ----------------------------------------------------
# チャンネルIDまたはユーザーIDをキーとしてAkinatorインスタンスを格納
active_akinator_games = {} # {channel_id: Akinator_instance}
# テキスト応答を有効にするための対応表
AKINATOR_TEXT_ANSWERS = {
    "y": "y", "はい": "y", "yes": "y",
    "n": "n", "いいえ": "n", "no": "n",
    "idk": "idk", "わからない": "idk", "わからん": "idk",
    "p": "p", "たぶん": "p", "probably": "p",
    "pn": "pn", "たぶんちがう": "pn", "not really": "pn",
    "戻る": "back", "back": "back" # 特殊処理
}


# --- 💰 エコノミーシステム設定 (インメモリ) ---
user_wallets = {}  
# ... (既存のCOIN設定、SHOP_ITEMSの定義が続きます)


# --- ヘルパー関数群 ---
# ... (get_next_warn_id, send_log, is_allowed_userなどの定義が続きます)

def is_allowed_user():
    """ALLOWED_USER_IDSに含まれるユーザーのみが実行を許可されるカスタムチェック"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id in ALLOWED_USER_IDS:
            return True
        
        await interaction.response.send_message(
            "❌ あなたにはこのコマンドを実行する権限がありません。", 
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)


# --- 🎫 チケットシステムのView定義 ---
# ... (CloseTicketView, TicketViewの定義が続きます)


# --- 💰 VCアクティビティチェックタスク ---
# ... (check_vc_activityの定義が続きます)


# ----------------------------------------------------
# --- イベントと同期 ---
# ----------------------------------------------------

@bot.event
async def on_ready():
    # ... (Bot起動時の処理)
    pass

@bot.event
async def on_message(message):
    
    if message.author.bot or message.guild is None or not message.content:
        await bot.process_commands(message)
        return
        
    content = message.content.lower().strip()
    channel_id = message.channel.id
    
    # ------------------------------------
    # 3. 🎮 Akinator コマンドモード処理
    # ------------------------------------
    if channel_id in active_akinator_games:
        aki = active_akinator_games[channel_id]
        raw_answer = AKINATOR_TEXT_ANSWERS.get(content)
        
        if raw_answer:
            await message.delete() # 応答を消してクリーンに保つ
            await handle_akinator_answer(message.channel, aki, raw_answer)
            return

    # ------------------------------------
    # 1. 自動モデレーション処理
    # ------------------------------------
    # ... (既存のモデレーション処理が続きます)
        
    # ------------------------------------
    # 2. 💰 テキストチャットでのコイン獲得
    # ------------------------------------
    # ... (既存のコイン獲得処理が続きます)
        
    await bot.process_commands(message)

# ----------------------------------------------------
# --- Akinatorのヘルパー関数 ---
# ----------------------------------------------------

def create_akinator_embed(aki: Akinator, question_text: str = None, color: discord.Color = discord.Color.blue()):
    """Akinatorの質問/結果をDiscord Embedとして作成"""
    
    embed = discord.Embed(
        title=f"❓ ステップ {aki.step}: {question_text or aki.question}",
        description=f"**進行度:** {aki.progression:.2f}%\n",
        color=color
    )
    embed.set_thumbnail(url=aki.akitude or "https://en.akinator.com/assets/img/akitudes_670x1096/defi.png")
    embed.set_footer(text="回答: はい/いいえ/わからない/たぶん/たぶんちがう (または y/n/idk/p/pn)。 '戻る'で前の質問へ。")
    return embed

async def handle_akinator_answer(channel: discord.TextChannel, aki: Akinator, answer: str):
    """Akinatorの回答を処理し、次の状態をチャンネルに送信する"""
    
    try:
        if answer == "back":
            aki.go_back()
            embed = create_akinator_embed(aki, question_text=f"ステップ {aki.step} に戻りました")
            await channel.send(embed=embed, view=AkinatorView(channel.id))
            return

        aki.post_answer(answer)
        
        if aki.name:
            # 推測結果が出た場合
            embed = discord.Embed(
                title=f"💡 判明しました! 私が考えていたのは...",
                description=f"**{aki.name}**\n\n*{aki.description}*",
                color=discord.Color.green()
            )
            if aki.photo: embed.set_image(url=aki.photo)
            
            await channel.send(embed=embed)
            del active_akinator_games[channel.id]
            
        else:
            # 次の質問
            embed = create_akinator_embed(aki)
            await channel.send(embed=embed, view=AkinatorView(channel.id))
            
    except AkinatorError as e:
        await channel.send(f"❌ Akinatorエラー: {e}", delete_after=10)
    except Exception as e:
        await channel.send(f"❌ 予期せぬエラーが発生しました: {e}", delete_after=10)
        del active_akinator_games[channel.id]
        
        
class AkinatorView(ui.View):
    """Akinatorのボタン回答UI"""
    def __init__(self, channel_id: int):
        super().__init__(timeout=180) # 3分でタイムアウト
        self.channel_id = channel_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel_id != self.channel_id:
            await interaction.response.send_message("❌ このボタンは現在のゲーム専用です。", ephemeral=True)
            return False
        return True

    @ui.button(label="はい", style=discord.ButtonStyle.green, custom_id="aki_y")
    async def button_yes(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        aki = active_akinator_games.get(self.channel_id)
        if aki: await handle_akinator_answer(interaction.channel, aki, "y")

    @ui.button(label="いいえ", style=discord.ButtonStyle.red, custom_id="aki_n")
    async def button_no(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        aki = active_akinator_games.get(self.channel_id)
        if aki: await handle_akinator_answer(interaction.channel, aki, "n")

    @ui.button(label="わからない", style=discord.ButtonStyle.gray, custom_id="aki_idk")
    async def button_idk(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        aki = active_akinator_games.get(self.channel_id)
        if aki: await handle_akinator_answer(interaction.channel, aki, "idk")

    @ui.button(label="戻る", style=discord.ButtonStyle.blurple, custom_id="aki_back")
    async def button_back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        aki = active_akinator_games.get(self.channel_id)
        if aki: await handle_akinator_answer(interaction.channel, aki, "back")
        
    async def on_timeout(self):
        aki = active_akinator_games.pop(self.channel_id, None)
        if aki:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                await channel.send("⏰ Akinatorゲームがタイムアウトしました。ゲームを終了します。", delete_after=10)


# ----------------------------------------------------
# --- スラッシュコマンドの定義 ---
# ----------------------------------------------------

# --- 🎮 Akinator コマンド ---

@bot.tree.command(name="akinator", description="Akinatorゲームを開始します。")
@app_commands.describe(theme="テーマを選択")
@app_commands.choices(theme=[
    app_commands.Choice(name="キャラクター", value="characters"),
    app_commands.Choice(name="物体", value="objects"),
    app_commands.Choice(name="動物", value="animals"),
])
@is_allowed_user() # 🚨 実行を許可されたIDのみ使用可能 🚨
async def akinator_slash(interaction: discord.Interaction, theme: str = "characters"):
    await interaction.response.defer(thinking=True)
    channel_id = interaction.channel.id

    if channel_id in active_akinator_games:
        await interaction.followup.send("❌ このチャンネルでは既にAkinatorゲームが進行中です。", ephemeral=True)
        return

    try:
        aki = Akinator(theme=theme, lang="jp")
        first_question = aki.start_game()
        
        active_akinator_games[channel_id] = aki
        
        embed = create_akinator_embed(aki, question_text=f"Akinator ({theme}) ゲーム開始!")
        
        await interaction.followup.send(embed=embed, view=AkinatorView(channel_id))

    except AkinatorError as e:
        await interaction.followup.send(f"❌ Akinatorゲームの開始に失敗しました: {e}", ephemeral=True)
    except Exception as e:
        logging.error(f"Akinator開始時の予期せぬエラー: {e}")
        await interaction.followup.send("❌ 予期せぬエラーが発生しました。", ephemeral=True)


@bot.tree.command(name="akinator_end", description="現在のAkinatorゲームを強制終了します。")
@is_allowed_user()
async def akinator_end_slash(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    if channel_id in active_akinator_games:
        del active_akinator_games[channel_id]
        await interaction.response.send_message("✅ Akinatorゲームを終了しました。", ephemeral=False)
    else:
        await interaction.response.send_message("❌ このチャンネルで進行中のAkinatorゲームはありません。", ephemeral=True)


# --- その他のスラッシュコマンド (既存のコード) ---

@bot.tree.command(name="help", description="利用可能なコマンド一覧を表示します。")
@is_allowed_user()
async def help_slash(interaction: discord.Interaction):
    # ... (処理内容省略)
    pass 

# ... (既存の member_log_toggle, ticket, nuke, warn, fakemessage などのコマンドが続きます)

@bot.tree.command(name="balance", description="現在のコイン残高を確認します。")
async def balance_slash(interaction: discord.Interaction):
    # ... (処理内容省略 - 誰でも利用可能)
    pass

@bot.tree.command(name="shop", description="サーバーショップの商品リストを表示します。")
@is_allowed_user()
async def shop_slash(interaction: discord.Interaction):
    # ... (処理内容省略)
    pass

@bot.tree.command(name="buy", description="指定された商品（役職）を購入します。")
@is_allowed_user()
async def buy_slash(interaction: discord.Interaction, item_id: str):
    # ... (処理内容省略)
    pass

@bot.tree.command(name="eco", description="経済システムを管理します。")
@app_commands.default_permissions(administrator=True) 
class EcoAdminCommands(app_commands.Group):
    # ... (処理内容省略 - 制限付き)
    pass


# ----------------------------------------------------
# --- KeepAlive Server & Main Execution ---
# ----------------------------------------------------

def start_bot():
    # ... (Bot起動ロジック)
    pass

# ... (Flaskアプリの定義と実行ロジックが続きます)
