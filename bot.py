#!/usr/bin/env python3
"""
TeleRich — Telegram Rich Markdown & HTML Bot (Python edition)
Ported from the original Cloudflare Worker (worker.js) by DarknessShade,
extended with additional Telegram Bot API 10.1 Rich Message coverage.

Bot API: 10.1 (Rich Messages — sendRichMessage / sendRichMessageDraft / rich_message)
Runtime: plain Python 3.9+, long polling (getUpdates) — no webhook / no public URL needed.
Built for Wispbyte "Python" Docker image: startup command -> python bot.py

Original project: https://github.com/DarknessShade/TeleRich
"""

import json
import logging
import os
import random
import sys
import time
import traceback
import uuid
from pathlib import Path

import requests

# ─── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "Enter your Telegram bot token")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30          # long-polling timeout (seconds)
REQUEST_TIMEOUT = POLL_TIMEOUT + 10
RETRY_DELAY = 3            # seconds to wait after a network error

# 👉👉👉 EDIT THIS: apna Telegram username daalo (bina @ ke) 👈👈👈
DEV_USERNAME = "YOUR_USERNAME"

# 👉👉👉 EDIT THIS: apni Telegram numeric user ID daalo (username nahi!) 👈👈👈
# ID nikaalne ke liye @userinfobot ya @getidsbot ko /start karo.
# Multiple admins chahiye to: ADMIN_IDS = {111111111, 222222222}
ADMIN_IDS = {123456789}

# AI chat-completion API (inline search ke jawab ke liye)
AI_API_URL = "https://api-xqwa.onrender.com/chat/completion"
AI_REQUEST_TIMEOUT = 30

BASE_DIR = Path(__file__).resolve().parent
CONTENT_PATH = BASE_DIR / "content.json"
USERS_PATH = BASE_DIR / "users.json"        # broadcast recipient list (persisted)
BROADCAST_DELAY = 0.05                       # seconds between sends (flood-limit safe)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("telerich")

BOT_USERNAME = ""  # filled in at startup via getMe() in main()

# ─── Content (bilingual guide/demo text) ───────────────────────────────────
try:
    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        CONTENT = json.load(f)
except FileNotFoundError:
    log.error("content.json not found next to bot.py — cannot start.")
    sys.exit(1)

WELCOME = CONTENT["WELCOME"]
ABOUT = CONTENT["ABOUT"]
HELP_MD = CONTENT["HELP_MD"]
HELP_HTML = CONTENT["HELP_HTML"]
HELP_MEDIA = CONTENT["HELP_MEDIA"]
HELP_ADV = CONTENT["HELP_ADV"]
DEMO = CONTENT["DEMO"]
STREAM_DEMO_FRAMES = CONTENT["STREAM_DEMO_FRAMES"]

# Built-in fallback so an older/mismatched content.json (missing this key)
# can't crash the whole bot — only the /ai command would miss translations.
_AI_TXT_FALLBACK = {
    "en": {
        "ask": "🤖 Search inline for an AI answer:\nType @{bot} your question in any chat",
        "thinking": "🤔 Thinking...",
        "error": "❌ Error, try again",
        "dev_btn": "👤 Developer",
        "inline_title": "🤖 Ask AI: ",
        "inline_desc": "Tap to send this question and get an AI-generated answer",
    },
    "hi": {
        "ask": "🤖 AI जवाब के लिए inline search करो:\nकिसी भी चैट में @{bot} अपना सवाल टाइप करो",
        "thinking": "🤔 सोच रहा हूँ...",
        "error": "❌ गलती हुई",
        "dev_btn": "👤 डेवलपर",
        "inline_title": "🤖 AI से पूछो: ",
        "inline_desc": "टैप करें और AI से जवाब पाएं",
    },
}
if "AI_TXT" not in CONTENT:
    log.warning("content.json is missing 'AI_TXT' — using built-in fallback text. "
                "Re-upload the latest content.json to fix this properly.")
