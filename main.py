import os
import threading
import json
import time
import asyncio
from flask import Flask, jsonify
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import datetime, timedelta
import re
import requests # API呼び出しのためにrequestsをインポート

# ログの設定
logging.basicConfig(level=logging.INFO)

# --- 🚨 Gunicorn対応: Flaskアプリの定義を最上位に移動 🚨 ---
app = Flask(__name__)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True          # メンバー情報やログに必須
intents.message_content = True  # メッセージの内容を読むために必須
intents.moderation = True
intents.presences = True

# ボットのクライアントオブジェクトを初期化
bot = commands.Bot(command_prefix="!", intents=intents)

# 環境変数からの初期設定
try:
    GLOBAL_VC_CHANNEL_ID = int(os.environ.get("LOG_VC_CHANNEL_ID", 0))
    GLOBAL_MEMBER_CHANNEL_ID = int(os.environ.get("LOG_MEMBER_CHANNEL_ID", 0))
    GLOBAL_CONFIG_CHANNEL_ID = int(os.environ.get("LOG_CONFIG_CHANNEL_ID", 0))
    WELCOME_CHANNEL_ID = int(os.environ.get("WELCOME_CHANNEL_ID", 0))
except ValueError:
    GLOBAL_VC_CHANNEL_ID = 0
    GLOBAL_MEMBER_CHANNEL_ID = 0
    GLOBAL_CONFIG_CHANNEL_ID = 0
    WELCOME_CHANNEL_ID = 0
    logging.warning("環境変数ログチャンネルIDの初期値が無効な数値です。")

# ボット実行中に使用されるグローバル変数 (動的に変更される)
LOG_VC_CHANNEL_ID = GLOBAL_VC_CHANNEL_ID
LOG_MEMBER_CHANNEL_ID = GLOBAL_MEMBER_CHANNEL_ID
LOG_CONFIG_CHANNEL_ID = GLOBAL_CONFIG_CHANNEL_ID # 詳細ログとBot操作ログのメインチャンネル

# フラグはIDの有無に基づいて動的に更新
LOG_VC_ENABLED = (LOG_VC_CHANNEL_ID != 0) 
LOG_MEMBER_JOIN_LEAVE_ENABLED = (LOG_MEMBER_CHANNEL_ID != 0)
LOG_CONFIG_ENABLED = (LOG_CONFIG_CHANNEL_ID != 0) 


# --- Carl-bot風 データストア (インメモリ/Bot再起動でリセット) ---
warn_history = {} 
REACTION_ROLE_MSG_ID = 0
REACTION_ROLE_MAP = {
    "🎮": "ゲーマー",
    "📢": "通知受け取り",
    "💡": "アイデア出し"
}

# --- AI応答機能のグローバル設定 ---
AI_ENABLED_CHANNELS = set() 

# --- 自動モデレーション設定 ---
# スパム検知用データストア (メッセージ内容とタイムスタンプ)
SPAM_HISTORY = {} # {user_id: [(content, timestamp), ...]}
SPAM_THRESHOLD_COUNT = 3  # 5秒以内に3回
SPAM_THRESHOLD_TIME_SECONDS = 5
MENTION_SPAM_THRESHOLD = 5 # メンション数

# NGワードリスト (小文字で定義)
FORBIDDEN_WORDS = [
    "f*ck", "shit", "d*mn", "c*nt", # 英語の禁止語句例
    "死ね", "殺す", "きもい", "うざい", # 日本語の禁止語句例
    "広告", "宣伝", "投資勧誘" # スパム/商用ワード例
]

# --- 🌟 Venice AI API 設定 🌟 ---
# 環境変数 VENICE_API_KEY からキーを読み込むことを推奨
VENICE_API_KEY = os.environ.get("VENICE_API_KEY", os.environ.get("API_KEY", "")) 
VENICE_API_URL = "https://api.venice.ai/v1/chat/completions" # Venice AIの互換エンドポイント
VENICE_MODEL = "v-deepseek-70b" # 利用したいVenice AIのモデル名
MAX_RETRIES = 5                  # リトライ回数はそのまま維持


# --- 警告システム用ヘルパー関数 ---
def get_next_warn_id(user_id):
    """ユーザーの次の警告IDを計算する"""
    if user_id not in warn_history:
        return 1
    return max([w['id'] for w in warn_history[user_id]]) + 1

# ログタイプに応じてチャンネルIDを取得するヘルパー関数
def get_log_channel_id(log_type: str) -> int:
    """ログタイプに基づいて、有効なログチャンネルIDを返します。"""
    global LOG_VC_CHANNEL_ID, LOG_MEMBER_CHANNEL_ID, LOG_CONFIG_CHANNEL_ID
    global LOG_VC_ENABLED, LOG_MEMBER_JOIN_LEAVE_ENABLED, LOG_CONFIG_ENABLED

    if log_type == "vc" and LOG_VC_ENABLED:
        return LOG_VC_CHANNEL_ID
    if log_type == "member" and LOG_MEMBER_JOIN_LEAVE_ENABLED:
        return LOG_MEMBER_CHANNEL_ID
    # config (メッセージ編集/削除, ロール, サーバー設定) と moderation (Bot操作) は同じチャンネル
    if (log_type == "config" or log_type == "moderation") and LOG_CONFIG_ENABLED:
        return LOG_CONFIG_CHANNEL_ID
    return 0

# ログ送信関数 (色指定を可能に)
async def send_log(guild, title, description, fields, color=discord.Color.blue(), moderator=None, log_type="moderation"):
    """
    指定された情報をログチャンネルに送信します。
    log_type: "vc", "member", "config", "moderation"
    """
    log_id = get_log_channel_id(log_type)
    
    if log_id != 0:
        if guild is not None:
            log_channel = guild.get_channel(log_id)
        else:
            log_channel = bot.get_channel(log_id)
            
        if log_channel:
            log_embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now()
            )
            
            # --- Bot操作ログの追加 ---
            if moderator and LOG_CONFIG_ENABLED and log_type == "moderation":
                fields.insert(0, ("🧑‍💻 Bot操作実行者", moderator.mention, False))

            for name, value, inline in fields:
                if value:
                    value_str = str(value)
                    if len(value_str) > 1024:
                        value_str = value_str[:1020] + "..."
                    log_embed.add_field(name=name, value=value_str, inline=inline)
            
            try:
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                logging.error(f"ログチャンネル ({log_id}) への送信権限がありません。")

# --- 更新ログ送信関数 ---
async def send_update_log(bot_instance, title, version, changes_list, target_channel: discord.TextChannel, color=discord.Color.gold()):
    """
    指定されたチャンネルにBotの更新ログを送信します。
    """
    if target_channel is None:
        logging.warning("送信先チャンネルが指定されていません。更新ログは送信されません。")
        return
        
    update_channel = target_channel
    
    if update_channel:
        # 変更点をリストとしてフォーマット
        formatted_changes = "\n".join([f"• {change}" for change in changes_list])
        description = f"**バージョン: {version}**\n\n**変更点:**\n{formatted_changes}"
        
        update_embed = discord.Embed(
            title=f"🚀 Bot更新ログ: {title}",
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        update_embed.set_footer(text="管理者によって通知されました。")
        
        try:
            await update_channel.send(embed=update_embed)
            logging.info(f"Bot更新ログをチャンネル {update_channel.id} に送信しました。")
        except discord.Forbidden:
            logging.error(f"更新ログチャンネル ({update_channel.id}) への送信権限がありません。")

# 同期API呼び出しのヘルパー関数 (Venice/OpenAI互換)
def sync_gemini_api_call(api_url, headers, payload):
    """requestsを使用してAPIを同期的に呼び出し、レスポンスのJSONを返します。"""
    # requestsモジュールは既にトップレベルでインポートされています
    response = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=20) # タイムアウトを20秒に設定
    response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
    return response.json()

