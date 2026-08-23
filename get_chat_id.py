"""Find your Telegram chat id, and check the bot token actually works.

    python get_chat_id.py 8134567890:AAHdEfGh...

Paste the token BotFather gave you as the argument. The token is only sent to
Telegram's own API - it is not stored or written anywhere.
"""

import sys

import requests


def main() -> None:
    token = (sys.argv[1] if len(sys.argv) > 1 else "").strip().strip("<>").strip()
    if not token:
        print(__doc__)
        sys.exit(1)

    if ":" not in token:
        print("That does not look like a full token. BotFather's token has two parts\n"
              "joined by a colon, e.g. 8134567890:AAHdEfGhIjKlMnOp...\n"
              "You may have copied only the first half.")
        sys.exit(1)

    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20)
    if r.status_code == 404 or not r.json().get("ok"):
        print("Telegram rejected this token (404 = token not recognised).\n"
              "Open your BotFather chat and copy the token again - the whole line,\n"
              "including the part after the colon. If in doubt, send BotFather\n"
              "/mybots, pick your bot, then 'API Token'.")
        sys.exit(1)

    bot = r.json()["result"]
    print(f"Token is valid - bot is @{bot['username']}\n")

    upd = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                       timeout=20).json()
    chats = {}
    for u in upd.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            who = chat.get("first_name") or chat.get("title") or chat.get("username", "")
            chats[chat["id"]] = who

    if not chats:
        print("Token works, but your bot has not received any message yet.\n\n"
              f"Open Telegram, search for @{bot['username']}, tap START and send it\n"
              "any message (e.g. 'hi'). Then run this command again.")
        sys.exit(1)

    print("Found your chat id:\n")
    for cid, who in chats.items():
        print(f"  TELEGRAM_CHAT_ID = {cid}    ({who})")
    print("\nAdd that number as the TELEGRAM_CHAT_ID secret on GitHub,\n"
          "and the token as TELEGRAM_TOKEN.")


if __name__ == "__main__":
    main()
