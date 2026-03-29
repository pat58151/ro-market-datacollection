import discord
from discord.ext import commands
from datetime import datetime, timedelta
import traceback
from utils.data_tools import load_data, normalize_item_name

async def show_stats(ctx, *, args: str = None):
    """Show basic statistics for a specific item in a server."""
    if not args:
        await ctx.send("โปรดกรอกชื่อไอเทม: `!stats <item name> <server>` หรือ `!stats <item name> <server> <days>`")
        return

    parts = args.split()
    days = 30

    # Detect whether user supplied number of days at the end
    if parts and parts[-1].isdigit():
        days = int(parts[-1])
        if len(parts) < 3:
            await ctx.send("รูปแบบคำสั่งไม่ถูกต้อง: `!stats <item name> <server> <days>`")
            return
        server_name = parts[-2]
        item_name = ' '.join(parts[:-2])
    elif len(parts) >= 2:
        server_name = parts[-1]
        item_name = ' '.join(parts[:-1])
    else:
        await ctx.send("รูปแบบคำสั่งไม่ถูกต้อง: `!stats <item name> <server>`")
        return

    valid_servers = ["chaos", "thor", "baphomet", "debug"]
    if server_name.lower() not in valid_servers:
        await ctx.send(f"ชื่อเซิร์ฟเวอร์ไม่ถูกต้อง: `{server_name}`. โปรดเลือกจาก: {', '.join(valid_servers)}")
        return

    try:
        data = load_data()
        normalized_name = normalize_item_name(item_name, server_name)

        if normalized_name not in data:
            await ctx.send(f"ไม่พบข้อมูล **{item_name} ({server_name})**.")
            return

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_data = [
            d for d in data[normalized_name]
            if datetime.fromisoformat(d['timestamp']) >= cutoff_date
        ]

        if not recent_data:
            await ctx.send(f"ไม่มีข้อมูลภายใน {days} วันล่าสุดสำหรับ **{item_name} ({server_name})**")
            return

        averages = [d['average'] for d in recent_data]

        stats_msg = (
            f"**ค่าสถิติสำหรับ {item_name.title()} ({server_name.title()}) (ย้อนหลัง {days} วัน):**\n"
            f"จำนวนข้อมูล: {len(recent_data)}\n"
            f"ราคาเฉลี่ย: {sum(averages) / len(averages):,.2f}\n"
            f"ต่ำสุด: {min(averages):,.2f}\n"
            f"สูงสุด: {max(averages):,.2f}"
        )

        await ctx.send(stats_msg)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการคำนวณสถิติ: {str(e)}")
        traceback.print_exc()

async def list_recent_records(ctx, item_name: str, server_name: str):
    """List the 50 most recent records for a specific item."""
    server_name = server_name.lower()
    normalized_name = normalize_item_name(item_name, server_name)

    try:
        data = load_data()
        records = data.get(normalized_name)

        if not records:
            await ctx.send(f"ไม่พบบันทึกสำหรับ **{item_name.title()} ({server_name.title()})**.")
            return

        recent_records = records[-50:]
        total_records = len(records)
        start_index = max(1, total_records - 50 + 1)

        output_lines = [
            f"🗒 **Records {start_index}-{total_records}** (จากทั้งหมด {total_records}) สำหรับ **{item_name.title()} ({server_name.title()})**:",
            "`Index | ราคา | จำนวน | Timestamp`",
            "-" * 50
        ]

        for i, record in enumerate(recent_records, start=start_index):
            price_text = f"{record.get('average', 0):,.0f}"
            quantity_text = str(record.get('quantity', 1))
            try:
                dt_obj = datetime.fromisoformat(record.get('timestamp'))
                time_str = dt_obj.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = "Invalid Time"
            line = f"`{i:<2}`| `{price_text:>7}` | `{quantity_text:>3}` | `{time_str}`"
            output_lines.append(line)

        output = "\n".join(output_lines)

        if len(output) > 2000:
            chunks = [output[i:i + 1900] for i in range(0, len(output), 1900)]
            for idx, chunk in enumerate(chunks, start=1):
                if idx == 1:
                    await ctx.send(f"รายการยาว ({len(chunks)} ข้อความ):\n{chunk}")
                else:
                    await ctx.send(chunk)
        else:
            await ctx.send(output)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการแสดงรายการ: {e}")
        traceback.print_exc()