# --- 🌟 Venice AI 呼び出し関数 (非同期/指数バックオフ付き) 🌟 ---
async def call_venice_api(prompt: str) -> str:
    """
    Venice AI Chat Completions APIを呼び出し、応答テキストを取得します。
    OpenAI互換の形式を使用します。
    """
    global VENICE_API_KEY, VENICE_API_URL, VENICE_MODEL
    
    if not VENICE_API_KEY:
        return "エラー: Venice AI APIキーが設定されていません。環境変数をご確認ください。"

    # ヘッダー (OpenAI互換)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {VENICE_API_KEY}'
    }

    # OpenAI互換のChat Completions APIペイロード
    payload = {
        "model": VENICE_MODEL,
        "messages": [
            # システムインストラクション
            {"role": "system", "content": "あなたはフレンドリーで親切なDiscordボットです。日本語で、質問に対して正確かつ有用な情報を提供します。"},
            # ユーザーのプロンプト
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            logging.debug(f"API呼び出し試行 {attempt + 1}/{MAX_RETRIES}...")

            # 同期処理をスレッドプールエグゼキュータで非同期に実行
            result = await bot.loop.run_in_executor(
                None,  # デフォルトのエグゼキュータを使用
                sync_gemini_api_call, # requestsによるPOST呼び出し関数を流用
                VENICE_API_URL,
                headers,
                payload
            )
            
            # --- 成功時の処理: OpenAI互換レスポンスのパース ---
            if result.get('choices'):
                text = result['choices'][0]['message']['content']
                return text

            return "AIからの応答を抽出できませんでした。（JSON形式が予期せぬものでした）"

        except requests.exceptions.HTTPError as e:
            # 4xx (クライアントエラー) や 5xx (サーバーエラー) のHTTPエラーを捕捉
            logging.error(f"HTTPエラーが発生しました (コード: {e.response.status_code}): {e.response.text}")
            if e.response.status_code in [400, 401, 403, 404]:
                 return f"APIエラーが発生しました (コード: {e.response.status_code})。Venice AI APIキーやモデル名を確認してください。"

        except requests.exceptions.RequestException as e:
            # 接続エラー、DNSエラー、タイムアウトなど、requestsに関連する一般的なエラーを捕捉
            logging.error(f"リクエストエラーが発生しました ({e.__class__.__name__}): {e}")

        except Exception as e:
            # JSONデコードエラーなど、予期せぬその他のエラーを捕捉
            logging.error(f"Venice AI API呼び出し中に予期せぬエラーが発生しました: {e}")

        # リトライロジック
        if attempt < MAX_RETRIES - 1:
            delay = 2 ** attempt
            logging.warning(f"リトライします ({attempt + 1}/{MAX_RETRIES}、{delay}秒後)...")
            await asyncio.sleep(delay)
        else:
            return "APIへの接続が最大リトライ回数を超えて失敗しました。時間を置いて再度お試しください。"
    
    return "API呼び出しの最終的な試行に失敗しました。"


# --- 自動モデレーション機能のヘルパー関数 ---

def is_mention_spam(message: discord.Message) -> bool:
    """メッセージがメンションスパムの閾値を超えているかチェックする"""
    # ユーザーとロールへのメンションの合計数が閾値を超えているか
    return len(message.mentions) + len(message.role_mentions) > MENTION_SPAM_THRESHOLD

async def is_repeat_spam(message: discord.Message) -> bool:
    """5秒以内に同じ内容のメッセージを3回以上繰り返しているかチェックする"""
    user_id = message.author.id
    now = datetime.now()
    
    # 履歴から古いエントリを削除 (5秒以上前のもの)
    if user_id in SPAM_HISTORY:
        SPAM_HISTORY[user_id] = [
            (content, timestamp) for content, timestamp in SPAM_HISTORY[user_id] 
            if (now - timestamp).total_seconds() < SPAM_THRESHOLD_TIME_SECONDS
        ]

    # 現在のメッセージを追加
    content_key = message.content.strip().lower() # 大文字・小文字を区別せず、スペースを無視
    SPAM_HISTORY.setdefault(user_id, []).append((content_key, now))
    
    # 同じ内容のメッセージの数をカウント
    recent_messages = [content for content, _ in SPAM_HISTORY[user_id]]
    
    # 最後のメッセージと同じ内容の連続数 (厳密な繰り返しスパム検知)
    repeat_count = 0
    for content in reversed(recent_messages):
        if content == content_key:
            repeat_count += 1
        else:
            break

    # 履歴を綺麗に保つために、カウントに関係なく、古いエントリは定期的に削除
    # ただし、同じ内容のメッセージが連続して閾値を超えた場合にTrueを返す
    return repeat_count >= SPAM_THRESHOLD_COUNT

def contains_forbidden_word(content: str) -> str | None:
    """メッセージがNGワードを含んでいるかチェックする。含まれている場合、そのNGワードを返す。"""
    lower_content = content.lower().strip()
    for word in FORBIDDEN_WORDS:
        if word in lower_content:
            return word
    return None

# --- イベントと同期 ---

@bot.event
async def on_ready():
    """ボット起動時に実行される処理。スラッシュコマンドの同期を行います。"""
    # --- 修正箇所: ステータスを "/help" に変更 ---
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="/help")
    )
    # ---------------------------------------------
    logging.info("Bot is ready!")
    
    # スラッシュコマンドの同期 (既存ロジック)
    GUILD_ID_STR = os.environ.get("GUILD_ID")
    if GUILD_ID_STR:
        try:
            guild_id = int(GUILD_ID_STR)
            guild = bot.get_guild(guild_id)
            if guild:
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                logging.info(f"指定ギルド ({guild.name}) でスラッシュコマンドを同期しました。登録数: {len(synced)}")
            else:
                synced = await bot.tree.sync()
                logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")
        except Exception as e:
            logging.error(f"スラッシュコマンドの同期中にエラーが発生しました: {e}")
    else:
        try:
            synced = await bot.tree.sync()
            logging.info(f"グローバルでスラッシュコマンドを同期しました。登録数: {len(synced)}")
        except Exception as e:
            logging.error(f"グローバル同期中にエラーが発生しました: {e}")

# --- AI応答機能と自動モデレーションのメインロジック (on_message) ---

