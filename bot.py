import os
import re
import json
import random
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ── 環境変数 ────────────────────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ── パス定義 ──────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
DATA_PATH    = os.path.join(BASE_DIR, "data", "letters.json")
SERVERS_PATH = os.path.join(BASE_DIR, "data", "servers.json")

# ── お便りデータ読み込み ───────────────────────────────────────────────────
def load_letters() -> list[dict]:
    """letters.json を読み込んで返す。失敗時は空リスト。"""
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] letters.json が見つかりません: {DATA_PATH}")
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] letters.json の形式が不正です: {e}")
        return []

letters: list[dict] = load_letters()

# ── サーバー設定の読み書き ─────────────────────────────────────────────────
def load_servers() -> dict:
    """servers.json を読み込む。ファイルが存在しない場合は空dictを返す。"""
    try:
        with open(SERVERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"[ERROR] servers.json の形式が不正です: {e}")
        return {}

def save_servers(servers: dict) -> None:
    """servers.json に書き込む。dataディレクトリがなければ作成する。"""
    os.makedirs(os.path.dirname(SERVERS_PATH), exist_ok=True)
    with open(SERVERS_PATH, "w", encoding="utf-8") as f:
        json.dump(servers, f, ensure_ascii=False, indent=2)

# servers はグローバルで保持する（変更時は必ずsave_servers()を呼ぶ）
servers: dict = load_servers()

# ── ラジオネーム生成 ───────────────────────────────────────────────────────
PREFIXES = [
    # 時間・夜の雰囲気
    "夜更かし", "眠れない", "深夜の", "真夜中の", "夜明けの",
    "宵の口の", "夕暮れの", "朝靄の", "夜霧の", "夜空の",
    # 状態・感覚
    "ひとり", "のんびり", "ふわふわ", "ぼんやり", "うとうと",
    "きらきら", "てくてく", "ぽつり", "しんみり", "ぽかぽか",
    "ゆらゆら", "ほっこり", "ぽかん", "ぼうっと", "しずかな",
    # 感情・心境
    "静かな", "おだやかな", "おぼろな", "たよりない", "なつかしい",
    "あたたかな", "やさしい", "ふしぎな", "せつない", "ほのかな",
    # 自然・情景
    "雨音の", "霧雨の", "木漏れ日の", "三日月の", "星明かりの",
    "春風の", "秋風の", "小雨の", "夕焼けの", "朝露の",
    # ユニーク・個性的
    "迷子の", "道草の", "うろうろ", "さすらいの", "ぐるぐる",
    "ひっそり", "こっそり", "ゆっくり", "ひらひら", "ゆらり",
]

SUFFIXES = [
    # 自然・植物
    "さくら", "もみじ", "すみれ", "たんぽぽ", "あじさい",
    "なのはな", "つゆくさ", "わすれな草", "ひまわり", "コスモス",
    # 動物
    "ねこ", "うさぎ", "ことり", "たぬき", "きつね",
    "ふくろう", "はりねずみ", "こあら", "りす", "かもめ",
    # 天体・空
    "つき", "ほし", "かぜ", "そら", "にじ",
    "ながれ星", "みかづき", "あけぼの", "たそがれ", "オーロラ",
    # 水・自然現象
    "かわ", "しずく", "なみ", "きり", "ゆき",
    "あめ", "あられ", "みずうみ", "いずみ", "なだれ",
    # 食べ物・飲み物
    "はな", "もり", "ほうじ茶", "ミルク", "バニラ",
    "チョコ", "キャラメル", "クッキー", "マシュマロ", "あんこ",
]

def generate_radio_name() -> str:
    return random.choice(PREFIXES) + random.choice(SUFFIXES)

# ── サーバーごとの重複防止 ────────────────────────────────────────────────
def get_random_letter(guild_id: str) -> dict | None:
    """
    サーバーごとの used_ids を参照してランダムに1件返す。
    全件使い切ったらそのサーバーのみリセット。
    """
    if not letters:
        return None
    used = set(servers.get(guild_id, {}).get("used_ids", []))
    available = [l for l in letters if l["id"] not in used]
    if not available:
        # このサーバーの used_ids のみリセット
        used = set()
        available = letters
        print(f"[INFO] サーバー {guild_id} の used_ids をリセットしました。")
    letter = random.choice(available)
    used.add(letter["id"])
    # 保存
    servers[guild_id]["used_ids"] = list(used)
    save_servers(servers)
    return letter