AI_TXT = CONTENT.get("AI_TXT", _AI_TXT_FALLBACK)  # only "en" / "hi" — no other languages

LANG_SELECT_MESSAGE = "🌐 Please choose your language / भाषा चुनें:"
LANG_SELECT_KEYBOARD = {
    "inline_keyboard": [[
        {"text": "🇮🇳 हिन्दी", "callback_data": "hi_start"},
        {"text": "🇬🇧 English", "callback_data": "en_start"},
    ]]
}


# ─── Keyboards ──────────────────────────────────────────────────────────────
def main_keyboard(lang: str) -> dict:
    if lang == "hi":
        return {
            "inline_keyboard": [
                [
                    {"text": "📖 Markdown गाइड", "callback_data": "hi_help_md"},
                    {"text": "🌐 HTML गाइड", "callback_data": "hi_help_html"},
                ],
                [
                    {"text": "🖼 मीडिया गाइड", "callback_data": "hi_help_media"},
                    {"text": "🧩 एडवांस्ड 10.1", "callback_data": "hi_help_adv"},
                ],
                [
                    {"text": "🎨 फुल डेमो", "callback_data": "hi_demo"},
                    {"text": "⚡ स्ट्रीमिंग डेमो", "callback_data": "hi_stream"},
                ],
                [
                    {"text": "ℹ️ बॉट के बारे में", "callback_data": "hi_about"},
                ],
                [
                    {"text": "🇬🇧 Switch to English", "callback_data": "en_start"},
                ],
            ]
        }
    return {
        "inline_keyboard": [
            [
                {"text": "📖 Markdown Guide", "callback_data": "en_help_md"},
                {"text": "🌐 HTML Guide", "callback_data": "en_help_html"},
            ],
            [
                {"text": "🖼 Media Guide", "callback_data": "en_help_media"},
                {"text": "🧩 Advanced 10.1", "callback_data": "en_help_adv"},
            ],
            [
                {"text": "🎨 Full Demo", "callback_data": "en_demo"},
                {"text": "⚡ Streaming Demo", "callback_data": "en_stream"},
            ],
            [
                {"text": "ℹ️ About", "callback_data": "en_about"},
            ],
            [
                {"text": "🇮🇳 हिन्दी में बदलें", "callback_data": "hi_start"},
            ],
        ]
    }


def ai_lang(from_user: dict) -> str:
    """Hindi/English only — anything else (Telegram's own language_code, e.g.
    'ru', 'it', 'fr'...) safely falls back to English."""
    code = (from_user or {}).get("language_code", "") or ""
    return "hi" if code.lower().startswith("hi") else "en"


def ai_ask_text(lang: str) -> str:
    return AI_TXT[lang]["ask"].format(bot=BOT_USERNAME or "your_bot")


def dev_keyboard(lang: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": AI_TXT[lang]["dev_btn"], "url": f"https://t.me/{DEV_USERNAME}"}
        ]]
    }


def back_keyboard(lang: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "⬅️ मेनू पर वापस जाएं", "callback_data": "hi_back"}
                if lang == "hi"
                else {"text": "⬅️ Back to Menu", "callback_data": "en_back"},
                {"text": "🇬🇧 English", "callback_data": "en_start"}
                if lang == "hi"
                else {"text": "🇮🇳 हिन्दी", "callback_data": "hi_start"},
            ]
        ]
    }


# ─── UTF-16 aware slicing helpers ──────────────────────────────────────────
# Telegram MessageEntity offset/length are counted in UTF-16 code units.
# Python strings are indexed by Unicode code points, so with emoji / rare
# characters outside the BMP a naive text[offset:offset+length] slice can
# land in the wrong place. We slice on the UTF-16LE byte representation
# instead, which matches Telegram's (and JavaScript's) native indexing.
def _utf16_slice(text: str, start: int, end: int) -> str:
    b = text.encode("utf-16-le")
    return b[start * 2:end * 2].decode("utf-16-le", errors="ignore")


