# This script creates a Telegram self-bot that replies when you're away.
# The initial setup and remote control are handled via a separate BotFather bot.

import os
import sys
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import getpass # Using getpass to hide sensitive input

# File path for the configuration file
CONFIG_FILE = 'config.json'

# --- Custom Exception for Clean Exit ---
class SetupCompleteError(Exception):
    """Custom exception to signal that setup is complete and the script should exit."""
    pass

# --- Configuration & Setup Logic ---

def save_config(api_id: int, api_hash: str, offline_message: str):
    """Saves the API ID, API Hash, and offline message to a JSON file."""
    config = {
        'api_id': api_id,
        'api_hash': api_hash,
        'offline_message': offline_message
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print("Configuration saved successfully!")

def load_config():
    """Loads the configuration from the JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

# --- BotFather Bot for Initial Setup ---

async def setup_with_bot_father(bot_token, api_id, api_hash):
    """
    Guides the user through setting up the API credentials using a BotFather bot.
    """
    print("\nStarting the setup bot...")
    try:
        # Initialize the client with provided credentials
        setup_app = Client("setup_session", bot_token=bot_token, api_id=api_id, api_hash=api_hash)
    except Exception as e:
        print(f"Error: Could not initialize setup client. Please check your bot token, API ID, and API Hash. ({e})")
        sys.exit(1)

    setup_message = """
**Welcome to the Setup Wizard!**

I need your Telegram API credentials to run the auto-reply bot on your account.
1. Go to **[my.telegram.org](https://my.telegram.org)**.
2. Log in and click on "API Development Tools".
3. Create a new application to get your API ID and API Hash.

Once you have them, send me a message in the following format:
`API_ID API_HASH`
(e.g., `123456 0123456789abcdef0123456789abcdef`)
"""

    @setup_app.on_message(filters.command("start") & filters.private)
    async def start_handler(client, message: Message):
        await message.reply_text(setup_message, disable_web_page_preview=True)

    @setup_app.on_message(filters.private & ~filters.me)
    async def credential_handler(client, message: Message):
        try:
            if message.text.startswith('/'):
                # Ignore other commands
                return

            parts = message.text.split()
            if len(parts) != 2:
                await message.reply_text("Invalid format. Please send `API_ID API_HASH`.")
                return

            api_id_str, api_hash = parts
            api_id = int(api_id_str)

            # Validate credentials by trying to start a temporary client
            await message.reply_text("Credentials received. Validating...")
            test_client = Client("test_session", api_id=api_id, api_hash=api_hash)
            try:
                await test_client.start()
                await test_client.stop()
            except Exception as e:
                print(f"Test client failed with unknown error: {e}")
                await message.reply_text("Invalid API ID or API Hash. Please check them and try again.")
                return

            save_config(api_id, api_hash, "I am currently offline and will get back to you as soon as possible. Thank you!")
            await message.reply_text("Credentials saved successfully! The bot is now configured.")
            await message.reply_text("Please restart the main script to start your auto-reply bot.")
            
            # The script will now exit gracefully
            raise SetupCompleteError("Setup is complete. Exiting cleanly.")

        except ValueError:
            await message.reply_text("Invalid API ID. It must be a number.")
        except Exception as e:
            await message.reply_text(f"An error occurred: {e}")

    print("Please open your BotFather bot chat and send the /start command.")
    print("The setup bot is now waiting for your input...")

    async with setup_app:
        await setup_app.idle()

# --- Main Auto-Reply Bot Logic ---

async def main():
    """Main function to run the auto-reply bot."""
    config = load_config()

    if not config:
        print("Bot is not yet configured. Please provide initial credentials.")
        bot_token = input("Enter your BotFather bot token: ")
        
        # New interactive prompt for API credentials
        print("\nNow, provide your Telegram API credentials. You can also press Enter to skip and set them up via the bot later.")
        api_id_str = input("Enter your API ID from my.telegram.org (or press Enter): ")
        api_hash = getpass.getpass("Enter your API Hash from my.telegram.org (or press Enter): ")
        
        if api_id_str and api_hash:
            # Terminal-based setup
            try:
                api_id = int(api_id_str)
                # Create a temporary client to validate credentials
                test_client = Client("test_session", api_id=api_id, api_hash=api_hash)
                await test_client.start()
                await test_client.stop()
                save_config(api_id, api_hash, "I am currently offline and will get back to you as soon as possible. Thank you!")
                
                # Reload config after saving
                config = load_config()
                
                print("Credentials saved. Starting the main bot...")
                # The function will now proceed to start the main bot.
            except (ValueError, Exception) as e:
                print(f"Invalid API ID or Hash provided. Please check and try again. ({e})")
                sys.exit(1)
        else:
            # Bot-based setup
            try:
                await setup_with_bot_father(bot_token, api_id=0, api_hash='') # Dummy credentials
            except SetupCompleteError:
                print("Setup process finished. Please re-run the script to start the main bot.")
                return

    # Create and run the main auto-reply client
    try:
        app = Client(
            "auto_reply_session",
            api_id=config['api_id'],
            api_hash=config['api_hash']
        )

        @app.on_message(filters.command("editoff") & filters.me)
        async def edit_offline_message(client, message: Message):
            """Handles the /editoff command to update the offline message."""
            try:
                new_message = message.text.split(" ", 1)[1].strip()
                config['offline_message'] = new_message
                save_config(config['api_id'], config['api_hash'], new_message)
                await message.reply_text(f"Offline message updated successfully to: \n`{new_message}`")
            except IndexError:
                await message.reply_text("Please provide a new message after the /editoff command.\nExample: `/editoff I will reply later.`")
            except Exception as e:
                await message.reply_text(f"An error occurred: {e}")

        @app.on_message(filters.private & filters.incoming & ~filters.me)
        async def auto_reply(client, message: Message):
            """Automatically replies to incoming private messages."""
            try:
                current_message = config.get('offline_message', "I am currently offline.")
                await asyncio.sleep(3)  # Small delay for natural response
                await message.reply(current_message)
                print(f"Replied to {message.from_user.first_name} with: '{current_message}'")
            except Exception as e:
                print(f"An error occurred: {e}")

        print("Telegram Auto-reply bot is starting...")
        print("Press Ctrl+C to stop the bot.")
        async with app:
            await app.idle()

    except Exception as e:
        print(f"An error occurred while starting the main bot. Please check your configuration. ({e})")
        
if __name__ == "__main__":
    asyncio.run(main())