# ── メッセージ組み立て ─────────────────────────────────────────────────────
def build_message(guild_id: str) -> str | None:
    """お便りを1件選んでDiscord投稿用文字列を返す。"""
    letter = get_random_letter(guild_id)
    if letter is None:
        return None
    radio_name = generate_radio_name()
    text = (
        f"ラジオネーム：{radio_name}\n"
        f"配信者さんこんばんは。\n"
        f"{letter['episode']}\n"
        f"{letter['feeling']}\n"
        f"{letter['question']}"
    )
    return text[:2000]  # Discord上限

# ── 時刻パース ─────────────────────────────────────────────────────────────
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")

JST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc

def normalize_to_halfwidth(s: str) -> str:
    """全角数字（０〜９）・全角コロン（：）を半角に正規化する。"""
    result = []
    for ch in s:
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19:
            result.append(chr(code - 0xFEE0))
        elif ch == "：":
            result.append(":")
        else:
            result.append(ch)
    return "".join(result)

def parse_jst_to_utc(time_str: str) -> tuple[int, int] | None:
    """
    時刻文字列をパースしてUTCの (hour, minute) タプルに変換する。
    全角・半角の数字とコロンが混在していても正しく処理する。
    パース失敗・範囲外の場合はNoneを返す。
    """
    normalized = normalize_to_halfwidth(time_str)
    m = TIME_PATTERN.search(normalized)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    jst_dt = datetime.datetime(2000, 1, 1, hour, minute, tzinfo=JST)
    utc_dt = jst_dt.astimezone(UTC)
    return (utc_dt.hour, utc_dt.minute)

def utc_hm_to_jst_str(utc_hour: int, utc_minute: int) -> str:
    """UTC の (hour, minute) をJST表記の文字列に変換する。"""
    utc_dt = datetime.datetime(2000, 1, 1, utc_hour, utc_minute, tzinfo=UTC)
    jst_dt = utc_dt.astimezone(JST)
    return f"{jst_dt.hour:02d}:{jst_dt.minute:02d}"

# ── Discord Bot セットアップ ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="", intents=intents)

# ── 自動投稿タスク（毎分チェック方式） ───────────────────────────────────
@tasks.loop(minutes=1)
async def scheduled_post():
    now_utc = datetime.datetime.now(UTC)
    for guild_id, config in list(servers.items()):
        if not config.get("auto_post_enabled", False):
            continue
        if (now_utc.hour == config.get("auto_post_utc_hour") and
                now_utc.minute == config.get("auto_post_utc_minute")):
            channel = bot.get_channel(config["channel_id"])
            if channel is None:
                print(f"[ERROR] サーバー {guild_id}: チャンネルID {config['channel_id']} が見つかりません。")
                continue
            message = build_message(guild_id)
            if message:
                await channel.send(message)
                jst_str = utc_hm_to_jst_str(config["auto_post_utc_hour"], config["auto_post_utc_minute"])
                print(f"[AUTO] サーバー {guild_id} に自動投稿しました（{jst_str} JST）。")
            else:
                print(f"[AUTO] サーバー {guild_id}: お便りデータが空です。letters.json を確認してください。")

# ── on_ready ──────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[BOT] ログイン完了: {bot.user}")
    if not scheduled_post.is_running():
        scheduled_post.start()
    print(f"[BOT] 自動投稿タスク開始（毎分チェック方式）")
    print(f"[BOT] 登録済みサーバー数: {len(servers)}")

# ── 権限チェックヘルパー ───────────────────────────────────────────────────
async def check_owner(message: discord.Message) -> bool:
    """サーバーオーナー以外なら拒否メッセージを送ってFalseを返す。"""
    if message.author.id != message.guild.owner_id:
        await message.channel.send("このコマンドは配信者のみ使用できます。")
        return False
    return True