# ─── Convert Telegram message entities back into Markdown/HTML source ─────
def entities_to_markdown(text: str, entities) -> str:
    if not entities:
        return text

    items = [
        {"e": e, "idx": i, "start": e["offset"], "end": e["offset"] + e["length"]}
        for i, e in enumerate(entities)
    ]

    def is_top_level(item, pool):
        for other in pool:
            if other["idx"] == item["idx"]:
                continue
            strictly_larger = (
                other["start"] <= item["start"]
                and other["end"] >= item["end"]
                and (other["start"] < item["start"] or other["end"] > item["end"])
            )
            same_span_outer = (
                other["start"] == item["start"]
                and other["end"] == item["end"]
                and other["idx"] < item["idx"]
            )
            if strictly_larger or same_span_outer:
                return False
        return True

    def render(start, end, pool):
        in_range = [it for it in pool if it["start"] >= start and it["end"] <= end]
        top = sorted(
            (it for it in in_range if is_top_level(it, in_range)),
            key=lambda it: it["start"],
        )

        out = []
        pos = start
        for item in top:
            out.append(_utf16_slice(text, pos, item["start"]))
            inner_pool = [p for p in pool if p["idx"] != item["idx"]]
            inner = render(item["start"], item["end"], inner_pool)
            out.append(wrap_entity(item["e"], inner))
            pos = item["end"]
        out.append(_utf16_slice(text, pos, end))
        return "".join(out)

    return render(0, len(text.encode("utf-16-le")) // 2, items)


def wrap_entity(e: dict, content: str) -> str:
    t = e.get("type")
    if t == "bold":
        return f"**{content}**"
    if t == "italic":
        return f"*{content}*"
    if t == "underline":
        return f"<u>{content}</u>"
    if t == "strikethrough":
        return f"~~{content}~~"
    if t == "spoiler":
        return f"||{content}||"
    if t == "code":
        return f"`{content}`"
    if t == "pre":
        lang = e.get("language") or ""
        return f"```{lang}\n{content}\n```"
    if t == "text_link":
        return f"[{content}]({e.get('url', '')})"
    if t == "text_mention":
        user = e.get("user")
        return f"[{content}](tg://user?id={user['id']})" if user else content
    if t in ("blockquote", "expandable_blockquote"):
        return "\n".join(f">{line}" for line in content.split("\n"))
    if t == "custom_emoji":
        # Established Bot API HTML syntax for custom emoji (Bot API 6.2+)
        return f'<tg-emoji emoji-id="{e.get("custom_emoji_id", "")}">{content}</tg-emoji>'
    if t == "date_time":
        # Rich Message date/time entity (Bot API 9.5 field, 10.1 rich rendering)
        unix_time = e.get("unix_time", "")
        fmt = e.get("date_time_format", "")
        return f'<tg-date-time unix-time="{unix_time}" format="{fmt}">{content}</tg-date-time>'
    # mention, hashtag, cashtag, bot_command, url, email, phone_number:
    # Telegram never strips these from the raw text, so no wrapping needed.
    return content


# ─── Telegram API helpers ──────────────────────────────────────────────────
_session = requests.Session()


def call_api(method: str, body: dict, notify_on_error: bool = True):
    try:
        res = _session.post(
            f"{TELEGRAM_API}/{method}", json=body, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException as exc:
        log.error("[%s] network error: %s", method, exc)
        return None

    if not res.ok:
        log.error("[%s] %s: %s", method, res.status_code, res.text)
        if notify_on_error and body.get("chat_id") and method != "sendMessage":
            try:
                _session.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": body["chat_id"],
                        "text": f"⚠️ Error ({res.status_code}): {res.text[:300]}",
                    },
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.exceptions.RequestException:
                pass
        return None

    try:
        return res.json()
    except ValueError:
        return None


def send_plain(chat_id, text, reply_markup=None):
    body = {"chat_id": chat_id, "text": text}
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("sendMessage", body)


def send_rich_markdown(chat_id, markdown, reply_markup=None):
    body = {"chat_id": chat_id, "rich_message": {"markdown": markdown}}
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("sendRichMessage", body)


def send_rich_html(chat_id, html, reply_markup=None):
    body = {"chat_id": chat_id, "rich_message": {"html": html}}
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("sendRichMessage", body)


def edit_rich_markdown(chat_id, message_id, markdown, reply_markup=None):
    body = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": {"markdown": markdown},
    }
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("editMessageText", body)


