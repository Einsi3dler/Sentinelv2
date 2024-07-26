from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import random
import string
import mysql.connector
from datetime import datetime, timedelta
import logging
import os
import yara
import asyncio
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MySQL Configuration
def connect_db():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="sentinel",
            password="password",
            database="my_telegram_bot"
        )
        logger.info("Connected to the MySQL database successfully.")
        return db
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
        exit()

db = connect_db()
cursor = db.cursor()

# Telegram Configuration
api_id = '27619061'
api_hash = '044736b403fee3d0978cdd9e4881f91d'
bot_token = '6321087523:AAFC8ucN4DL1FiZp2rIB5j88SkfPBc0tTW4'
admin_user_id = 914357068  # Replace with your actual user ID

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# YARA Configuration
yara_rules = yara.compile(filepath='malware_rules.yar')

def generate_eth_wallet_address():
    wallet_address = '0x' + ''.join(random.choices(string.hexdigits.lower(), k=40))
    return wallet_address

@app.on_message(filters.command("escrow") & filters.group)
async def initiate_escrow(client, message):
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.reply_text("Usage: /escrow <sender_id> <receiver_id>")
            logger.info("Usage message sent due to incorrect number of arguments.")
            return

        sender_id = int(args[1])
        receiver_id = int(args[2])
        escrow_uid = str(uuid.uuid4())  # Generate a unique identifier for the escrow

        wallet_address = generate_eth_wallet_address()

        # Store escrow details in the database
        cursor.execute("INSERT INTO escrows (uid, sender_id, receiver_id, wallet_address, initiated_at, status, votes) VALUES (%s, %s, %s, %s, %s, 'pending', '')",
                       (escrow_uid, sender_id, receiver_id, wallet_address, datetime.now()))
        db.commit()

        # Notify the users with inline buttons
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Sent", callback_data=f"sent_{escrow_uid}"),
             InlineKeyboardButton("Cancel Escrow", callback_data=f"cancel_{escrow_uid}")]
        ])

        try:
            await client.send_message(sender_id, f"Escrow initiated. Send funds to this wallet address: {wallet_address}", reply_markup=keyboard)
            await client.send_message(receiver_id, f"Escrow initiated by {sender_id}. You are the receiver.")
        except Exception as e:
            logger.error(f"Error sending message to users: {e}")
            await message.reply_text("Error: Make sure both the sender and receiver have interacted with the bot.")

        await message.reply_text("Escrow initiated successfully.")
        logger.info(f"Escrow initiated between sender {sender_id} and receiver {receiver_id} with wallet address {wallet_address}.")
    except Exception as e:
        logger.error(f"Error initiating escrow: {e}")
        await message.reply_text(f"Error initiating escrow: {e}")

@app.on_callback_query(filters.regex(r"^(sent|cancel)_[0-9a-fA-F-]{36}$"))
async def handle_sent_cancel(client, callback_query: CallbackQuery):
    try:
        action, escrow_uid = callback_query.data.split("_")

        if action == "sent":
            cursor.execute("UPDATE escrows SET status = 'funds_sent' WHERE uid = %s AND status = 'pending'", (escrow_uid,))
            db.commit()

            # Notify both sender and receiver to confirm satisfaction
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes", callback_data=f"satisfy_yes_{escrow_uid}"),
                 InlineKeyboardButton("No", callback_data=f"satisfy_no_{escrow_uid}")]
            ])

            cursor.execute("SELECT sender_id, receiver_id FROM escrows WHERE uid = %s", (escrow_uid,))
            escrow = cursor.fetchone()
            if not escrow:
                await callback_query.answer("Escrow not found.")
                logger.info(f"Escrow not found for uid {escrow_uid}.")
                return

            sender_id, receiver_id = escrow
            await client.send_message(sender_id, "Is the Escrow contract satisfied?", reply_markup=keyboard)
            await client.send_message(receiver_id, "Is the Escrow contract satisfied?", reply_markup=keyboard)

            await callback_query.message.reply_text("Escrow funds sent. Waiting for confirmation from both parties.")
            logger.info(f"Escrow funds sent for uid {escrow_uid} and waiting for confirmation from both parties.")
        elif action == "cancel":
            cursor.execute("DELETE FROM escrows WHERE uid = %s AND status = 'pending'", (escrow_uid,))
            db.commit()

            cursor.execute("SELECT sender_id, receiver_id FROM escrows WHERE uid = %s", (escrow_uid,))
            escrow = cursor.fetchone()
            if not escrow:
                await callback_query.answer("Escrow not found.")
                logger.info(f"Escrow not found for uid {escrow_uid}.")
                return

            sender_id, receiver_id = escrow
            await client.send_message(sender_id, "Escrow has been canceled.")
            await client.send_message(receiver_id, "Escrow has been canceled.")
            
            await callback_query.message.reply_text("Escrow canceled successfully.")
            logger.info(f"Escrow canceled for uid {escrow_uid}.")
    except Exception as e:
        logger.error(f"Error handling sent/cancel action: {e}")
        await callback_query.message.reply_text(f"Error: {e}")

