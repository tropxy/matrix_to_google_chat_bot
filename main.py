import sys
import logging
from logging import StreamHandler, FileHandler
import requests
from nio import AsyncClient, RoomMessageText, MatrixRoom, SyncResponse
from nio.events.room_events import Event
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# LOGGER LEVEL
LOG_LEVEL = os.getenv("LOG_LEVEL", logging.INFO)
LOG_FILE = "/tmp/matrix_to_google_chat_hook.log"
# Matrix Home server
MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER")
# Matrix User credentials
MATRIX_USER = os.getenv("MATRIX_USER")
MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
# Matrix Base URL
MATRIX_BASE_URL = os.getenv("MATRIX_BASE_URL")
# Chat Room ID that we want specifically to listen to
MATRIX_VALEO_ROOM = os.getenv("MATRIX_VALEO_ROOM")
# E2E keys related to the user account and necessary
# for the bot to be trusted
MATRIX_E2E_KEYS_FILE = os.getenv("MATRIX_E2E_KEYS_FILE")
MATRIX_E2E_KEYS_FILE_PASS = os.getenv("MATRIX_E2E_KEYS_FILE_PASS")
# Location of where to save the NoSQL DB to
MATRIX_DB_LOCATION = os.getenv("MATRIX_DB_LOCATION")
# Google Chat webhook URL
GOOGLE_CHAT_WEBHOOK = os.getenv("GOOGLE_CHAT_WEBHOOK")

# To track that sync is complete
initial_sync_complete = False

# Silence other loggers
logging.getLogger("nio").setLevel(logging.WARNING)  # Suppress matrix-nio's INFO logs
# Configure logging to log to both stdout and file
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        StreamHandler(sys.stdout),           # Print to stdout
        FileHandler(LOG_FILE, mode="w"),     # Write to log file
    ],
)
logger = logging.getLogger()

async def message_listener():
    global initial_sync_complete
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER, store_path=MATRIX_DB_LOCATION)
    await client.login(MATRIX_PASSWORD)
    logger.info("Bot Logged into Matrix")
    # This imports the E2E keys extracted from my user account at app.element.io, which allow this bot to be trusted and be able
    # to decrypt the messages sent by other uses in an E2E chat where my user is present
    await client.import_keys(MATRIX_E2E_KEYS_FILE, MATRIX_E2E_KEYS_FILE_PASS)

    async def prepare_and_send_message(event: Event, room):
        message_text = event.body
        room_name = room.display_name

        # Fetch the sender's display name
        sender_response = await client.get_displayname(event.sender)
        # Fallback if display name is not available
        sender_display_name = sender_response.displayname if sender_response and sender_response.displayname else event.sender
        # Create permalink URL for the message
        message_url = f"{MATRIX_BASE_URL}/{room.room_id}/{event.event_id}"
        full_message = (
            f"Room: {room_name}\n"
            f"Author: {sender_display_name}\n"
            f"Message: {message_text}\n"
            f"Link: {message_url}"
        )
        send_to_google_chat(full_message)

    async def message_callback(room, event):
        global initial_sync_complete
        if not initial_sync_complete:
            return
        # Just send notifications to the google chat if the messages are coming from
        # the Valeo chat group (we dont want to expose private ones)
        if room.room_id != MATRIX_VALEO_ROOM:
            pass
        try:
            if isinstance(event, RoomMessageText):
                # Handle plaintext messages
                await prepare_and_send_message(event, room)
            else:
                # Handle other events (e.g., encrypted)
                try:
                    decrypted_event = await client.decrypt_event(event)
                    if decrypted_event and hasattr(decrypted_event, "body"):
                        await prepare_and_send_message(decrypted_event, room)
                except Exception as e:
                    logger.error(f"Failed to decrypt event: {e}")
        except Exception as e:
            logger.error(f"Failed to decrypte message/event. {e}")
            # Catch decryption errors and send a notification
            room_link = f"{MATRIX_BASE_URL}/{room.room_id}"
            error_message = (
                f"⚠️ **Decryption Error**\n"
                f"Room: {room.display_name} ({room.room_id})\n"
                f"Link: {room_link}\n"
                f"Error: Undecryptable message received. Please check the chat UI."
            )
            send_to_google_chat(error_message)

    async def on_sync_completed(response: SyncResponse):
        global initial_sync_complete
        if not initial_sync_complete:
            logger.info("Initial sync completed. Listening for new messages...")
            initial_sync_complete = True

    # Register callbacks
    client.add_event_callback(message_callback, RoomMessageText)
    client.add_response_callback(on_sync_completed)

    logger.info("Starting sync...")
    await client.sync_forever(timeout=30000)



def send_to_google_chat(message):
    """Send message to Google Chat via webhook."""
    data = {"text": message}
    response = requests.post(GOOGLE_CHAT_WEBHOOK, json=data)
    if response.status_code == 200:
        logger.debug(f"Message sent to Google Chat: {message}")
    else:
        logger.error(f"Failed to send message: {response.text}")

# Start the script
asyncio.run(message_listener())