# ── メッセージ受信 ────────────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    # Bot自身は無視
    if message.author == bot.user:
        return

    # サーバー外（DM等）は無視
    if message.guild is None:
        return

    guild_id = str(message.guild.id)
    content  = message.content.strip()

    # ── コマンド：このチャンネルで使って（チャンネル登録） ───────────────
    if content == "スタッフ、このチャンネルで使って":
        if not await check_owner(message):
            return
        # すでに登録済みの場合は used_ids などを引き継ぎ、channel_id だけ更新する
        existing = servers.get(guild_id, {})
        servers[guild_id] = {
            "channel_id":         message.channel.id,
            "auto_post_enabled":  existing.get("auto_post_enabled", False),
            "auto_post_utc_hour": existing.get("auto_post_utc_hour", 11),
            "auto_post_utc_minute": existing.get("auto_post_utc_minute", 45),
            "used_ids":           existing.get("used_ids", []),
        }
        save_servers(servers)
        await message.channel.send(
            f"✅ 準備完了です！このチャンネルをお便りの投稿先として登録しました。\n\n"
            f"**使えるコマンド一覧**\n"
            f"`スタッフ、次のお便りちょうだい` ─ お便りを今すぐ1件投稿\n"
            f"`スタッフ、自動投稿を20:45にオンにして` ─ 毎日自動投稿（時刻はJST）\n"
            f"`スタッフ、自動投稿を20:45にオフにして` ─ 自動投稿を停止\n"
            f"`スタッフ、自動投稿の状態は` ─ 現在の設定を確認\n"
            f"`スタッフ、登録解除して` ─ このサーバーの設定を削除"
        )
        print(f"[CMD] サーバー {guild_id}: チャンネル {message.channel.id} を登録しました。")
        return

    # ── コマンド：登録解除して ────────────────────────────────────────────
    if content == "スタッフ、登録解除して":
        if not await check_owner(message):
            return
        if guild_id not in servers:
            await message.channel.send("このサーバーはまだ登録されていません。")
            return
        del servers[guild_id]
        save_servers(servers)
        await message.channel.send("このサーバーの設定をすべて削除しました。")
        print(f"[CMD] サーバー {guild_id}: 登録を解除しました。")
        return

    # ── 以降のコマンドは登録済みサーバーのみ受け付ける ───────────────────
    if guild_id not in servers:
        # 未登録サーバーでは何も反応しない
        return

    config = servers[guild_id]

    # 登録チャンネル以外からのコマンドは無視
    if message.channel.id != config["channel_id"]:
        return

    # ── コマンド：お便りを1件投稿 ─────────────────────────────────────────
    if content == "スタッフ、次のお便りちょうだい":
        if not await check_owner(message):
            return
        msg = build_message(guild_id)
        if msg:
            await message.channel.send(msg)
            print(f"[CMD] サーバー {guild_id}: 手動コマンドでお便りを投稿しました。")
        else:
            await message.channel.send("お便りデータが空です。letters.json を確認してください。")

    # ── コマンド：自動投稿を指定時刻にオン ───────────────────────────────
    elif content.startswith("スタッフ、自動投稿を") and content.endswith("にオンにして"):
        if not await check_owner(message):
            return
        result = parse_jst_to_utc(content)
        if result is None:
            await message.channel.send(
                "時刻の形式が正しくありません。\n"
                "例：`スタッフ、自動投稿を20:45にオンにして`"
            )
            return
        utc_hour, utc_minute = result
        config["auto_post_enabled"]   = True
        config["auto_post_utc_hour"]  = utc_hour
        config["auto_post_utc_minute"] = utc_minute
        save_servers(servers)
        jst_str = utc_hm_to_jst_str(utc_hour, utc_minute)
        await message.channel.send(f"自動投稿を **オン** にしました。毎日 **{jst_str}** に投稿します。")
        print(f"[CMD] サーバー {guild_id}: 自動投稿をオンにしました（{jst_str} JST）。")

    # ── コマンド：自動投稿を指定時刻にオフ ───────────────────────────────
    elif content.startswith("スタッフ、自動投稿を") and content.endswith("にオフにして"):
        if not await check_owner(message):
            return
        result = parse_jst_to_utc(content)
        if result is None:
            await message.channel.send(
                "時刻の形式が正しくありません。\n"
                "例：`スタッフ、自動投稿を20:45にオフにして`"
            )
            return
        utc_hour, utc_minute = result
        config["auto_post_enabled"]   = False
        config["auto_post_utc_hour"]  = utc_hour
        config["auto_post_utc_minute"] = utc_minute
        save_servers(servers)
        jst_str = utc_hm_to_jst_str(utc_hour, utc_minute)
        await message.channel.send(
            f"自動投稿を **オフ** にしました。\n"
            f"（時刻は {jst_str} に設定済み。オンにする場合は `スタッフ、自動投稿を{jst_str}にオンにして`）"
        )
        print(f"[CMD] サーバー {guild_id}: 自動投稿をオフにしました（時刻: {jst_str} JST）。")

    # ── コマンド：現在の自動投稿状態を確認 ───────────────────────────────
    elif content == "スタッフ、自動投稿の状態は":
        if not await check_owner(message):
            return
        jst_str = utc_hm_to_jst_str(
            config.get("auto_post_utc_hour", 11),
            config.get("auto_post_utc_minute", 45),
        )
        if config.get("auto_post_enabled", False):
            status = f"オン（毎日 **{jst_str}** に投稿）"
        else:
            status = f"オフ（設定時刻: {jst_str}）"
        await message.channel.send(f"自動投稿は現在 **{status}** です。")

# ── 起動 ──────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