@app.on_callback_query(filters.regex(r"^satisfy_(yes|no)_[0-9a-fA-F-]{36}$"))
async def check_escrow_satisfaction(client, callback_query: CallbackQuery):
    try:
        action, escrow_uid = callback_query.data.split("_")[1:]

        cursor.execute("SELECT id, votes, sender_id, receiver_id FROM escrows WHERE uid = %s AND status = 'funds_sent'", (escrow_uid,))
        escrow = cursor.fetchone()

        if not escrow:
            await callback_query.answer("Escrow not found.")
            logger.info(f"Escrow not found for uid {escrow_uid}.")
            return

        escrow_id, votes, sender_id, receiver_id = escrow
        user_id = callback_query.from_user.id

        if str(user_id) in votes.split(","):
            await callback_query.answer("You have already voted.")
            logger.info(f"User {user_id} has already voted for escrow {escrow_id}.")
            return

        new_votes = f"{votes},{user_id}_{action}"

        cursor.execute("UPDATE escrows SET votes = %s, status = 'awaiting_confirmation' WHERE id = %s", (new_votes, escrow_id))
        db.commit()

        await callback_query.answer("Vote registered. Waiting for the other party.")
        other_user_id = receiver_id if user_id == sender_id else sender_id
        await client.send_message(other_user_id, f"A vote has been cast by the other party. Waiting for your response.")
        logger.info(f"User {user_id} vote registered for escrow {escrow_id}: {action}")

        # Check if both votes are yes
        votes_list = new_votes.split(",")
        yes_votes = sum(1 for vote in votes_list if vote.endswith("_yes"))
        if yes_votes >= 2:
            cursor.execute("UPDATE escrows SET status = 'satisfied' WHERE id = %s", (escrow_id,))
            db.commit()
            await client.send_message(sender_id, "Escrow contract satisfied. Funds released.")
            await client.send_message(receiver_id, "Escrow contract satisfied. Funds released.")
            logger.info(f"Escrow {escrow_id} satisfied. Funds released.")
        elif len(votes_list) >= 2:
            cursor.execute("UPDATE escrows SET status = 'cooldown', cooldown_until = %s WHERE id = %s", (datetime.now() + timedelta(seconds=30), escrow_id))
            db.commit()
            await client.send_message(sender_id, "Escrow contract not satisfied. 30-second cool down period initiated.")
            await client.send_message
            await client.send_message(receiver_id, "Escrow contract not satisfied. 30-second cool down period initiated.")
            logger.info(f"Escrow {escrow_id} not satisfied. Cool down period initiated.")
            await asyncio.sleep(30)
            await retry_escrow_satisfaction(client, escrow_uid)
    except Exception as e:
        logger.error(f"Error checking escrow satisfaction: {e}")
        await callback_query.answer("Error processing your request.")


import re

@app.on_message(filters.command("remindme") & filters.group & filters.reply)
async def set_reminder(client, message):
    try:
        # Extract time from the command
        args = message.text.split()
        if len(args) != 2:
            await message.reply_text("Usage: /remindme <time>")
            return

        time_str = args[1]
        match = re.match(r"(\d+)([smhd])", time_str)
        if not match:
            await message.reply_text("Invalid time format. Use <number><s/m/h/d> (e.g., 10m for 10 minutes).")
            return

        amount, unit = int(match.group(1)), match.group(2)
        if unit == "s":
            delay = amount
        elif unit == "m":
            delay = amount * 60
        elif unit == "h":
            delay = amount * 3600
        elif unit == "d":
            delay = amount * 86400

        user_id = message.from_user.id
        username = message.from_user.username or "user"
        
        if message.reply_to_message is None:
            await message.reply_text("Error: Please reply to a specific message to set a reminder.")
            return
        
        # Logging to debug the attributes of the reply message
        logger.info(f"Reply to message attributes: {dir(message.reply_to_message)}")
        
        message_id = message.reply_to_message.message_id
        chat_id = message.chat.id

        await message.reply_text(f"Reminder set for {amount}{unit} from now.")

        # Schedule the reminder
        asyncio.create_task(remind(client, user_id, username, message_id, chat_id, delay))

    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        await message.reply_text("An error occurred while setting the reminder.")