async def get_latest_record_index(ctx, item_name: str, server_name: str):
    """Show the 50 latest records for an item."""
    server_name = server_name.lower()
    normalized_name = normalize_item_name(item_name, server_name)

    try:
        data = load_data()
        records = data.get(normalized_name)

        if not records:
            await ctx.send(f"ไม่พบบันทึกสำหรับ **{item_name.title()} ({server_name.title()})**.")
            return

        total_records = len(records)
        latest_records = records[-50:]  # Get last 50 records
        msg_lines = [
            f"**{item_name.title()} ({server_name.title()}) - 50 บันทึกล่าสุด (รวม {total_records} รายการ)**"
        ]

        for i, record in enumerate(reversed(latest_records), start=1):
            index = total_records - (i - 1)
            price_text = f"{record.get('average', 0):,.0f}"
            user_id = record.get('user_id', 'Unknown')

            try:
                dt_obj = datetime.fromisoformat(record.get('timestamp'))
                time_str = dt_obj.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = "Invalid Time"

            msg_lines.append(
                f"**#{index}** | ราคา: {price_text} | `{time_str}`"
            )

        msg = "\n".join(msg_lines)
        if len(msg) > 2000:
            chunks = [msg[i:i + 1900] for i in range(0, len(msg), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(msg)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการดึง Index: {e}")
        traceback.print_exc()

async def list_server_items(ctx, server_name: str):
    """List the 100 most recently updated items recorded in a specific server."""
    try:
        recent_items = get_recent_items(server_name)

        if not recent_items:
            await ctx.send(f"ไม่พบข้อมูลไอเทมในเซิร์ฟเวอร์ **{server_name.title()}**.")
            return

        embed = create_items_text(server_name, recent_items)
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาด: {str(e)}")
        traceback.print_exc()


def get_recent_items(server_name: str):
    """Return up to 100 most recently updated items for the given server."""
    data = load_data()
    server_name = server_name.lower().strip()

    valid_servers = ["chaos", "thor", "baphomet", "debug"]
    if server_name not in valid_servers:
        raise ValueError(f"ชื่อเซิร์ฟเวอร์ไม่ถูกต้อง: `{server_name}`. โปรดเลือกจาก: {', '.join(valid_servers)}")

    items_with_time = []

    for full_key, records in data.items():
        if '__' not in full_key or not records:
            continue

        item_name_part, server_name_part = full_key.rsplit('__', 1)
        if server_name_part.lower() != server_name:
            continue

        latest = records[-1]
        timestamp = latest.get('timestamp') or latest.get('time') or "1970-01-01T00:00:00"
        latest_price = latest.get('average', 0)
        record_count = len(records)

        items_with_time.append({
            "item_name": item_name_part.replace('_', ' ').title(),
            "price": latest_price,
            "records": record_count,
            "timestamp": timestamp
        })

    items_with_time.sort(key=lambda x: x['timestamp'], reverse=True)
    return items_with_time[:100]


def create_items_text(server_name: str, items: list, chunk_size=1900):
    """
    Create plain text showing up to 50 most recently updated items,
    automatically split into chunks under Discord's character limit.

    Returns a list of strings, each can be sent as a separate message.
    """
    if not items:
        return [f"ไม่พบข้อมูลในเซิร์ฟเวอร์ `{server_name}`"]

    lines = []
    for item in items[:50]:
        lines.append(f"• {item['item_name']} ราคาล่าสุด: {item['price']:,.0f}z ({item['records']} records)")

    text = "\n".join(lines)

    chunks = []
    current = []

    for line in text.split("\n"):
        if len("\n".join(current + [line])) > chunk_size:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current))

    return chunks