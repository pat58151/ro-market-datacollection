import discord
from datetime import datetime
from utils.data_tools import load_data, save_data, normalize_item_name
from utils.image_tools import process_image_for_price
import traceback
from datetime import datetime, timezone
import os

# Import reminder functions
from utils.reminder_tools import (
    get_all_reminders,
    remove_reminder
)

RATE_LIMIT = {}  # user_id: (last_timestamp, count)


def parse_price_args(args: str):
    """Parse '!price <item> <server> [manual price]' into components"""
    parts = args.split()
    if len(parts) < 2:
        return None, None, None

    manual_price = None
    try:
        price_str = parts[-1].replace(',', '')
        manual_price = float(price_str)
        parts = parts[:-1]
    except (ValueError, AttributeError):
        pass

    if len(parts) < 2:
        return None, None, None

    server_name = parts[-1]
    item_name = ' '.join(parts[:-1])

    return item_name.strip(), server_name.strip(), manual_price


def check_rate_limit(user_id: int, limit: int = 10, cooldown: int = 30):
    """Basic per-user rate limiting"""
    now = datetime.now(timezone.utc).timestamp()
    last_time, count = RATE_LIMIT.get(user_id, (0, 0))
    if now - last_time > cooldown:
        RATE_LIMIT[user_id] = (now, 1)
        return True, limit - 1, cooldown
    elif count < limit:
        RATE_LIMIT[user_id] = (last_time, count + 1)
        return True, limit - (count + 1), cooldown - (now - last_time)
    else:
        return False, 0, cooldown - (now - last_time)


# IMPORTANT: Define notify_price_alerts BEFORE handle_price_submission
async def notify_price_alerts(bot, channel, item_name, server_name, current_price):
    """Notify users whose reminder target is reached (supports higher/lower alerts)"""
    try:
        from utils.reminder_tools import load_reminders, save_reminders, should_trigger_alert

        reminders = load_reminders()
        key = f"{item_name.lower()}||{server_name.lower()}"

        if key not in reminders:
            return

        # Find all triggered reminders for this item
        triggered = []
        remaining = []

        for reminder in reminders[key]:
            alert_type = reminder.get('alert_type', 'lower')  # Default to 'lower' for backward compatibility
            target_price = reminder['target_price']

            # Check if alert should trigger based on alert_type
            if should_trigger_alert(current_price, target_price, alert_type):
                triggered.append(reminder)
            else:
                remaining.append(reminder)

        if not triggered:
            return

        # Send notifications to all triggered users
        for reminder in triggered:
            try:
                user = bot.get_user(int(reminder['user_id'])) if bot else None
                mention = user.mention if user else f"<@{reminder['user_id']}>"

                alert_type = reminder.get('alert_type', 'lower')
                target_price = reminder['target_price']

                # Different symbols and text based on alert type
                if alert_type == 'lower':
                    comparison = f"ต่ำกว่าหรือเท่ากับ **{target_price:,.2f}**"
                else:  # higher
                    comparison = f"สูงกว่าหรือเท่ากับ **{target_price:,.2f}**"

                await channel.send(
                    f"{mention} ราคาถึงเป้าหมายแล้ว!\n"
                    f"**{item_name.title()} ({server_name.title()})**\n"
                    f"ราคาปัจจุบัน: **{current_price:,.2f}**\n"
                    f"เป้าหมายของคุณ: {comparison}"
                )
            except Exception as e:
                print(f"Error notifying user {reminder['user_id']}: {e}")

        # Remove all triggered reminders in one operation
        if remaining:
            reminders[key] = remaining
        else:
            del reminders[key]

        save_reminders(reminders)
        print(f"✓ Notified {len(triggered)} user(s) for {item_name} ({server_name})")

    except Exception as e:
        print(f"Error in notify_price_alerts: {e}")
        traceback.print_exc()