async def retry_escrow_satisfaction(client, escrow_uid):
    try:
        cursor.execute("SELECT id, votes, sender_id, receiver_id FROM escrows WHERE uid = %s AND status = 'cooldown'", (escrow_uid,))
        escrow = cursor.fetchone()

        if not escrow:
            logger.info(f"No escrow found for retry with uid {escrow_uid}.")
            return

        escrow_id, votes, sender_id, receiver_id = escrow

        cursor.execute("UPDATE escrows SET status = 'awaiting_confirmation', votes = '' WHERE id = %s", (escrow_id,))
        db.commit()

        # Ask the satisfaction question again
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes", callback_data=f"satisfy_yes_{escrow_uid}"),
             InlineKeyboardButton("No", callback_data=f"satisfy_no_{escrow_uid}")]
        ])

        await client.send_message(sender_id, "Is the Escrow contract satisfied?", reply_markup=keyboard)
        await client.send_message(receiver_id, "Is the Escrow contract satisfied?", reply_markup=keyboard)

        logger.info(f"Satisfaction question asked again for escrow {escrow_id} with uid {escrow_uid}.")
    except Exception as e:
        logger.error(f"Error retrying escrow satisfaction: {e}")

# Function to scan files for malware using YARA
def scan_file(file_path):
    try:
        matches = yara_rules.match(file_path)
        if matches:
            return f"Malware detected: {matches}"
        else:
            return "No malware detected"
    except Exception as e:
        logger.error(f"Error scanning file: {e}")
        return f"Error scanning file: {e}"

# Function to check and delete messages containing banned words
def check_banned_words(client, message):
    cursor.execute("SELECT word FROM banned_words")
    banned_words = cursor.fetchall()
    text = message.text.lower()

    for word in banned_words:
        if word[0].lower() in text:
            client.delete_messages(message.chat.id, message.message_id)
            logger.info(f"Deleted message containing banned word '{word[0]}' from user {message.from_user.id}")
            return True
    return False

# Handler for new messages in groups
@app.on_message(filters.text & filters.group)
def group_message_handler(client, message):
    try:
        if message.text.startswith("/"):
            logger.info(f"Received command in group chat: {message.text}")
            command_handler(client, message)
            return

        if check_banned_words(client, message):
            return

        user_id = message.from_user.id
        username = message.from_user.username
        chat_id = message.chat.id
        chat_name = message.chat.title
        text = message.text

        logger.info(f"Received group message from user {user_id} in chat {chat_id}")

    except Exception as e:
        logger.error(f"Error handling group message: {e}")

# Handler for new messages in private chats
@app.on_message(filters.text & filters.private)
def private_message_handler(client, message):
    try:
        if message.text.startswith("/"):
            logger.info(f"Received command in private chat: {message.text}")
            command_handler(client, message)
            return

        user_id = message.from_user.id
        username = message.from_user.username
        chat_id = message.chat.id
        chat_name = message.chat.username
        text = message.text

        logger.info(f"Received private message from user {user_id}")

    except Exception as e:
        logger.error(f"Error handling private message: {e}")

# Handler for file uploads in groups
@app.on_message(filters.document & filters.group)
def group_document_handler(client, message):
    try:
        document = message.document
        file_path = client.download_media(document)

        logger.info(f"Received document from user {message.from_user.id} in chat {message.chat.id}: {document.file_name}")

        scan_result = scan_file(file_path)
        if "No malware detected" in scan_result:
            message.reply_text(f"File verified: {document.file_name}")
        else:
            message.reply_text(f"Malware detected in file: {document.file_name}")

        os.remove(file_path)  # Clean up the downloaded file
    except Exception as e:
        logger.error(f"Error handling group document: {e}")
        message.reply_text(f"Error: {e}")

