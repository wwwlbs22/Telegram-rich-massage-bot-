<div align="center">
   
# 🤖 Telegram [Rich Markdown](https://core.telegram.org/bots/api#rich-message-formatting-options) & HTML Bot

<a href="#english-version-us">🇺🇸 English</a> | <a href="#हिंदी">🇮🇳हिंदी</a>
  
Live Demo Bot: [@Reachmassegeaibot](https://t.me/Reachmassegeaibot)

[![GitHub Repo](https://img.shields.io/badge/Repo-TeleRich-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/wwwlbs22/Telegram-rich-massage-bot-)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-10.1-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)

![Status](https://img.shields.io/badge/status-active-success?style=flat-square)
![Markdown](https://img.shields.io/badge/Markdown-supported-blue?style=flat-square&logo=markdown)
![HTML](https://img.shields.io/badge/HTML-supported-orange?style=flat-square&logo=html5)
![Bilingual](https://img.shields.io/badge/Languages-EN%20%7C%20HI-9cf?style=flat-square)
![No Database](https://img.shields.io/badge/Database-none%20needed-lightgrey?style=flat-square)

</div>



---
<a id="english-version-us"></a>
## 🇬🇧 English


### 🚀 Features

- **🔁 Live Markdown → Rich Message rendering** — type Markdown, get a fully rendered rich message back.
- **🌐 Live HTML → Rich Message rendering** — messages starting with `<` (or containing HTML tags) are rendered as HTML.
- **🧠 Entity reconstruction engine** — Telegram strips raw `**bold**`, `` ```code``` ``, etc. from `message.text` and converts them into formatting *entities*. This bot **rebuilds the original Markdown/HTML source** from those entities (including nested formatting like bold-italic-underline combinations, blockquotes, spoilers, links, mentions, and code blocks) before re-rendering.
- **🌍 Full bilingual interface (English / Persian)** — every menu, button, and help page is available in both languages with one-tap switching.
- **📖 Interactive Markdown Guide** — live, side-by-side "type this → get this" examples covering:
  - Text styles: bold, italic, strikethrough, inline code, highlight (`==mark==`), spoilers
  - Headings (H1–H6)
  - Ordered & unordered lists, task lists (`- [ ]` / `- [x]`)
  - Links, single-line and multi-line blockquotes
  - Dividers, fenced code blocks with syntax highlighting
  - Tables with column alignment
  - Inline and block LaTeX math (`$...$` and `$$...$$`)
  - Collapsible `<details>` / `<summary>` sections (with nested Markdown, tables & code inside)
- **🌐 Interactive HTML Guide** — equivalent reference for raw HTML formatting tags supported by Telegram.
- **🖼 Media Guide** — demonstrates rich media embedding via Markdown image syntax and `<tg-map>` / `<tg-slideshow>` tags:
  - Photos, videos, audio, voice notes (`.ogg`), animations/GIFs
  - Captions for any media type
  - Combined slideshows with multiple items + captions
  - Live location maps (`<tg-map lat="..." long="..." zoom="..."/>`)
- **🎨 Full Demo mode** — a single message showcasing *every* feature at once (nested formatting, tables, math, code, collapsible sections, slideshows).
- **ℹ️ About page** — author/credits page with social links.
- **🛡 Bulletproof error handling** — the worker **always returns HTTP 200** to Telegram (even on internal errors), preventing Telegram from auto-disabling the webhook. Errors are logged and, where possible, reported directly to the chat.
- **⚡ Inline keyboard navigation** — persistent back/menu/language-switch buttons on every screen.

### 🧩 How It Works

1. Telegram sends an `update` (message or callback query) to your Worker via webhook (POST request).
2. If it's a **callback query** (button press) → the bot edits the existing message to show the requested menu/guide/demo.
3. If it's a **text message**:
   - `/start` or `/help` → shows the language selection screen.
   - Otherwise → the bot reconstructs the original Markdown/HTML from the message's formatting entities, detects whether it's HTML or Markdown, and sends it back as a `rich_message`.
4. The Worker responds `200 OK` to Telegram in all cases (per Telegram's webhook requirements).


### 🛠 Setup & Deployment

#### 1. Create your bot with BotFather
1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** you receive (looks like `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`)


   > 💡 **Recommended (more secure):** instead of hardcoding the token, use a Cloudflare **Secret** (see step 4) and change this line to:
   > ```js
   > const BOT_TOKEN = env.BOT_TOKEN;
   > ```
   > (and update the `fetch(request, env)` signature accordingly)


#### 4. (Recommended) Store the token as a secret instead of hardcoding it
1. In your Worker's page on the Cloudflare dashboard, go to **Settings → Variables and Secrets**
2. Click **Add** → set type to **Secret**, name it `BOT_TOKEN`, paste your token, and **Save and Deploy**

Then update the worker to read `env.BOT_TOKEN` instead of a hardcoded string, and pass `env` into the `fetch` handler:
```js
export default {
  async fetch(request, env) {
    const TELEGRAM_API = `https://api.telegram.org/bot${env.BOT_TOKEN}`;
    // ...
  }
};
```

#### 5. Set the Telegram webhook
Point Telegram at your Worker URL by visiting this URL in a browser (or via `curl`):
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<your-worker>.workers.dev
```
A successful response looks like:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

#### 6. Test it!
1. Open your bot in Telegram and send `/start`
2. Choose your language (🇮🇳हिंदी / 🇬🇧 English)
3. Try the **Markdown Guide**, **HTML Guide**, **Media Guide**, and **Full Demo** buttons
4. Send your own Markdown/HTML text, e.g.:
   ```
   **Hello** _world_! Here's a [link](https://telegram.org) and a table:

   | A | B |
   |---|---|
   | 1 | 2 |
   ```

### 🔍 Verifying the webhook
Check webhook status anytime:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

### ⚠️ Notes & Limits

- Telegram rich messages are limited to **32,768 characters** per message.
- `sendRichMessage` / `rich_message` / `<tg-map>` / `<tg-slideshow>` are part of **Bot API 10.1** — make sure your bot client/library and Telegram app are up to date to see full rendering.
- The worker logs errors via `console.error`, viewable in the Cloudflare dashboard under **Workers & Pages → your worker → Logs** (enable "Real-time Logs" or use `wrangler tail`).

### 📄 License & Credits

Released under the **MIT License** — free to use, modify, and distribute, with attribution appreciated.



⭐ Star the project: **[https://github.com/wwwlbs22/Telegram-rich-massage-bot-](https://github.com/wwwlbs22/Telegram-rich-massage-bot-)**

---
