import sys
import logging
import requests
import asyncio
import os

from nio import AsyncClient, RoomMessageText, MatrixRoom, SyncResponse, ClientConfig
from nio.events.room_events import Event
from typing import Optional
from dotenv import load_dotenv
from logging import StreamHandler, FileHandler


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
# Environmental to force receiving all messages from any channel
MATRIX_GET_ALL_MESSAGES = os.getenv("MATRIX_GET_ALL_MESSAGES", False).lower() == "true"
# Chat Room ID that we want specifically to listen to
MATRIX_FILTER_FOR_ROOM_ID = os.getenv("MATRIX_FILTER_FOR_ROOM_ID")
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
    client = AsyncClient(MATRIX_HOMESERVER, MATRIX_USER, device_id="google_chat_bot", store_path=MATRIX_DB_LOCATION)
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
        logger.info(f"Message received from room id {room.room_id}")
        if (room.room_id != MATRIX_FILTER_FOR_ROOM_ID) and (MATRIX_GET_ALL_MESSAGES is False):
            logger.info(f"Message {event.body} from Room {room.display_name}, Ignored")
            return
        try:
            if isinstance(event, RoomMessageText):
                # Handle plaintext messages
                logger.debug(f"Received {event.body} from Room {room.display_name}, processing...")
                await prepare_and_send_message(event, room)
            else:
                # Handle other events (e.g., encrypted)
                try:
                    logger.debug(f"Received Encrypted {event.body} from Room {room.display_name}, processing...")
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
            #await client.room_send(
                # # Watch out! If you join an old room you'll see lots of old messages
                # room_id="!FiDziuxXnATHZcWjUW:matrix.org",
                # message_type="m.room.message",
                # content={"msgtype": "m.text", "body": "Hello world!"},
            # )
            await trust_devices("@romain_valeo:matrix.org")
            await trust_devices("@damien-valeo:matrix.org")
            await trust_devices("@shalinnijel:matrix.org")
            await trust_devices("@andre_d:matrix.org")
            await trust_devices("@hmercier:im.iot.bzh")
            await trust_devices("@fulup:im.iot.bzh")

    async def trust_devices(user_id: str, device_list: Optional[str] = None) -> None:
        """Trusts the devices of a user.

        If no device_list is provided, all of the users devices are trusted. If
        one is provided, only the devices with IDs in that list are trusted.

        Arguments:
            user_id {str} -- the user ID whose devices should be trusted.

        Keyword Arguments:
            device_list {Optional[str]} -- The full list of device IDs to trust
                from that user (default: {None})
        """

        logger.info(f"{user_id}'s device store: {client.device_store[user_id]}")

        # The device store contains a dictionary of device IDs and known
        # OlmDevices for all users that share a room with us, including us.

        # We can only run this after a first sync. We have to populate our
        # device store and that requires syncing with the server.
        for device_id, olm_device in client.device_store[user_id].items():
            if device_list and device_id not in device_list:
                # a list of trusted devices was provided, but this ID is not in
                # that list. That's an issue.
                logger.info(
                    f"Not trusting {device_id} as it's not in {user_id}'s pre-approved list."
                )
                continue

            # if user_id == client.user_id and device_id == client.device_id:
                # # We cannot explicitly trust the device andre is using
                # continue

            client.verify_device(olm_device)
            logger.info(f"Trusting {device_id} from user {user_id}")

    ## This Key verification code is not working (the EVent is never received here...)
    # But check here for a possible solution:
    #    https://github.com/matrix-nio/matrix-nio/issues/430
    # from nio import KeyVerificationStart, KeyVerificationKey, KeyVerificationMac, KeyVerificationEvent

    # async def verification_callback(event: KeyVerificationEvent, room: MatrixRoom):
        # logger.info(f"Received verification request from {event.sender}")
        # # Automatically accept verification from a trusted user
        # if event.sender == "@andre_d:matrix.org":  # Replace with your trust condition
            # accept_event = KeyVerificationAccept.from_key_verification_start(
                # event,
                # method="m.sas.v1",  # SAS method, adjust if using a different method
                # key_agreement_protocols=["curve25519-hkdf-sha256"],
                # hashes=["sha256"],
                # message_authentication_codes=["hkdf-hmac-sha256"],
                # short_authentication_string=["decimal"],
            # )
            # await client.send_to_device(accept_event)

        # # Further steps would involve handling the exchanged keys and finalizing the verification
        # # This is typically handled by `matrix-nio` but may require additional customization


    # Register callbacks
    client.add_event_callback(message_callback, RoomMessageText)
    client.add_response_callback(on_sync_completed)
    # Register the callback for key verification start events
    # client.add_event_callback(verification_callback, KeyVerificationEvent)
    logger.info("Starting sync...")
    await client.sync_forever(timeout=29999)




def send_to_google_chat(message):
    """Send message to Google Chat via webhook."""
    data = {"text": message}
    response = requests.post(GOOGLE_CHAT_WEBHOOK, json=data)
    if response.status_code == 200:
        logger.info(f"✅ - Message sent to Google Chat: {message}")
    else:
        logger.error(f"❌ - Failed to send message: {response.text}")

# Start the script
asyncio.run(message_listener())

