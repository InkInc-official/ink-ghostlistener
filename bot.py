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

DISCORD_TOKEN      = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# ── お便りデータ読み込み ───────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "letters.json")

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

# ── 重複防止 ───────────────────────────────────────────────────────────────
used_ids: set[int] = set()

def get_random_letter() -> dict | None:
    """未使用のお便りをランダムに1件返す。全件使い切ったらリセット。"""
    global used_ids
    if not letters:
        return None
    available = [l for l in letters if l["id"] not in used_ids]
    if not available:
        used_ids.clear()
        available = letters
    letter = random.choice(available)
    used_ids.add(letter["id"])
    return letter

# ── メッセージ組み立て ─────────────────────────────────────────────────────
def build_message() -> str | None:
    """お便りを1件選んでDiscord投稿用文字列を返す。"""
    letter = get_random_letter()
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
# 正規化後の半角文字列にマッチするパターン
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")

JST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc

def normalize_to_halfwidth(s: str) -> str:
    """全角数字（０〜９）・全角コロン（：）を半角に正規化する。"""
    result = []
    for ch in s:
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19:   # 全角数字 → 半角数字
            result.append(chr(code - 0xFEE0))
        elif ch == "：":               # 全角コロン → 半角コロン
            result.append(":")
        else:
            result.append(ch)
    return "".join(result)

def parse_jst_to_utc(time_str: str) -> datetime.time | None:
    """
    時刻文字列をパースしてUTCのdatetime.timeに変換する。
    全角・半角の数字とコロンが混在していても正しく処理する。
    対応例：「20:45」「２０:４５」「20：45」「２０：４５」
    パース失敗・範囲外の場合はNoneを返す。
    """
    normalized = normalize_to_halfwidth(time_str)
    m = TIME_PATTERN.search(normalized)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    # JST → UTC（-9時間）
    jst_dt = datetime.datetime(2000, 1, 1, hour, minute, tzinfo=JST)
    utc_dt = jst_dt.astimezone(UTC)
    return utc_dt.time().replace(tzinfo=UTC)

def utc_to_jst_str(utc_time: datetime.time) -> str:
    """UTCのdatetime.timeをJST表記の文字列に変換する。"""
    utc_dt = datetime.datetime(2000, 1, 1,
                               utc_time.hour, utc_time.minute, tzinfo=UTC)
    jst_dt = utc_dt.astimezone(JST)
    return f"{jst_dt.hour:02d}:{jst_dt.minute:02d}"

# ── Discord Bot セットアップ ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="", intents=intents)

# 自動投稿の状態管理
auto_post_enabled: bool = True
# デフォルト投稿時刻：JST 20:45 → UTC 11:45
auto_post_utc_time: datetime.time = datetime.time(hour=11, minute=45, tzinfo=UTC)

# ── タスク再起動ヘルパー ───────────────────────────────────────────────────
def restart_scheduled_post(new_utc_time: datetime.time) -> None:
    """タスクを停止して新しい時刻で再起動する。"""
    global auto_post_utc_time
    auto_post_utc_time = new_utc_time
    if scheduled_post.is_running():
        scheduled_post.cancel()
    scheduled_post.change_interval(time=new_utc_time)
    scheduled_post.start()

# ── 自動投稿タスク ────────────────────────────────────────────────────────
# 初期時刻はデフォルト（JST 20:45 = UTC 11:45）で起動
@tasks.loop(time=datetime.time(hour=11, minute=45, tzinfo=UTC))
async def scheduled_post():
    if not auto_post_enabled:
        print("[AUTO] 自動投稿はオフのためスキップしました。")
        return
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        print(f"[ERROR] チャンネルID {DISCORD_CHANNEL_ID} が見つかりません。")
        return
    message = build_message()
    if message:
        await channel.send(message)
        print(f"[AUTO] 自動投稿しました（{utc_to_jst_str(auto_post_utc_time)} JST）。")
    else:
        print("[AUTO] お便りデータが空です。letters.json を確認してください。")

# ── on_ready ──────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[BOT] ログイン完了: {bot.user}")
    if not scheduled_post.is_running():
        scheduled_post.start()
    print(f"[BOT] 自動投稿タスク開始（デフォルト: 20:45 JST）")

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

    # 指定チャンネル以外は無視
    if message.channel.id != DISCORD_CHANNEL_ID:
        return

    # サーバー外（DM等）は無視
    if message.guild is None:
        return

    content = message.content.strip()

    # ── コマンド：お便りを1件投稿 ─────────────────────────────────────────
    if content == "スタッフ、次のお便りちょうだい":
        if not await check_owner(message):
            return
        msg = build_message()
        if msg:
            await message.channel.send(msg)
            print("[CMD] 手動コマンドでお便りを投稿しました。")
        else:
            await message.channel.send("お便りデータが空です。letters.json を確認してください。")

    # ── コマンド：自動投稿を指定時刻にオン ───────────────────────────────
    # 例：「スタッフ、自動投稿を20：45にオンにして」
    #     「スタッフ、自動投稿を21:00にオンにして」
    elif content.startswith("スタッフ、自動投稿を") and content.endswith("にオンにして"):
        if not await check_owner(message):
            return
        utc_time = parse_jst_to_utc(content)
        if utc_time is None:
            await message.channel.send(
                "時刻の形式が正しくありません。\n"
                "例：`スタッフ、自動投稿を20:45にオンにして`"
            )
            return
        global auto_post_enabled
        auto_post_enabled = True
        restart_scheduled_post(utc_time)
        jst_str = utc_to_jst_str(utc_time)
        await message.channel.send(f"自動投稿を **オン** にしました。毎日 **{jst_str}** に投稿します。")
        print(f"[CMD] 自動投稿をオンにしました（{jst_str} JST）。")

    # ── コマンド：自動投稿を指定時刻にオフ ───────────────────────────────
    # 例：「スタッフ、自動投稿を20：45にオフにして」
    elif content.startswith("スタッフ、自動投稿を") and content.endswith("にオフにして"):
        if not await check_owner(message):
            return
        utc_time = parse_jst_to_utc(content)
        if utc_time is None:
            await message.channel.send(
                "時刻の形式が正しくありません。\n"
                "例：`スタッフ、自動投稿を20:45にオフにして`"
            )
            return
        auto_post_enabled = False
        restart_scheduled_post(utc_time)
        jst_str = utc_to_jst_str(utc_time)
        await message.channel.send(
            f"自動投稿を **オフ** にしました。\n"
            f"（時刻は {jst_str} に設定済み。オンにする場合は `スタッフ、自動投稿を{jst_str}にオンにして`）"
        )
        print(f"[CMD] 自動投稿をオフにしました（時刻: {jst_str} JST）。")

    # ── コマンド：現在の自動投稿状態を確認 ───────────────────────────────
    elif content == "スタッフ、自動投稿の状態は":
        if not await check_owner(message):
            return
        jst_str = utc_to_jst_str(auto_post_utc_time)
        if auto_post_enabled:
            status = f"オン（毎日 **{jst_str}** に投稿）"
        else:
            status = f"オフ（設定時刻: {jst_str}）"
        await message.channel.send(f"自動投稿は現在 **{status}** です。")

# ── 起動 ──────────────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