# Handler for file uploads in private chats
@app.on_message(filters.document & filters.private)
def private_document_handler(client, message):
    try:
        document = message.document
        file_path = client.download_media(document)

        logger.info(f"Received document from user {message.from_user.id} in chat {message.chat.id}: {document.file_name}")

        scan_result = scan_file(file_path)
        if "No malware detected" in scan_result:
            message.reply_text(f"File verified: {document.file_name}")
        else:
            message.reply_text(f"Malware detected in file: {document.file_name}")

        os.remove(file_path)  # Clean up the downloaded file
    except Exception as e:
        logger.error(f"Error handling private document: {e}")
        message.reply_text(f"Error: {e}")


async def remind(client, user_id, username, message_id, chat_id, delay):
    try:
        await asyncio.sleep(delay)
        await client.send_message(
            chat_id,
            f"@{username}, here is your reminder!",
            reply_to_message_id=message_id
        )
        logger.info(f"Sent reminder to user {user_id} in chat {chat_id}.")
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")





# Command handler
def command_handler(client, message):
    try:
        command_text = message.text.split()
        command = command_text[0].lower()
        args = command_text[1:]

        if command == "/addsub":
            if len(args) != 2:
                message.reply_text("Usage: /addsub <user_id> <days>")
                return

            user_id = int(args[0])
            days = int(args[1])
            expiry_date = datetime.now() + timedelta(days=days)
            cursor.execute("REPLACE INTO subscriptions (user_id, expiry_date) VALUES (%s, %s)", (user_id, expiry_date))
            db.commit()
            logger.info(f"Added/Updated subscription for user {user_id} for {days} days.")
            message.reply_text(f"Subscription for user {user_id} has been updated for {days} days.")

        elif command == "/checksub":
            if len(args) != 1:
                message.reply_text("Usage: /checksub <user_id>")
                return

            user_id = int(args[0])
            cursor.execute("SELECT expiry_date FROM subscriptions WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result:
                expiry_date = result[0]
                message.reply_text(f"User {user_id} subscription expiry date: {expiry_date}")
            else:
                message.reply_text(f"User {user_id} does not have a subscription.")

        elif command == "/user":
            if len(args) != 1:
                message.reply_text("Usage: /user @username")
                return

            username = args[0].lstrip('@')
            user = app.get_users(username)
            user_id = user.id

            message.reply_text(f"User ID of @{username} is {user_id}.")

        elif command == "/commands":
            commands_list = (
                "/addsub <user_id> <days> - Add or update a subscription for a user.\n"
                "/checksub <user_id> - Check a user's subscription status.\n"
                "/user @username - Get the user ID of a username.\n"
                "/commands - Show this message.\n"
                "/addbannedword <word> - Add a word to the banned list.\n"
                "/removebannedword <word> - Remove a word from the banned list.\n"
                "/listbannedwords - List all banned words."
            )
            message.reply_text(f"Available commands:\n{commands_list}")

        elif command == "/addbannedword":
            if len(args) != 1:
                message.reply_text("Usage: /addbannedword <word>")
                return

            word = args[0].lower()
            cursor.execute("INSERT INTO banned_words (word) VALUES (%s)", (word,))
            db.commit()
            logger.info(f"Added banned word: {word}")
            message.reply_text(f"Banned word added: {word}")

        elif command == "/removebannedword":
            if len(args) != 1:
                message.reply_text("Usage: /removebannedword <word>")
                return

            word = args[0].lower()
            cursor.execute("DELETE FROM banned_words WHERE word = %s", (word,))
            db.commit()
            logger.info(f"Removed banned word: {word}")
            message.reply_text(f"Banned word removed: {word}")

        elif command == "/listbannedwords":
            cursor.execute("SELECT word FROM banned_words")
            banned_words = cursor.fetchall()
            if banned_words:
                banned_list = "\n".join(word[0] for word in banned_words)
                message.reply_text(f"Banned words:\n{banned_list}")
            else:
                message.reply_text("No banned words found.")

        else:
            logger.warning(f"Unrecognized command: {message.text}")
            message.reply_text("Unrecognized command. Use /commands to see the list of available commands.")
    except Exception as e:
        logger.error(f"Error handling command: {e}")
        message.reply_text(f"Error: {e}")

if __name__ == "__main__":
    app.run()