def send_rich_message_draft(chat_id, draft_id, markdown):
    # sendRichMessageDraft streams an ephemeral (~30s) preview of a rich
    # message while it is still being generated. It must be followed by a
    # real sendRichMessage call to persist anything in the chat.
    body = {
        "chat_id": chat_id,
        "draft_id": draft_id,
        "rich_message": {"markdown": markdown},
    }
    return call_api("sendRichMessageDraft", body, notify_on_error=False)


def answer_callback_query(callback_query_id):
    call_api("answerCallbackQuery", {"callback_query_id": callback_query_id}, notify_on_error=False)


def edit_rich_markdown_inline(inline_message_id, markdown, reply_markup=None):
    # Same as edit_rich_markdown, but for messages that came from an inline
    # query result (identified by inline_message_id, no chat_id/message_id).
    body = {
        "inline_message_id": inline_message_id,
        "rich_message": {"markdown": markdown},
    }
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("editMessageText", body, notify_on_error=False)


def edit_plain_inline(inline_message_id, text, reply_markup=None, parse_mode=None):
    body = {"inline_message_id": inline_message_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    if reply_markup:
        body["reply_markup"] = reply_markup
    return call_api("editMessageText", body, notify_on_error=False)


def answer_inline_query(inline_query_id, results, cache_time=0):
    return call_api(
        "answerInlineQuery",
        {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": True,
        },
        notify_on_error=False,
    )


# ─── /ai command (external chat-completion API) ────────────────────────────
def ask_ai(question: str):
    """Returns (ok, answer_or_error_text)."""
    try:
        res = requests.get(
            AI_API_URL,
            params={"message": question, "style": "chatgpt-alternative"},
            timeout=AI_REQUEST_TIMEOUT,
        )
        data = res.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        log.error("AI API error: %s", exc)
        return False, None
    if data.get("status") == 200 and data.get("response"):
        return True, data["response"]
    return False, None


def handle_inline_query(iq: dict):
    lang = ai_lang(iq.get("from"))
    query = (iq.get("query") or "").strip()

    if not query:
        # Empty query -> show a hint article using plain text (guaranteed to
        # work everywhere, no rich_message dependency for the hint itself).
        results = [{
            "id": "ask",
            "type": "article",
            "title": ai_ask_text(lang).split("\n")[0],
            "description": ai_ask_text(lang),
            "input_message_content": {
                "message_text": ai_ask_text(lang),
            },
        }]
        answer_inline_query(iq["id"], results)
        return

    result_id = uuid.uuid4().hex
    placeholder = f"💬 {query}\n\n{AI_TXT[lang]['thinking']}"
    results = [{
        "id": result_id,
        "type": "article",
        "title": AI_TXT[lang]["inline_title"] + query,
        "description": AI_TXT[lang]["inline_desc"],
        # Plain InputTextMessageContent here on purpose — this is the part
        # Telegram must accept for the picker to even show a result. Once
        # chosen, /handle_chosen_inline_result below upgrades it to a real
        # rich_message via editMessageText.
        "input_message_content": {
            "message_text": placeholder,
            "parse_mode": "Markdown",
        },
        "reply_markup": dev_keyboard(lang),
    }]
    answer_inline_query(iq["id"], results)


def handle_chosen_inline_result(cir: dict):
    lang = ai_lang(cir.get("from"))
    kb = dev_keyboard(lang)
    query = (cir.get("query") or "").strip()
    inline_message_id = cir.get("inline_message_id")
    if not query or not inline_message_id:
        return

    ok, answer = ask_ai(query)
    final_markdown = (
        f"💬 **{query}**\n\n🤖 {answer}" if ok else f"💬 **{query}**\n\n{AI_TXT[lang]['error']}"
    )

    # Bot API 10.1 rich_message first; if the API/client rejects it for any
    # reason, fall back to a plain Markdown edit so the user still gets an
    # answer instead of being stuck on "Thinking...".
    result = edit_rich_markdown_inline(inline_message_id, final_markdown, kb)
    if result is None:
        edit_plain_inline(inline_message_id, final_markdown, kb, parse_mode="Markdown")


# ─── Broadcast system (admin only) ─────────────────────────────────────────
def load_users() -> set:
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, ValueError):
        return set()


