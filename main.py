import discord
from discord.ext import commands
import json
import matplotlib.pyplot as plt
import easyocr
import traceback
import asyncio
from datetime import datetime, timezone
import os
import shutil
import tempfile

os.environ['MIOPEN_DISABLE_CACHE'] = '1'
os.environ['MIOPEN_DEBUG_DISABLE_FIND_DB'] = '1'

try:
    plt.switch_backend('Agg')
except ImportError:
    print("Warning: Could not set 'Agg' backend. Chart generation might fail without a display server.")

# Initialize EasyOCR
print("Initializing EasyOCR...")
try:
    # Always try GPU first
    reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    print("EasyOCR initialized successfully with GPU")
except Exception as e:
    print(f"Failed to initialize EasyOCR with GPU, trying CPU: {e}")
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    print("EasyOCR initialized with CPU")

# Load configuration and Intents
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Attach OCR reader to bot object so it's accessible everywhere
bot.ocr_reader = reader

initial_extensions = [
    "cogs.stats",
    "cogs.admin",
    "cogs.redo",
    "cogs.reminder"
]

async def setup_hook():
    """Load extensions and perform one-time async setup tasks."""
    print("Executing setup_hook...")

    # Load all standard extensions asynchronously
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)  # <-- AWAIT load_extension
            print(f"{extension} loaded successfully.")
        except Exception as e:
            print(f"Failed to load extension {extension}: {e}")
            traceback.print_exc()

    # Load Prices cog and pass the reader
    try:
        from cogs.prices import Prices
        await bot.add_cog(Prices(bot, reader))  # <-- AWAIT add_cog and pass reader
        print("cogs.prices loaded successfully.")
    except Exception as e:
        print(f"Failed to load Prices cog with reader: {e}")
        traceback.print_exc()

bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    """Bot is ready and connected to Discord."""
    print(f'\n{bot.user} has connected to Discord.')
    print(f'Bot is active in {len(bot.guilds)} guild(s).')

    # Send startup notification
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name='bot-notification')
        if channel:
            role = discord.utils.get(guild.roles, name='Notification')
            mention = role.mention if role else ""
            await channel.send(f'{mention} {bot.user.name} is now online!')
        else:
            print(f'ไม่พบ #bot-notification ใน {guild.name}')

    await check_recent_price_submissions(reader)


from utils.data_tools import load_data
from utils.price_tools import handle_price_submission, parse_price_args, process_image_for_price


async def check_recent_price_submissions(ocr_reader):
    """Check recent 100 messages in #market-price channel for !price commands and record them if not in debug"""
    try:
        data = load_data()

        for key, entries in data.items():
            if isinstance(entries, list):
                data[key] = [e for e in entries if isinstance(e, dict)]

        debug_entries = set()
        for key, entries in data.items():
            if key.endswith('__debug'):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    item_name = '__'.join(key.split('__')[:-1])
                    debug_entries.add((
                        item_name,
                        entry.get('user_id'),
                        entry.get('timestamp')
                    ))

        processed_count = 0
        skipped_count = 0

        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name='market-price')
            if not channel or not channel.permissions_for(guild.me).read_message_history:
                if channel:
                    print(f"ไม่มีสิทธิ์อ่านประวัติข้อความใน #market-price ของ {guild.name}")
                else:
                    print(f"ไม่พบ #market-price ใน {guild.name}")
                continue

            try:
                async for message in channel.history(limit=100):
                    if message.author.bot:
                        continue

                    if any(reaction.me for reaction in message.reactions):
                        continue

                    if not message.content.startswith('!price'):
                        continue

                    args = message.content[6:].strip()
                    if not args:
                        continue

                    item_name, server_name, manual_price = parse_price_args(args)
                    if not item_name or not server_name:
                        continue

                    server_name = server_name.lower()
                    valid_servers = ["chaos", "thor", "baphomet", "debug"]
                    if server_name not in valid_servers:
                        continue

                    # --- Check if already recorded OR is a debug entry ---
                    already_recorded = False
                    for entries in data.values():
                        for entry in entries:
                            if not isinstance(entry, dict):
                                continue
                            if entry.get('message_id') == message.id:
                                already_recorded = True
                                break
                        if already_recorded:
                            break

                    if already_recorded:
                        skipped_count += 1
                        continue

                    # Check if similar entry exists in debug (using timestamp tolerance)
                    normalized_name = f"{item_name.lower().replace(' ', '_')}__{server_name}"
                    item_key = '__'.join(normalized_name.split('__')[:-1])

                    is_debug = False
                    msg_time_iso = message.created_at.replace(tzinfo=timezone.utc).isoformat()

                    for debug_item_key, debug_user_id, debug_timestamp in debug_entries:
                        if debug_item_key == item_key and debug_user_id == str(message.author.id):
                            try:
                                msg_time = message.created_at.replace(tzinfo=timezone.utc)
                                debug_time = datetime.fromisoformat(debug_timestamp).replace(tzinfo=timezone.utc)
                                time_diff = abs((msg_time - debug_time).total_seconds())

                                if time_diff <= 5:  # 5 seconds tolerance
                                    is_debug = True
                                    skipped_count += 1
                                    break
                            except:
                                pass  # Handle unparseable timestamps

                    if is_debug:
                        print(f"Skipped debug entry: {item_name} by {message.author.name}")
                        continue

                    # --- Process and Record ---
                    attachment = message.attachments[0] if message.attachments else None

                    await handle_price_submission(
                        message.channel,
                        message.author,
                        message.id,
                        item_name,
                        server_name,
                        manual_price,
                        attachment,
                        ocr_reader
                    )
                    processed_count += 1

            except discord.Forbidden:
                print(f"No permission to read history in #market-price")
                continue
            except Exception as e:
                print(f"Error checking #market-price: {str(e)}")
                traceback.print_exc()
                continue

        print(
            f"Auto-check complete: {processed_count} entries processed, {skipped_count} skipped (already Processed/Debug).")

    except Exception as e:
        print(f"Error in check_recent_price_submissions: {str(e)}")
        traceback.print_exc()