async def handle_price_submission(channel, author, message_id, item_name, server_name,
                                  manual_price=None, attachment=None, ocr_reader=None, bot=None):
    """Process a !price submission and notify matching reminders"""
    try:
        data = load_data()
        normalized_name = normalize_item_name(item_name, server_name)

        price = manual_price
        cleaned = []

        if not price and attachment:
            # Add error handling for when process_image_for_price returns None
            result = await process_image_for_price(attachment, ocr_reader)

            if result is not None:
                price, cleaned = result
            else:
                # If OCR fails, send error and add reaction to mark as processed
                error_msg = await channel.send("ไม่สามารถอ่านราคาจากรูปภาพได้ กรุณาระบุราคาด้วยตนเอง")

                # Add reaction to original message to prevent reprocessing
                try:
                    original_msg = await channel.fetch_message(message_id)
                    await original_msg.add_reaction("❌")
                except discord.NotFound:
                    print(f"Message {message_id} not found for reaction")
                except discord.Forbidden:
                    print(f"No permission to add reaction to message {message_id}")
                except Exception as e:
                    print(f"Could not add reaction to message {message_id}: {type(e).__name__}: {e}")

                # Delete error message after 10 seconds
                try:
                    await error_msg.delete(delay=10)
                except Exception as e:
                    print(f"Could not delete error message: {e}")

                return

        if not price:
            # Send error and add reaction to mark as processed
            error_msg = await channel.send("ไม่สามารถระบุราคาได้ กรุณาแนบรูปภาพหรือระบุราคาด้วยตนเอง")

            # Add reaction to original message to prevent reprocessing
            try:
                original_msg = await channel.fetch_message(message_id)
                await original_msg.add_reaction("❌")
            except discord.NotFound:
                print(f"Message {message_id} not found for reaction")
            except discord.Forbidden:
                print(f"No permission to add reaction to message {message_id}")
            except Exception as e:
                print(f"Could not add reaction to message {message_id}: {type(e).__name__}: {e}")

            # Delete error message after 10 seconds
            try:
                await error_msg.delete(delay=10)
            except Exception as e:
                print(f"Could not delete error message: {e}")

            return

        entry = {
            'user_id': str(author.id),
            'recorded_by': author.display_name,
            'message_id': message_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'average': price
        }

        if normalized_name not in data:
            data[normalized_name] = []

        data[normalized_name].append(entry)
        save_data(data)

        total_records = len(data[normalized_name])
        cleaned_text = ", ".join(f"{num:,}" for num in cleaned) if cleaned else "N/A"

        success_msg = await channel.send(
            f"บันทึกราคา **{item_name.title()} ({server_name.title()})**\n"
            f"ราคาที่พบ: **{cleaned_text}**\n"
            f"ราคาเฉลี่ย: **{price:,.2f}**\n"
            f"Index: **{total_records}**"
        )

        # Add success reaction to original message (non-critical, don't fail if this errors)
        try:
            original_msg = await channel.fetch_message(message_id)
            await original_msg.add_reaction("✅")
        except discord.NotFound:
            print(f"Message {message_id} not found for reaction")
        except discord.Forbidden:
            print(f"No permission to add reaction to message {message_id}")
        except Exception as e:
            print(f"Could not add success reaction to message {message_id}: {type(e).__name__}: {e}")

        # Check and notify price alerts (wrap in try-except to prevent failures)
        try:
            await notify_price_alerts(bot, channel, item_name, server_name, price)
        except Exception as alert_error:
            print(f"Error in notify_price_alerts: {alert_error}")
            traceback.print_exc()

    except Exception as e:
        print(f"Error in handle_price_submission: {e}")
        traceback.print_exc()

        # Send error message and delete it
        try:
            error_msg = await channel.send("เกิดข้อผิดพลาดในการบันทึกราคา")

            # Add reaction to original message to prevent reprocessing
            try:
                original_msg = await channel.fetch_message(message_id)
                await original_msg.add_reaction("⚠️")
            except:
                pass

            await error_msg.delete(delay=10)
        except Exception as delete_error:
            print(f"Could not send/delete error message: {delete_error}")


async def undo_price_submission(ctx):
    """Undo the most recent !price entry by the user"""
    try:
        data = load_data()

        # Check if data is valid
        if not data or not isinstance(data, dict):
            await ctx.send("ไม่พบข้อมูลในระบบ")
            return

        author_string = str(ctx.author.id)
        most_recent_entry = None
        target_key = None
        target_index = -1

        for key, entries in data.items():
            if key.endswith('__debug'):
                continue

            # Skip if entries is not a list
            if not isinstance(entries, list):
                continue

            for i in range(len(entries) - 1, -1, -1):
                entry = entries[i]

                # Skip if entry doesn't have required fields
                if not isinstance(entry, dict) or 'user_id' not in entry or 'timestamp' not in entry:
                    continue

                if entry['user_id'] == author_string:
                    try:
                        entry_time = datetime.fromisoformat(entry['timestamp'])
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)

                        if not most_recent_entry:
                            most_recent_entry = entry
                            target_key = key
                            target_index = i
                        else:
                            recent_time = datetime.fromisoformat(most_recent_entry['timestamp'])
                            if recent_time.tzinfo is None:
                                recent_time = recent_time.replace(tzinfo=timezone.utc)

                            if entry_time > recent_time:
                                most_recent_entry = entry
                                target_key = key
                                target_index = i
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing timestamp for entry: {e}")
                        continue

        if not most_recent_entry:
            await ctx.send("ไม่พบบันทึกราคาที่คุณบันทึกเอง")
            return

        item_server_parts = target_key.split('__')
        if len(item_server_parts) < 2:
            await ctx.send("รูปแบบข้อมูลไม่ถูกต้อง")
            return

        item_name = ' '.join(item_server_parts[:-1]).title()
        server_name = item_server_parts[-1].title()

        debug_key = '__'.join(item_server_parts[:-1] + ['debug'])
        if debug_key not in data:
            data[debug_key] = []

        moved_entry = data[target_key].pop(target_index)
        data[debug_key].append(moved_entry)

        if not data[target_key]:
            del data[target_key]

        save_data(data)

        undo_time = datetime.fromisoformat(most_recent_entry['timestamp'])
        if undo_time.tzinfo is None:
            undo_time = undo_time.replace(tzinfo=timezone.utc)
        undo_time_str = undo_time.strftime('%Y-%m-%d %H:%M:%S')

        await ctx.send(
            f"**Undo สำเร็จ**\n"
            f"**{item_name} ({server_name})**\n"
            f"ราคาที่ลบ: {moved_entry.get('average', 0):,.2f}\n"
            f"Timestamp: `{undo_time_str}`"
        )

    except KeyError as e:
        await ctx.send(f"เกิดข้อผิดพลาด: ไม่พบคีย์ {str(e)}")
        traceback.print_exc()
    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการ undo: {type(e).__name__}: {str(e)}")
        traceback.print_exc()