def save_users(users: set):
    try:
        with open(USERS_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(users), f)
    except OSError as exc:
        log.error("Could not save users.json: %s", exc)


KNOWN_USERS = load_users()


def track_user(chat_id):
    if chat_id not in KNOWN_USERS:
        KNOWN_USERS.add(chat_id)
        save_users(KNOWN_USERS)


def is_admin(user_id) -> bool:
    return user_id in ADMIN_IDS


def handle_broadcast_command(message: dict):
    chat_id = message["chat"]["id"]
    from_id = (message.get("from") or {}).get("id")

    if not is_admin(from_id):
        return  # silently ignore — don't reveal the command exists to non-admins

    raw = (message.get("text") or "").strip()
    text = raw.split(None, 1)[1].strip() if " " in raw else ""
    if not text:
        send_plain(chat_id, "Usage: /broadcast <message>\n\nSupports **Markdown** formatting.")
        return

    targets = list(KNOWN_USERS)
    send_plain(chat_id, f"📢 Broadcasting to {len(targets)} user(s)...")

    sent, failed = 0, 0
    for target_id in targets:
        result = send_rich_markdown(target_id, text)
        if result and result.get("ok"):
            sent += 1
        else:
            failed += 1
        time.sleep(BROADCAST_DELAY)

    send_plain(chat_id, f"✅ Broadcast done — sent: {sent}, failed: {failed}")


# ─── Handlers ───────────────────────────────────────────────────────────────
def handle_message(message: dict):
    chat_id = message["chat"]["id"]
    raw_text = message.get("text")
    if raw_text is None:
        return
    trimmed = raw_text.strip()

    track_user(chat_id)

    if trimmed in ("/start", "/help"):
        send_plain(chat_id, LANG_SELECT_MESSAGE, LANG_SELECT_KEYBOARD)
        return

    if trimmed == "/broadcast" or trimmed.startswith("/broadcast "):
        handle_broadcast_command(message)
        return

    # Telegram clients auto-format **bold**, ```code```, etc. typed by the
    # user into formatting entities and STRIP the raw markdown syntax from
    # message.text. Reconstruct the original Markdown/HTML from
    # text + entities before echoing it back as a rich message.
    text = entities_to_markdown(raw_text, message.get("entities")).strip()
    if not text:
        text = trimmed

    if text.startswith("<") or any(c == "<" for c in text[:200]):
        send_rich_html(chat_id, text)
    else:
        send_rich_markdown(chat_id, text)


