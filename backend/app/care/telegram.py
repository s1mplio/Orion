import os

import requests


TELEGRAM_API = "https://api.telegram.org"

REQUEST_TIMEOUT = 15


def bot_token():
    """Bot token from @BotFather, set as ORION_TELEGRAM_BOT_TOKEN."""
    return os.getenv("ORION_TELEGRAM_BOT_TOKEN", "").strip()


def is_configured():
    return bool(bot_token())


def _call(method, **payload):
    token = bot_token()

    if not token:
        raise RuntimeError(
            "Telegram is not configured. Set ORION_TELEGRAM_BOT_TOKEN "
            "and restart the backend."
        )

    response = requests.post(
        f"{TELEGRAM_API}/bot{token}/{method}",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram error: {data.get('description', response.status_code)}"
        )

    return data["result"]


def send_message(chat_id, text):
    return _call("sendMessage", chat_id=chat_id, text=text)


def recent_chats():
    """
    People who recently messaged the bot (e.g. sent /start),
    so the caregiver can add them without copying chat IDs.
    """

    chats = {}

    for update in _call("getUpdates"):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}

        if chat.get("type") != "private" or "id" not in chat:
            continue

        name = " ".join(
            part for part in (chat.get("first_name"), chat.get("last_name")) if part
        ) or chat.get("username") or "Telegram user"

        chats[str(chat["id"])] = name

    return [
        {"telegram_chat_id": chat_id, "name": name}
        for chat_id, name in chats.items()
    ]


def notify_family(contacts, text):
    """Send to every contact. Returns the number delivered."""
    delivered = 0

    for contact in contacts:
        try:
            send_message(contact["telegram_chat_id"], text)
            delivered += 1
        except Exception as error:
            print(
                "TELEGRAM_SEND_ERROR:",
                contact.get("name"),
                repr(error),
            )

    return delivered