@bot.event
async def on_message(message):
    """メッセージを受信した際の処理。自動モデレーションとAI応答を処理します。"""
    
    if message.author.bot or message.guild is None or not message.content:
        await bot.process_commands(message)
        return

    # ------------------------------------
    # 1. 自動モデレーション処理 (AI応答より前に実行)
    # ------------------------------------
    try:
        # A. メンションスパムの検知
        if is_mention_spam(message):
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} メンションスパムを検知しました。メッセージが削除されました。", delete_after=5)
            await send_log(message.guild, "❌ メンションスパム削除", f"{message.author.mention} のメッセージがメンションスパムとして削除されました。",
                           [("チャンネル", message.channel.mention, True), ("メンション数", str(len(message.mentions) + len(message.role_mentions)), True), ("メッセージ内容", message.content, False)],
                           discord.Color.red(), log_type="moderation")
            return # 削除したら以降の処理を停止

        # B. NGワードフィルター
        forbidden_word = contains_forbidden_word(message.content)
        if forbidden_word:
            await message.delete()
            await message.channel.send(f"🛑 {message.author.mention} NGワードの使用が検知されました。メッセージが削除されました。", delete_after=5)
            await send_log(message.guild, "❌ NGワード削除", f"{message.author.mention} のメッセージがNGワードとして削除されました。",
                           [("チャンネル", message.channel.mention, True), ("検知ワード", forbidden_word, True), ("メッセージ内容", message.content, False)],
                           discord.Color.red(), log_type="moderation")
            return # 削除したら以降の処理を停止

        # C. 繰り返しスパムの検知
        if await is_repeat_spam(message):
            # メッセージを削除する代わりに、警告とタイムアウトを課すなど、より重い処理も可能だが、
            # ここではシンプルにメッセージを削除
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention} 繰り返しスパムを検知しました。メッセージが削除されました。", delete_after=5)
            await send_log(message.guild, "❌ 繰り返しスパム削除", f"{message.author.mention} のメッセージが繰り返しスパムとして削除されました。",
                           [("チャンネル", message.channel.mention, True), ("メッセージ内容", message.content, False)],
                           discord.Color.red(), log_type="moderation")
            return # 削除したら以降の処理を停止

    except discord.Forbidden:
        logging.warning("モデレーション失敗: Botにメッセージ削除権限がありません。")
    except Exception as e:
        logging.error(f"自動モデレーション処理中にエラーが発生しました: {e}")
        
    # ------------------------------------
    # 2. AI応答処理
    # ------------------------------------
    if message.channel.id in AI_ENABLED_CHANNELS:
        try:
            # 🌟 修正箇所: async with を使用して、安全にタイピングインジケータを開始・終了します
            async with message.channel.typing():
                logging.info(f"AI処理開始: チャンネルID {message.channel.id}, ユーザー: {message.author.name}")
                # Venice AI の呼び出し
                ai_response_text = await call_venice_api(message.content)
            
            # async with ブロックを抜けると、タイピングは自動的に停止される

            if len(ai_response_text) > 2000:
                # 2000文字を超える場合は切り詰める
                await message.reply(ai_response_text[:1990] + "...")
            else:
                await message.reply(ai_response_text)
            
            logging.info(f"AI処理完了: チャンネルID {message.channel.id}")

        except Exception as e:
            # 例外が発生した場合も async with ブロックは安全に終了する
            logging.error(f"AI応答処理中の外部エラーが発生しました (on_message): {e}")
            await message.channel.send("AI応答中にエラーが発生しました。時間を置いて再度お試しください。")

    await bot.process_commands(message)

# --- サーバー参加/脱退ログ (LOG_MEMBER_JOIN_LEAVE_ENABLED 制御) ---

@bot.event
async def on_member_join(member):
    """メンバー参加時のウェルカムメッセージを送信し、ログを記録"""
    if member.guild is None: return

    # ログ送信 (log_type="member"を指定)
    if LOG_MEMBER_JOIN_LEAVE_ENABLED:
        await send_log(
            member.guild,
            "メンバー参加ログ",
            f"新しいメンバーが参加しました: {member.mention}",
            [
                ("ユーザー名", member.name, True), 
                ("アカウント作成日", member.created_at.strftime('%Y/%m/%d %H:%M:%S'), False)
            ],
            discord.Color.green(),
            log_type="member"
        )
    
    # ウェルカムメッセージの送信 (ログ機能とは独立して動作)
    if WELCOME_CHANNEL_ID != 0:
        welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            welcome_message = (
                f"🎉 **{member.mention}** さん、**{member.guild.name}** へようこそ！ 🎉\n"
                f"あなたはサーバーの**{len(member.guild.members)}**人目のメンバーです。\n"
                "ルールを確認して、楽しい時間を過ごしましょう！"
            )
            try: await welcome_channel.send(welcome_message)
            except discord.Forbidden: logging.warning("挨拶チャンネルへの送信権限がありません。")

@bot.event
async def on_member_remove(member):
    """メンバー脱退時のグッバイメッセージを送信し、ログを記録"""
    if member.guild is None: return
    
    # ログ送信 (log_type="member"を指定)
    if LOG_MEMBER_JOIN_LEAVE_ENABLED:
        await send_log(
            member.guild,
            "メンバー脱退ログ",
            f"{member.mention} ({member.id}) がサーバーを去りました。",
            [("ユーザー名", member.name, True)],
            discord.Color.orange(),
            log_type="member"
        )

# --- VC活動ログ (LOG_VC_ENABLED 制御) ---

@bot.event
async def on_voice_state_update(member, before, after):
    """ボイスチャンネルの参加、退出、移動を追跡します。"""
    if not LOG_VC_ENABLED: return
    
    # 参加 (before.channel が None で、after.channel が None でない)
    if before.channel is None and after.channel is not None:
        await send_log(
            member.guild,
            "🗣️ VC参加ログ",
            f"{member.mention} がVCに参加しました。",
            [
                ("VCチャンネル", after.channel.mention, True),
                ("ユーザーID", str(member.id), True)
            ],
            discord.Color.lighter_grey(),
            log_type="vc"
        )
    
    # 退出 (before.channel が None でなく、after.channel が None)
    elif before.channel is not None and after.channel is None:
        await send_log(
            member.guild,
            "🚪 VC退出ログ",
            f"{member.mention} がVCを退出しました。",
            [
                ("VCチャンネル", before.channel.mention, True),
                ("ユーザーID", str(member.id), True)
            ],
            discord.Color.darker_grey(),
            log_type="vc"
        )

# --- 詳細ログ機能群 (LOG_CONFIG_ENABLED 制御) ---

@bot.event
async def on_member_update(before, after):
    """ニックネームとロールの変更を追跡します。"""
    # ニックネームとロールの変更はLOG_CONFIG_ENABLEDに依存 (log_type="config")
    if not LOG_CONFIG_ENABLED: return
    
    # 1. ニックネーム変更のログ
    if before.nick != after.nick:
        await send_log(after.guild, "ニックネーム変更ログ", f"{after.mention} がニックネームを変更しました。",
            [("変更前", before.nick or before.name, True), ("変更後", after.nick or after.name, True)], 
            discord.Color.teal(), log_type="config")
    
    # 2. ロールの変更ログ (付与または剥奪) 
    if before.roles != after.roles:
        added_roles = [role for role in after.roles if role not in before.roles]
        removed_roles = [role for role in before.roles if role not in after.roles]
        
        if added_roles:
            role_names = ", ".join([r.name for r in added_roles])
            await send_log(after.guild, "ロール付与ログ", f"{after.mention} に新しいロールが付与されました。",
                [("付与されたロール", role_names, False)], 
                discord.Color.dark_teal(), log_type="config")

        if removed_roles:
            role_names = ", ".join([r.name for r in removed_roles])
            await send_log(after.guild, "ロール剥奪ログ", f"{after.mention} からロールが剥奪されました。",
                [("剥奪されたロール", role_names, False)], 
                discord.Color.dark_red(), log_type="config")