def handle_callback(cb: dict):
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]
    data = cb.get("data", "")

    answer_callback_query(cb["id"])

    lang = "hi" if data.startswith("hi_") else "en"
    action = data[3:]  # strip "hi_" / "en_"

    kb = back_keyboard(lang)
    main = main_keyboard(lang)

    if action in ("start", "back"):
        edit_rich_markdown(chat_id, msg_id, WELCOME[lang], main)
    elif action == "help_md":
        edit_rich_markdown(chat_id, msg_id, HELP_MD[lang], kb)
    elif action == "help_html":
        edit_rich_markdown(chat_id, msg_id, HELP_HTML[lang], kb)
    elif action == "help_media":
        edit_rich_markdown(chat_id, msg_id, HELP_MEDIA[lang], kb)
    elif action == "help_adv":
        edit_rich_markdown(chat_id, msg_id, HELP_ADV[lang], kb)
    elif action == "demo":
        edit_rich_markdown(chat_id, msg_id, DEMO[lang], kb)
    elif action == "about":
        edit_rich_markdown(chat_id, msg_id, ABOUT[lang], kb)
    elif action == "stream":
        run_streaming_demo(chat_id, lang, kb)


def run_streaming_demo(chat_id, lang, reply_markup):
    """Demonstrates sendRichMessageDraft -> sendRichMessage (Bot API 10.1)."""
    frames = STREAM_DEMO_FRAMES.get(lang, STREAM_DEMO_FRAMES["en"])
    draft_id = random.randint(1, 2_147_483_647)  # draft_id must be non-zero

    for frame in frames:
        send_rich_message_draft(chat_id, draft_id, frame)
        time.sleep(0.6)

    final_text = STREAM_DEMO_FRAMES["final"].get(lang, STREAM_DEMO_FRAMES["final"]["en"])
    send_rich_markdown(chat_id, final_text, reply_markup)


def process_update(update: dict):
    message = update.get("message")
    callback_query = update.get("callback_query")
    inline_query = update.get("inline_query")
    chosen_inline_result = update.get("chosen_inline_result")

    try:
        if callback_query:
            handle_callback(callback_query)
        elif inline_query:
            handle_inline_query(inline_query)
        elif chosen_inline_result:
            handle_chosen_inline_result(chosen_inline_result)
        elif message and "text" in message:
            handle_message(message)
    except Exception:
        log.error("Handler error:\n%s", traceback.format_exc())
        chat_id = None
        if message:
            chat_id = message.get("chat", {}).get("id")
        elif callback_query:
            chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        if chat_id:
            send_plain(chat_id, "⚠️ Internal error, please try again.")


# ─── Long-polling main loop ─────────────────────────────────────────────────
def get_updates(offset):
    body = {"timeout": POLL_TIMEOUT}
    if offset is not None:
        body["offset"] = offset
    try:
        res = _session.post(
            f"{TELEGRAM_API}/getUpdates", json=body, timeout=REQUEST_TIMEOUT
        )
        res.raise_for_status()
        return res.json().get("result", [])
    except requests.exceptions.RequestException as exc:
        log.error("getUpdates failed: %s", exc)
        time.sleep(RETRY_DELAY)
        return []


def main():
    global BOT_USERNAME

    if not BOT_TOKEN or BOT_TOKEN == "Enter your Telegram bot token":
        log.error(
            "BOT_TOKEN is not set. Set the BOT_TOKEN environment variable "
            "(Wispbyte: server Startup tab -> Variables) before starting the bot."
        )
        sys.exit(1)

    me = call_api("getMe", {}, notify_on_error=False)
    if me and me.get("ok"):
        BOT_USERNAME = me["result"]["username"]
        log.info("✅ Logged in as @%s — TeleRich (Bot API 10.1) is running.", BOT_USERNAME)
    else:
        log.warning("Could not verify bot token via getMe — continuing anyway.")

    if DEV_USERNAME == "YOUR_USERNAME":
        log.warning("DEV_USERNAME is still the placeholder — edit it near the top of bot.py.")
    if ADMIN_IDS == {123456789}:
        log.warning("ADMIN_IDS is still the placeholder — /broadcast won't work for you "
                    "until you set your real numeric Telegram user ID near the top of bot.py.")
    log.info("Broadcast list currently has %d known user(s).", len(KNOWN_USERS))

    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            process_update(update)


if __name__ == "__main__":
    main()
