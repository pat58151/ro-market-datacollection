import traceback
from datetime import datetime, timezone
from utils.data_tools import load_data, save_data, normalize_item_name
from pathlib import Path
from typing import Dict, Any
import json

async def clear_chat_command(ctx, amount: int = None):
    """Deletes messages in the channel."""
    if amount is None:
        limit = 500
    else:
        limit = amount + 1
    try:
        deleted = await ctx.channel.purge(limit=limit)
        await ctx.send(f"ลบข้อความไปแล้ว {len(deleted) - 1} รายการ", delete_after=10)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการล้างข้อความ: {str(e)}")


async def delete_item_command(ctx, args: str = None):
    """Deletes ALL records for a specific item and server."""
    if not args or len(args.split()) < 2:
        await ctx.send("วิธีใช้: `!delete <item name> <server>` (example: !delete shadowdecon thor)")
        return

    parts = args.split()
    server_name = parts[-1]
    item_name = ' '.join(parts[:-1])

    try:
        data = load_data()
        normalized_name = normalize_item_name(item_name, server_name)

        if normalized_name not in data:
            await ctx.send(f"ไม่พบบันทึกสำหรับ **{item_name.title()} ({server_name.title()})**.")
            return

        # 1. Move to debug/archive (Optional, but good practice)
        debug_key = '__'.join(normalized_name.split('__')[:-1] + ['debug'])
        if debug_key not in data:
            data[debug_key] = []

        data[debug_key].extend(data[normalized_name])

        # 2. Delete the primary record key
        deleted_count = len(data[normalized_name])
        del data[normalized_name]

        save_data(data)

        await ctx.send(
            f"ลบข้อมูลทั้งหมด {deleted_count} รายการ สำหรับ **{item_name.title()} ({server_name.title()})** เรียบร้อยแล้ว"
        )
    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการลบรายการ: {str(e)}")
        traceback.print_exc()


async def strike_price_record(ctx, args: str = None):
    """Deletes a specific record using its 1-based index."""
    if not args or len(args.split()) < 3:
        await ctx.send("วิธีใช้: `!strike <item name> <server> <record number>` (example: !strike shadowdecon thor 5)")
        return

    parts = args.split()

    try:
        # The last part is the record number
        record_num = int(parts[-1])
    except ValueError:
        await ctx.send("Record number ต้องเป็นตัวเลข")
        return

    server_name = parts[-2]
    item_name = ' '.join(parts[:-2])

    try:
        data = load_data()
        normalized_name = normalize_item_name(item_name, server_name)

        if normalized_name not in data or not data[normalized_name]:
            await ctx.send(f"ไม่พบบันทึกสำหรับ **{item_name.title()} ({server_name.title()})**.")
            return

        total_records = len(data[normalized_name])
        if record_num < 1 or record_num > total_records:
            await ctx.send(f"Record number ต้องอยู่ระหว่าง 1 ถึง {total_records}")
            return

        # Convert 1-based user input to 0-based Python index
        index_to_remove = record_num - 1
        record_to_remove = data[normalized_name][index_to_remove]

        # Check permissions - if user doesn't have manage_messages permission
        if not ctx.author.guild_permissions.manage_messages:
            # Regular user can only delete their own records
            if str(record_to_remove.get('user_id')) != str(ctx.author.id):
                await ctx.send("คุณสามารถลบเฉพาะบันทึกของคุณเองเท่านั้น")
                return

        # --- Archiving the removed entry (Good practice) ---
        item_server_parts = normalized_name.split('__')
        debug_key = '__'.join(item_server_parts[:-1] + ['debug'])
        if debug_key not in data:
            data[debug_key] = []

        removed_entry = data[normalized_name].pop(index_to_remove)
        data[debug_key].append(removed_entry)

        # Clean up if the list is now empty
        if not data[normalized_name]:
            del data[normalized_name]

        save_data(data)

        timestamp = removed_entry.get("timestamp", "Unknown")
        avg_price = removed_entry.get("average", 0)
        recorded_by = removed_entry.get("recorded_by", "Unknown")

        try:
            dt = datetime.fromisoformat(timestamp)
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            timestamp_str = timestamp

        await ctx.send(
            f"ลบข้อมูล **{item_name.title()} ({server_name.title()})** สำเร็จ\n"
            f"Record **#{record_num}** (บันทึกโดย: {recorded_by})\n"
            f"Timestamp: `{timestamp_str}`\n"
            f"ราคาเฉลี่ย: {avg_price:,.2f}\n"
            f"Records ที่เหลือ: **{len(data.get(normalized_name, []))}**"
        )
    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการ strike: {str(e)}")
        traceback.print_exc()

def clean_debug_entries(db_filepath: str) -> int:
    """
    Loads the JSON database, removes all keys that end with the '__debug' suffix,
    and saves the cleaned data back.

    Args:
        db_filepath: The path to the JSON database file.

    Returns:
        The number of entries (keys) that were successfully removed.
    """
    db_path = Path(db_filepath)

    if not db_path.exists():
        # Raise an error that the cog can catch and report to Discord
        raise FileNotFoundError(f"Database file not found at {db_filepath}")

    try:
        with db_path.open('r', encoding='utf-8') as f:
            data: Dict[str, Any] = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from {db_filepath}: {e}") from e

    keys_to_remove = [key for key in data if key.endswith('__debug')]
    removed_count = 0

    for key in keys_to_remove:
        del data[key]
        removed_count += 1

    if removed_count > 0:
        try:
            with db_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise IOError(f"Failed to write cleaned JSON to file: {e}") from e

    return removed_count