@bot.event
async def on_guild_update(before, after):
    """サーバー設定の変更を追跡します。"""
    if not LOG_CONFIG_ENABLED: return
    fields = []
    if before.name != after.name:
        fields.append(("サーバー名変更", f"**前:** `{before.name}`\n**後:** `{after.name}`", False))
    if before.icon != after.icon:
        fields.append(("アイコン変更", "アイコンが変更されました。", False))
    if before.verification_level != after.verification_level:
        fields.append(("認証レベル変更", f"**前:** {str(before.verification_level).split('.')[-1]}\n**後:** {str(after.verification_level).split('.')[-1]}", False))
    if fields:
        await send_log(after, "🌐 サーバー設定変更ログ", "サーバーの重要な設定が変更されました。", 
            fields, discord.Color.purple(), log_type="config")

# リアクションロールとログ
async def process_reaction_role_add(payload, guild, member):
    """リアクションロール付与のロジック"""
    global REACTION_ROLE_MSG_ID
    if payload.message_id != REACTION_ROLE_MSG_ID or payload.user_id == bot.user.id: return
    emoji_name = str(payload.emoji)
    if emoji_name in REACTION_ROLE_MAP:
        role_name_or_id = REACTION_ROLE_MAP[emoji_name]
        role_to_give = discord.utils.get(guild.roles, name=role_name_or_id)
        if role_to_give:
            try: await member.add_roles(role_to_give)
            except discord.Forbidden: logging.warning(f"Failed to give role {role_to_give.name}: Missing permissions.")

async def process_reaction_role_remove(payload, guild, member):
    """リアクションロール剥奪のロジック"""
    global REACTION_ROLE_MSG_ID
    if payload.message_id != REACTION_ROLE_MSG_ID or payload.user_id == bot.user.id: return
    emoji_name = str(payload.emoji)
    if emoji_name in REACTION_ROLE_MAP:
        role_name_or_id = REACTION_ROLE_MAP[emoji_name]
        role_to_remove = discord.utils.get(guild.roles, name=role_name_or_id)
        if role_to_remove:
            try: await member.remove_roles(role_to_remove)
            except discord.Forbidden: logging.warning(f"Failed to remove role {role_to_remove.name}: Missing permissions.")

@bot.event
async def on_raw_reaction_add(payload):
    """リアクション追加を追跡し、リアクションロールを処理します。"""
    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    user = guild.get_member(payload.user_id)
    if not user: return

    # 詳細ログが有効な場合のみ記録 (log_type="config")
    if LOG_CONFIG_ENABLED and payload.message_id != REACTION_ROLE_MSG_ID: 
        channel = guild.get_channel(payload.channel_id)
        await send_log(guild, "👍 リアクション追加ログ", f"{user.mention} がリアクションを追加しました。",
            [("チャンネル", channel.mention, True), ("メッセージID", str(payload.message_id), True), ("リアクション", str(payload.emoji), False)], 
            discord.Color.green(), log_type="config")
    
    # リアクションロール処理
    await process_reaction_role_add(payload, guild, user)

@bot.event
async def on_raw_reaction_remove(payload):
    """リアクション削除を追跡し、リアクションロールを処理します。"""
    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    user = guild.get_member(payload.user_id)
    if not user: return
    
    # 詳細ログが有効な場合のみ記録 (log_type="config")
    if LOG_CONFIG_ENABLED and payload.message_id != REACTION_ROLE_MSG_ID: 
        channel = guild.get_channel(payload.channel_id)
        await send_log(guild, "👎 リアクション削除ログ", f"{user.mention} がリアクションを削除しました。",
            [("チャンネル", channel.mention, True), ("メッセージID", str(payload.message_id), True), ("リアクション", str(payload.emoji), False)], 
            discord.Color.dark_green(), log_type="config")
        
    # リアクションロール処理
    await process_reaction_role_remove(payload, guild, user)

# --- メッセージ削除/編集ログ (LOG_CONFIG_ENABLED 制御) ---

@bot.event
async def on_message_delete(message):
    """メッセージ削除を追跡します。"""
    # 自動モデレーションによる削除はログに記録済みのため、ここではbot以外の自然な削除を記録
    if not LOG_CONFIG_ENABLED: return
    if message.author.bot or message.guild is None: return
    await send_log(message.guild, "メッセージ削除ログ", f"{message.author.mention} がメッセージを削除しました。 (チャンネル: {message.channel.name})",
                   [("実行者", message.author.mention, True), ("削除されたメッセージ", message.content or "（埋め込み、画像など）", False)], 
                   discord.Color.blue(), log_type="config")

@bot.event
async def on_message_edit(before, after):
    """メッセージ編集を追跡します。"""
    if not LOG_CONFIG_ENABLED: return
    if before.author.bot or before.content == after.content or before.guild is None: return
    await send_log(before.guild, "メッセージ編集ログ", f"{before.author.mention} がメッセージを編集しました。 (チャンネル: {before.channel.name})",
                   [("実行者", before.author.mention, True), ("編集前のメッセージ", before.content, False), ("編集後のメッセージ", after.content, False)], 
                   discord.Color.gold(), log_type="config")

@bot.event
async def on_guild_channel_create(channel):
    # このログは詳細ログとは切り離して常に有効にするか、トグル対象とするか検討が必要ですが、
    # 今回はLOG_CONFIG_ENABLEDの対象外として残します。
    await send_log(channel.guild, "チャンネル作成ログ", f"チャンネルが作成されました: {channel.name}",
                   [("チャンネルタイプ", str(channel.type).split('.')[-1].capitalize(), True)], discord.Color.dark_green(), log_type="moderation")

@bot.event
async def on_guild_channel_delete(channel):
    # このログは詳細ログとは切り離して常に有効にするか、トグル対象とするか検討が必要ですが、
    # 今回はLOG_CONFIG_ENABLEDの対象外として残します。
    await send_log(channel.guild, "チャンネル削除ログ", f"チャンネルが削除されました: {channel.name}",
                   [("チャンネルID", str(channel.id), True)], discord.Color.dark_red(), log_type="moderation")

@bot.event
async def on_guild_role_create(role):
    # このログは詳細ログとは切り離して常に有効にするか、トグル対象とするか検討が必要ですが、
    # 今回はLOG_CONFIG_ENABLEDの対象外として残します。
    await send_log(role.guild, "ロール作成ログ", f"新しいロールが作成されました: {role.name}",
                   [("色", str(role.color), True)], discord.Color.light_grey(), log_type="moderation")

@bot.event
async def on_guild_role_delete(role):
    # このログは詳細ログとは切り離して常に有効にするか、トグル対象とするか検討が必要ですが、
    # 今回はLOG_CONFIG_ENABLEDの対象外として残します。
    await send_log(role.guild, "ロール削除ログ", f"ロールが削除されました: {role.name}",
                   [("削除されたロールID", str(role.id), True)], discord.Color.dark_grey(), log_type="moderation")