def clean_data_file(file_path: str):
    """
    Safely clean data.json by removing any non-dict entries.
    Keeps only valid entries and rewrites the file atomically.
    Creates a .bak backup before writing.
    Logs detailed results and prevents data loss even if interrupted.
    """
    if not os.path.exists(file_path):
        print(f"[clean_data_file] File not found: {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[clean_data_file] Error: File is not valid JSON — {e}")
        return
    except Exception as e:
        print(f"[clean_data_file] Error reading file: {e}")
        return

    changed = False
    total_entries = 0

    # Use a copy of data.items() to safely modify during iteration
    for key, entries in list(data.items()):
        if isinstance(entries, list):
            cleaned = [e for e in entries if isinstance(e, dict)]
            removed = len(entries) - len(cleaned)
            if removed > 0:
                print(f"[clean_data_file] Removed {removed} invalid entries from '{key}'")
                changed = True
            data[key] = cleaned
            total_entries += len(cleaned)
        else:
            print(f"[clean_data_file] Invalid format in '{key}' (expected list) — removing key")
            del data[key]
            changed = True

    if not changed:
        print("[clean_data_file] No invalid entries found — no changes made.")
        print(f"[clean_data_file] Total valid entries: {total_entries}")
        return

    backup_path = file_path + ".bak"
    try:
        # Create a backup before overwriting
        shutil.copy2(file_path, backup_path)
        print(f"[clean_data_file] Backup created at {backup_path}")

        # Write cleaned data to a temporary file first
        dir_name = os.path.dirname(file_path)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        os.close(fd)

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Replace original file atomically
        os.replace(temp_path, file_path)
        print(f"[clean_data_file] Cleaned data written safely to {file_path}")

    except Exception as e:
        print(f"[clean_data_file] Error during save: {e}")
        print("[clean_data_file] Original file and backup remain untouched.")
        return

    print(f"[clean_data_file] Cleaning complete. Total valid entries: {total_entries}")

# --- 5. Main Execution Block ---

async def main():
    """Main function to start the bot and run the setup_hook."""
    try:
        await bot.start(config["token"])
    except discord.LoginFailure:
        print("Fatal Error: Invalid token provided. Please check config.json.")
    except Exception as e:
        print(f"Fatal Error during bot execution: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    try:
        clean_data_file('item_prices.json')
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutting down via KeyboardInterrupt.")
    except Exception as e:
        print(f"An unexpected error occurred during startup/shutdown: {e}")