# --- スラッシュコマンドの定義 ---

@bot.tree.command(name="help", description="利用可能なコマンド一覧を表示します。")
async def help_slash(interaction: discord.Interaction):
    """コマンド一覧を表示します。"""
    
    def get_log_status(channel_id):
        if channel_id != 0:
            channel = bot.get_channel(channel_id)
            return f"✅ 有効 (送信先: {channel.mention if channel else 'ID:' + str(channel_id)})"
        return "🚫 無効"

    vc_status = get_log_status(LOG_VC_CHANNEL_ID)
    member_status = get_log_status(LOG_MEMBER_CHANNEL_ID)
    config_status = get_log_status(LOG_CONFIG_CHANNEL_ID)

    current_ai_channels = [bot.get_channel(cid).mention for cid in AI_ENABLED_CHANNELS if bot.get_channel(cid)]
    ai_status = f"有効なチャンネル: {', '.join(current_ai_channels)}" if current_ai_channels else "現在、AI応答は無効です。"
    
    embed = discord.Embed(
        title="🤖 Botコマンドヘルプ (Carl-bot風)",
        description="モデレーションとコミュニティ機能が充実しています。",
        color=0x3498DB
    )

    commands_list = [
        ("--- AI応答設定 (Venice AI) ---", "高性能AIが質問に答えます。"),
        (f"`/ai_channel_toggle`", "このチャンネルをAI応答チャンネルとして設定/解除します。\n現在の状態: " + ai_status),
        ("--- ログ設定 (チャンネル選択機能付き) ---", "各ログ機能を独立して有効/無効に切り替え、送信先チャンネルを設定します。"),
        ("`/send_update_log <バージョン> <変更内容> <チャンネル>`", "Botの更新ログを指定チャンネルに送信します。（管理者専用）"),
        (f"`/member_log_toggle <有効/無効> [チャンネル]`", f"サーバー参加・脱退ログを切り替えます。\n現在の状態: {member_status}"),
        (f"`/vc_log_toggle <有効/無効> [チャンネル]`", f"🗣️ ボイスチャンネルの参加・退出ログを切り替えます。\n現在の状態: {vc_status}"),
        (f"`/log_config <有効/無効> [チャンネル]`", f"📜 詳細ログ（メッセージ、ロール、サーバー設定、Bot操作）を切り替えます。\n現在の状態: {config_status}"),
        ("--- 管理 & モデレーション ---", "Carl-botの核となる高度な管理とモデレーション機能"),
        ("`/fakemessage <ユーザー> <内容>`", "指定ユーザーになりすましてメッセージを送信します。（Webhookを使用）"),
        ("`/warn <メンバー> <理由>`", "指定メンバーに警告を付与し、履歴に記録します。"),
        ("`/warns <メンバー>`", "指定メンバーの警告履歴を一覧表示します。"),
        ("`/unwarn <メンバー>`", "指定メンバーの最新の警告を1つ削除します。"),
        ("`/timeout <メンバー> <分>`", "メンバーに一時的なタイムアウトを課します。"),
        ("`/kick <メンバー> <理由>`", "メンバーをキックします。"),
        ("`/clear <件数>`", "メッセージを一括削除します。"),
        ("--- コミュニティ & ユーティリティ ---", "エンゲージメントと情報表示"),
        ("`/avatar <メンバー>`", "指定したユーザーのアバター画像を表示します。"),
        ("`/rr_setup`", "リアクションロールの設定メッセージを送信します。"),
        ("`/poll <質問> <選択肢>`", "簡易投票を作成します。"),
        ("`/info`", "ユーザーの詳細情報を表示します。"),
        ("`/serverstatus`", "サーバーの統計情報を表示します。"),
        ("`/ping`", "Botの遅延を計算します。"),
    ]

    for name, desc in commands_list:
        embed.add_field(name=name, value=desc, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info("Action completed: Slash Help")


# --- Bot更新ログ送信コマンド ---
@bot.tree.command(name="send_update_log", description="Botの更新ログを指定チャンネルに送信します。（管理者専用）")
@app_commands.describe(
    version="新しいバージョン番号 (例: v2.1.0)",
    changes="変更点をカンマ区切りで入力 (例: 機能Aを追加,機能Bを削除,バグ修正)",
    channel="更新ログを送信するチャンネル"
)
@commands.has_permissions(administrator=True)
async def send_update_log_slash(interaction: discord.Interaction, version: str, changes: str, channel: discord.TextChannel):
    """管理者によるBotの更新ログ送信を処理します。"""
    
    changes_list = [c.strip() for c in changes.split(',') if c.strip()]
    
    if not changes_list:
        await interaction.response.send_message("変更内容をカンマ区切りで入力してください。", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    try:
        await send_update_log(
            bot,
            "重要アップデート",
            version,
            changes_list,
            channel,
            discord.Color.gold()
        )
        
        await interaction.followup.send(
            f"✅ 更新ログ (バージョン: **{version}**) を {channel.mention} に送信しました。",
            ephemeral=True
        )
            
    except Exception as e:
        logging.error(f"更新ログ送信コマンド処理中にエラーが発生しました: {e}")
        await interaction.followup.send(f"❌ 更新ログの送信中にエラーが発生しました: {e}", ephemeral=True)


# --- AI応答チャンネル設定コマンド (変更なし) ---

@bot.tree.command(name="ai_channel_toggle", description="このチャンネルをAI応答チャンネルとして設定/解除します。")
@commands.has_permissions(administrator=True)
async def ai_channel_toggle_slash(interaction: discord.Interaction):
    """AI応答が有効なチャンネルをトグルします。"""
    channel_id = interaction.channel_id
    channel_mention = interaction.channel.mention
    
    if channel_id in AI_ENABLED_CHANNELS:
        AI_ENABLED_CHANNELS.remove(channel_id)
        message = f"🚫 {channel_mention} をAI応答チャンネルから**解除**しました。\nこのチャンネルでのAI応答は停止されます。"
        color = discord.Color.red()
    else:
        AI_ENABLED_CHANNELS.add(channel_id)
        message = f"✅ {channel_mention} をAI応答チャンネルとして**設定**しました。\nこのチャンネルでメッセージを送信すると、AIが応答します。"
        color = discord.Color.green()
        
    await interaction.response.send_message(message, ephemeral=True)
    
    # Bot操作ログとして記録 (log_type="moderation")
    await send_log(
        interaction.guild,
        "AI応答チャンネル設定変更",
        f"{interaction.user.display_name} がAI応答チャンネル設定を変更しました。",
        [
            ("対象チャンネル", channel_mention, True),
            ("新しい状態", "有効" if channel_id in AI_ENABLED_CHANNELS else "無効", True)
        ],
        color
    )


# --- サーバー参加・脱退ログ トグルコマンド ---

@bot.tree.command(name="member_log_toggle", description="サーバー参加・脱退ログを有効/無効にし、送信チャンネルを設定します。")
@app_commands.describe(
    action="ログを有効にするか (enable) 無効にするか (disable)",
    channel="ログの送信先チャンネル (有効化時のみ任意)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="enable (有効)", value="enable"),
    app_commands.Choice(name="disable (無効)", value="disable"),
])
@commands.has_permissions(administrator=True)
async def member_log_toggle_slash(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    """サーバー参加・脱退ログ設定を有効または無効にします。"""
    global LOG_MEMBER_JOIN_LEAVE_ENABLED, LOG_MEMBER_CHANNEL_ID
    
    await interaction.response.defer(ephemeral=True)

    if action == "enable":
        if channel:
            # 新しいチャンネルを設定して有効化
            LOG_MEMBER_CHANNEL_ID = channel.id
            LOG_MEMBER_JOIN_LEAVE_ENABLED = True
            message = f"✅ **サーバー参加・脱退ログ**を**有効**にしました。\n新しい送信先: {channel.mention}"
            color = discord.Color.green()
        elif LOG_MEMBER_CHANNEL_ID != 0:
            # チャンネル指定なしで有効化（既存IDを使用）
            LOG_MEMBER_JOIN_LEAVE_ENABLED = True
            current_channel = bot.get_channel(LOG_MEMBER_CHANNEL_ID)
            message = f"✅ **サーバー参加・脱退ログ**を**有効**にしました。(送信先: {current_channel.mention if current_channel else 'ID:' + str(LOG_MEMBER_CHANNEL_ID)})"
            color = discord.Color.green()
        else:
            await interaction.followup.send("有効化するには、ログを送信するチャンネルを指定してください。", ephemeral=True)
            return

    elif action == "disable":
        LOG_MEMBER_JOIN_LEAVE_ENABLED = False
        LOG_MEMBER_CHANNEL_ID = 0 # IDをリセット
        message = "🚫 **サーバー参加・脱退ログ**を**無効**にしました。"
        color = discord.Color.red()
    else:
        message = "エラー: 無効なアクションが指定されました。"
        color = discord.Color.orange()
        
    await interaction.followup.send(message, ephemeral=True)
    
    # Bot操作ログとして記録 (log_type="moderation")
    await send_log(
        interaction.guild,
        "サーバー参加・脱退ログ設定変更",
        f"{interaction.user.display_name} がサーバー参加・脱退ログ設定を変更しました。",
        [
            ("新しい状態", "有効" if LOG_MEMBER_JOIN_LEAVE_ENABLED else "無効", True),
            ("送信先チャンネル", channel.mention if channel else "変更なし/無効化", True)
        ],
        color,
        log_type="moderation"
    )


# --- VCログ トグルコマンド ---

@bot.tree.command(name="vc_log_toggle", description="VC参加・退出ログを有効/無効にし、送信チャンネルを設定します。")
@app_commands.describe(
    action="VCログを有効にするか (enable) 無効にするか (disable)",
    channel="ログの送信先チャンネル (有効化時のみ任意)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="enable (有効)", value="enable"),
    app_commands.Choice(name="disable (無効)", value="disable"),
])
@commands.has_permissions(administrator=True)
async def vc_log_toggle_slash(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    """VCログ設定を有効または無効にします。"""
    global LOG_VC_ENABLED, LOG_VC_CHANNEL_ID
    
    await interaction.response.defer(ephemeral=True)

    if action == "enable":
        if channel:
            # 新しいチャンネルを設定して有効化
            LOG_VC_CHANNEL_ID = channel.id
            LOG_VC_ENABLED = True
            message = f"✅ **ボイスチャンネルの参加・退出ログ**を**有効**にしました。\n新しい送信先: {channel.mention}"
            color = discord.Color.green()
        elif LOG_VC_CHANNEL_ID != 0:
            # チャンネル指定なしで有効化（既存IDを使用）
            LOG_VC_ENABLED = True
            current_channel = bot.get_channel(LOG_VC_CHANNEL_ID)
            message = f"✅ **ボイスチャンネルの参加・退出ログ**を**有効**にしました。(送信先: {current_channel.mention if current_channel else 'ID:' + str(LOG_VC_CHANNEL_ID)})"
            color = discord.Color.green()
        else:
            await interaction.followup.send("有効化するには、ログを送信するチャンネルを指定してください。", ephemeral=True)
            return

    elif action == "disable":
        LOG_VC_ENABLED = False
        LOG_VC_CHANNEL_ID = 0 # IDをリセット
        message = "🚫 **ボイスチャンネルの参加・退出ログ**を**無効**にしました。"
        color = discord.Color.red()
    else:
        message = "エラー: 無効なアクションが指定されました。"
        color = discord.Color.orange()
        
    await interaction.followup.send(message, ephemeral=True)
    
    # Bot操作ログとして記録 (log_type="moderation")
    await send_log(
        interaction.guild,
        "VCログ設定変更",
        f"{interaction.user.display_name} がVCログ設定を変更しました。",
        [
            ("新しい状態", "有効" if LOG_VC_ENABLED else "無効", True),
            ("送信先チャンネル", channel.mention if channel else "変更なし/無効化", True)
        ],
        color,
        log_type="moderation"
    )


# --- 詳細ログ設定コマンド ---

@bot.tree.command(name="log_config", description="ユーザー、サーバー、メッセージ、リアクションの詳細ログを有効/無効にし、送信チャンネルを設定します。")
@app_commands.describe(
    action="ログを有効にするか (enable) 無効にするか (disable)",
    channel="ログの送信先チャンネル (有効化時のみ任意)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="enable (有効)", value="enable"),
    app_commands.Choice(name="disable (無効)", value="disable"),
])
@commands.has_permissions(administrator=True)
async def log_config_slash(interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
    """詳細ログ設定を有効または無効にします。"""
    global LOG_CONFIG_ENABLED, LOG_CONFIG_CHANNEL_ID
    
    await interaction.response.defer(ephemeral=True)

    if action == "enable":
        if channel:
            # 新しいチャンネルを設定して有効化
            LOG_CONFIG_CHANNEL_ID = channel.id
            LOG_CONFIG_ENABLED = True
            message = f"✅ 詳細ログ（メッセージ編集/削除、ロール、サーバー設定、Bot操作）を**有効**にしました。\n新しい送信先: {channel.mention}"
            color = discord.Color.green()
        elif LOG_CONFIG_CHANNEL_ID != 0:
            # チャンネル指定なしで有効化（既存IDを使用）
            LOG_CONFIG_ENABLED = True
            current_channel = bot.get_channel(LOG_CONFIG_CHANNEL_ID)
            message = f"✅ 詳細ログ（...）を**有効**にしました。(送信先: {current_channel.mention if current_channel else 'ID:' + str(LOG_CONFIG_CHANNEL_ID)})"
            color = discord.Color.green()
        else:
            await interaction.followup.send("有効化するには、ログを送信するチャンネルを指定してください。", ephemeral=True)
            return

    elif action == "disable":
        LOG_CONFIG_ENABLED = False
        LOG_CONFIG_CHANNEL_ID = 0 # IDをリセット
        message = "🚫 詳細ログ（メッセージ編集/削除、ロール、サーバー設定、Bot操作）を**無効**にしました。"
        color = discord.Color.red()
    else:
        message = "エラー: 無効なアクションが指定されました。"
        color = discord.Color.orange()
        
    await interaction.followup.send(message, ephemeral=True)
    
    # Bot操作ログとして記録 (log_type="moderation")
    await send_log(
        interaction.guild,
        "詳細ログ設定変更 (Log Config)",
        f"{interaction.user.display_name} が詳細ログ設定を変更しました。",
        [
            ("新しい状態", "有効" if LOG_CONFIG_ENABLED else "無効", True),
            ("送信先チャンネル", channel.mention if channel else "変更なし/無効化", True)
        ],
        color,
        log_type="moderation"
    )

# --- Carl-bot風 警告システムコマンド ---

@bot.tree.command(name="warn", description="指定されたメンバーに警告を付与します。")
@app_commands.describe(member="警告するメンバー", reason="警告の理由")
@commands.has_permissions(moderate_members=True)
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str):
    """メンバーに警告を付与し、インメモリの履歴に記録します。"""
    global warn_history
    
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーに警告を付与することはできません。", ephemeral=True)
        return

    warn_id = get_next_warn_id(member.id)
    new_warn = {
        'id': warn_id,
        'moderator_id': interaction.user.id,
        'reason': reason,
        'timestamp': datetime.now()
    }

    if member.id not in warn_history:
        warn_history[member.id] = []
    
    warn_history[member.id].append(new_warn)
    total_warns = len(warn_history[member.id])

    await interaction.response.send_message(f"⚠️ {member.display_name} に警告を付与しました。 (警告数: **{total_warns}**) 理由: `{reason}`")
    
    # Botによる操作ログとして記録 (log_type="moderation")
    await send_log(interaction.guild, "メンバー警告ログ (Warn)", f"{member.display_name} に警告が発行されました。",
        [("対象ユーザー", member.mention, True), ("理由", reason, False), ("合計警告数", str(total_warns), True)],
        discord.Color.orange(), moderator=interaction.user, log_type="moderation")
    
@bot.tree.command(name="warns", description="指定されたメンバーの警告履歴を表示します。")
@app_commands.describe(member="履歴を表示するメンバー")
@commands.has_permissions(moderate_members=True)
async def warns_slash(interaction: discord.Interaction, member: discord.Member):
    """メンバーの警告履歴を一覧表示します。"""
    warns = warn_history.get(member.id, [])
    
    if not warns:
        await interaction.response.send_message(f"✅ {member.display_name} には警告履歴がありません。", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"⚠️ {member.display_name} の警告履歴 (合計: {len(warns)}件)",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    for warn in warns:
        mod_user = interaction.guild.get_member(warn['moderator_id'])
        mod_name = mod_user.display_name if mod_user else "不明なモデレーター"
        
        embed.add_field(
            name=f"Warn ID: #{warn['id']} (日付: {warn['timestamp'].strftime('%Y/%m/%d')})",
            value=f"**理由:** `{warn['reason']}`\n**担当:** {mod_name}",
            inline=False
        )
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unwarn", description="指定されたメンバーの最新の警告を1つ削除します。")
@app_commands.describe(member="警告を削除するメンバー")
@commands.has_permissions(moderate_members=True)
async def unwarn_slash(interaction: discord.Interaction, member: discord.Member):
    """メンバーの最新の警告を1つ削除します。"""
    global warn_history
    
    if member.id not in warn_history or not warn_history[member.id]:
        await interaction.response.send_message(f"⚠️ {member.display_name} には削除できる警告履歴がありません。", ephemeral=True)
        return

    removed_warn = warn_history[member.id].pop()
    remaining_warns = len(warn_history[member.id])
    
    if not warn_history[member.id]:
        del warn_history[member.id]

    await interaction.response.send_message(
        f"✅ {member.display_name} の最新の警告 **(ID: #{removed_warn['id']})** を削除しました。\n"
        f"現在の警告数: **{remaining_warns}**件"
    )

    # Botによる操作ログとして記録 (log_type="moderation")
    await send_log(interaction.guild, "メンバー警告削除ログ (Unwarn)", f"{member.display_name} の警告が削除されました。",
        [("対象ユーザー", member.mention, True), ("削除されたID", str(removed_warn['id']), True), ("削除された理由", removed_warn['reason'], False)],
        discord.Color.blue(), moderator=interaction.user, log_type="moderation")


# --- 管理コマンド ---

@bot.tree.command(name="fakemessage", description="指定ユーザーになりすましてメッセージを送信します (Webhookを使用)。")
@app_commands.describe(user="なりすますユーザー", content="送信するメッセージ内容")
@commands.has_permissions(manage_webhooks=True)
async def fakemessage_slash(interaction: discord.Interaction, user: discord.Member, content: str):
    await interaction.response.defer(ephemeral=True)
    
    webhooks = await interaction.channel.webhooks()
    webhook_name = "FakeMessageBotWebhook"
    webhook = discord.utils.get(webhooks, name=webhook_name)
    
    if webhook is None:
        try:
            webhook = await interaction.channel.create_webhook(name=webhook_name, reason="`/fakemessage`コマンド用のWebhook作成")
        except discord.Forbidden:
            await interaction.followup.send("エラー: Webhookを作成または管理する権限がありません。", ephemeral=True)
            return

    try:
        avatar_url = user.display_avatar.url
        await webhook.send(content=content, username=user.display_name, avatar_url=avatar_url, wait=True)
        await interaction.followup.send(f"✅ **{user.display_name}**になりすましてメッセージを送信しました。", ephemeral=True)
        
        # Botによる操作ログとして記録 (log_type="moderation")
        await send_log(interaction.guild, "💬 なりすましメッセージログ (Fake Message)", f"{interaction.user.display_name} がメッセージを偽装しました。",
            [("なりすましユーザー", user.mention, True), ("チャンネル", interaction.channel.mention, True), ("メッセージ内容", content, False)],
            discord.Color.dark_magenta(), moderator=interaction.user, log_type="moderation")

    except discord.Forbidden:
        await interaction.followup.send("エラー: Webhookを送信する権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="指定されたメンバーをサーバーからキックします。")
@app_commands.describe(member="キックするメンバー", reason="キックする理由 (省略可)")
@commands.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    if member.top_role >= interaction.user.top_role or member == interaction.user:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーをキックすることはできません。", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.display_name} をキックしました。理由: {reason}")
        
        # Botによる操作ログとして記録 (log_type="moderation")
        await send_log(interaction.guild, "メンバーキックログ (実行)", f"{member.display_name} がキックされました。",
                       [("対象ユーザー", member.mention, True), ("理由", reason, False)], 
                       discord.Color.red(), moderator=interaction.user, log_type="moderation")
                       
    except discord.Forbidden:
        await interaction.response.send_message("エラー: キックする権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

@bot.tree.command(name="timeout", description="メンバーに一時的なタイムアウトを課します。")
@app_commands.describe(member="タイムアウトするメンバー", minutes="タイムアウト時間 (1分〜40320分/4週間)", reason="理由 (省略可)")
@commands.has_permissions(moderate_members=True)
async def timeout_slash(interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "理由なし"):
    if member.top_role >= interaction.user.top_role or member == interaction.user:
        await interaction.response.send_message("自分より上位または同等の役職のメンバーにタイムアウトを課すことはできません。", ephemeral=True)
        return
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"⏸️ {member.display_name} に {minutes} 分間のタイムアウトを課しました。理由: {reason}")
        
        # Botによる操作ログとして記録 (log_type="moderation")
        await send_log(interaction.guild, "メンバータイムアウトログ", f"{member.display_name} がタイムアウトされました。",
                       [("期間", f"{minutes} 分間", True), ("理由", reason, False)], 
                       discord.Color.dark_teal(), moderator=interaction.user, log_type="moderation")
                       
    except discord.Forbidden:
        await interaction.response.send_message("エラー: タイムアウトを課す権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"予期せぬエラーが発生しました: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="指定された件数のメッセージを削除します (最大100件)。")
@app_commands.describe(count="削除するメッセージの件数 (1～100)")
@commands.has_permissions(manage_messages=True)
async def clear_slash(interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True)
    try:
        deleted = await interaction.channel.purge(limit=count)
        
        # Botによる操作ログとして記録 (log_type="moderation")
        await send_log(interaction.guild, "メッセージ一括削除ログ", f"{interaction.user.display_name} がメッセージを一括削除しました。",
                       [("削除件数", str(len(deleted)), True)], 
                       discord.Color.dark_red(), moderator=interaction.user, log_type="moderation")
                       
        await interaction.followup.send(f"✅ {len(deleted)} 件のメッセージを削除しました。", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("エラー: メッセージを管理する権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)


# --- 簡易リアクションロール設定 (/rr_setup) ---

@bot.tree.command(name="rr_setup", description=f"リアクションロールの設定メッセージを送信します。マップ: {', '.join(REACTION_ROLE_MAP.keys())}")
@commands.has_permissions(manage_roles=True)
async def rr_setup_slash(interaction: discord.Interaction):
    global REACTION_ROLE_MSG_ID
    description_lines = [
        "**📚 ロール自動付与ステーション 📚**",
        "欲しいロールに対応するリアクションをクリックしてください。",
        ""
    ]
    for emoji, role_name in REACTION_ROLE_MAP.items():
        description_lines.append(f"{emoji} で **{role_name}** ロールが付与/剥奪されます。")
    embed = discord.Embed(title="リアクションロール設定", description="\n".join(description_lines), color=discord.Color.purple())
    await interaction.response.defer(thinking=True)
    rr_message = await interaction.channel.send(embed=embed)
    REACTION_ROLE_MSG_ID = rr_message.id
    for emoji in REACTION_ROLE_MAP.keys():
        await rr_message.add_reaction(emoji)
        
    # Botによる操作ログとして記録 (log_type="moderation")
    await send_log(interaction.guild, "リアクションロール設定 (実行)", f"{interaction.user.display_name} がリアクションロールを設定しました。",
        [("チャンネル", interaction.channel.mention, True), ("メッセージID", str(REACTION_ROLE_MSG_ID), True)], 
        discord.Color.purple(), moderator=interaction.user, log_type="moderation")

    await interaction.followup.send(f"✅ リアクションロールメッセージを送信し、設定しました。メッセージID: `{REACTION_ROLE_MSG_ID}`", ephemeral=True)


# --- ユーティリティ/エンゲージメントコマンド (簡易実装) ---

@bot.tree.command(name="poll", description="簡易投票を作成します。")
@app_commands.describe(question="投票の質問", options="選択肢をカンマ区切りで入力 (例: A, B, C)")
async def poll_slash(interaction: discord.Interaction, question: str, options: str):
    options_list = [opt.strip() for opt in options.split(',')]
    if len(options_list) < 2 or len(options_list) > 10:
        await interaction.response.send_message("選択肢は2つ以上10個以下にしてください。", ephemeral=True)
        return

    emoji_map = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    poll_content = "\n".join([f"{emoji_map[i]} {opt}" for i, opt in enumerate(options_list)])
    
    embed = discord.Embed(title=f"🗳️ 投票: {question}", description=poll_content, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    response_msg = await interaction.original_response()
    for i in range(len(options_list)):
        await response_msg.add_reaction(emoji_map[i])

@bot.tree.command(name="guess", description="1から100までの数字を当てるゲームを開始します。")
async def guess_slash(interaction: discord.Interaction):
    await interaction.response.send_message("現在、`/guess` ゲーム機能はメンテナンス中です。近日中に実装予定です！", ephemeral=True)

@bot.tree.command(name="ping", description="Botの現在の応答速度（Ping値）を計測します。")
async def ping_slash(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Botの遅延: **{latency_ms}ms**", ephemeral=True)

@bot.tree.command(name="info", description="特定のユーザーの詳細情報を表示します。")
@app_commands.describe(member="情報を表示するユーザー (省略可)")
async def info_slash(interaction: discord.Interaction, member: discord.Member = None):
    user = member if member else interaction.user
    
    embed = discord.Embed(
        title=f"👤 {user.display_name} の情報",
        color=user.color if user.color != discord.Color.default() else discord.Color.greyple(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="作成日", value=user.created_at.strftime("%Y/%m/%d %H:%M"), inline=True)
    embed.add_field(name="サーバー参加日", value=user.joined_at.strftime("%Y/%m/%d %H:%M") if user.joined_at else "N/A", inline=True)
    
    roles = [role.name for role in user.roles if role.name != "@everyone"]
    roles_str = ", ".join(roles) if roles else "役職なし"
    embed.add_field(name="主な役職", value=user.top_role.name, inline=True)
    embed.add_field(name="全役職数", value=str(len(user.roles) - 1), inline=True)
    embed.add_field(name="ニックネーム", value=user.nick if user.nick else "N/A", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="serverstatus", description="サーバーの統計情報を表示します。")
async def serverstatus_slash(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("このコマンドはサーバー内でのみ実行できます。", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📊 {guild.name} のサーバー統計",
        color=discord.Color.dark_blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    
    embed.add_field(name="オーナー", value=guild.owner.mention if guild.owner else "不明", inline=True)
    embed.add_field(name="作成日", value=guild.created_at.strftime("%Y/%m/%d %H:%M"), inline=True)
    embed.add_field(name="メンバー数", value=f"{guild.member_count} 人", inline=True)
    embed.add_field(name="チャンネル数", value=f"テキスト: {text_channels}, VC: {voice_channels}", inline=True)
    embed.add_field(name="役職数", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="ブーストレベル", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} ブースト)", inline=True)
    
    await interaction.response.send_message(embed=embed)


# --- KeepAlive Server & Main Execution (Render安定化) ---

def start_bot():
    """Discord Botの実行を別スレッドで開始する"""
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logging.error("致命的なエラー: 環境変数 'DISCORD_TOKEN' が設定されていません。")
    else:
        token_preview = TOKEN[:5] + "..." + TOKEN[-5:]
        logging.info(f"DISCORD_TOKENを読み込みました (Preview: {token_preview})")
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            logging.error("ログイン失敗: Discord Bot Tokenが無効、または必要なインテントが不足しています。")
        except Exception as e:
            logging.error(f"予期せぬエラーが発生しました: {e}")

bot_thread = threading.Thread(target=start_bot)
bot_thread.start()

@app.route("/")
def home():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    if bot.is_ready():
        return "Bot is running and ready!"
    else:
        return "Bot is starting up or failed to start...", 503

@app.route("/keep_alive", methods=["GET"])
def keep_alive_endpoint():
    """UptimeRobotからのヘルスチェックに応答するエンドポイント"""
    return jsonify({"message": "Alive"}), 200
