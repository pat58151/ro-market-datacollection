import discord
from discord.ext import commands
from datetime import datetime
import traceback

from utils.data_tools import load_data, normalize_item_name

async def list_items(ctx, server_name: str):
    """List the 100 most recently updated tracked items for a given server."""
    try:
        data = load_data()

        if not data:
            await ctx.send("ปัจจุบันยังไม่มีไอเทม - ใช้ `!price <item name> <server>` เพื่อเริ่มบันทึกข้อมูล")
            return

        normalized_server = server_name.lower()
        valid_servers = ["chaos", "thor", "baphomet", "debug"]
        if normalized_server not in valid_servers:
            await ctx.send(f"ชื่อเซิฟเวอร์ไม่ถูกต้อง: `{server_name}`. โปรดเลือกจาก: {', '.join(valid_servers)}")
            return

        items_with_time = []
        for full_key, item_data in data.items():
            if '__' not in full_key or not item_data:
                continue

            item_name_part, server_name_part = full_key.rsplit('__', 1)
            server_name_part = server_name_part.lower()

            if server_name_part != normalized_server:
                continue

            latest = item_data[-1]
            timestamp = latest.get('timestamp') or latest.get('time') or 0
            latest_price = latest.get('average', 0)
            record_count = len(item_data)

            items_with_time.append({
                "item_name": item_name_part.replace('_', ' ').title(),
                "server": server_name_part.title(),
                "price": latest_price,
                "records": record_count,
                "timestamp": timestamp
            })

        if not items_with_time:
            await ctx.send(f"ไม่พบข้อมูลไอเทมในเซิฟเวอร์ **{server_name.title()}**.")
            return

        items_with_time.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_items = items_with_time[:50]

        # Create message
        header = f"**รายการไอเทมที่อัปเดตล่าสุด ({server_name.title()}):**\n"
        response = header + "\n".join(
            [f"**{item['item_name']}** - ราคาล่าสุด: {item['price']:,.2f} ({item['records']} records)" for item in recent_items]
        )

        if len(response) > 2000:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาด: {str(e)}")
        traceback.print_exc()

async def show_records(ctx, *, args: str = None):
    """Show the 50 most recent price records for an item"""
    if not args:
        await ctx.send("วิธีใช้: `!record <item name> <server>` (example: !record shadowdecon thor)")
        return

    parts = args.split()
    if len(parts) < 2:
        await ctx.send("วิธีใช้: `!record <item name> <server>` (example: !record shadowdecon thor)")
        return

    server_name = parts[-1]
    item_name = ' '.join(parts[:-1])

    try:
        data = load_data()
        normalized_name = normalize_item_name(item_name, server_name)

        if normalized_name not in data or not data[normalized_name]:
            await ctx.send(f"ไม่พบบันทึกสำหรับ **{item_name.title()} ({server_name.title()})**")
            return

        records = data[normalized_name]
        total_records = len(records)
        recent_records = records[-50:] if total_records > 50 else records
        start_index = total_records - len(recent_records) + 1

        response_lines = [f"**{item_name.title()} ({server_name.title()})**"]
        response_lines.append(f"แสดง {len(recent_records)} รายการล่าสุด (จากทั้งหมด {total_records} รายการ)\n")

        for i, record in enumerate(recent_records):
            index = start_index + i
            avg_price = record.get('average', 0)
            timestamp = record.get('timestamp', 'Unknown')
            recorded_by = record.get('recorded_by', 'Unknown')

            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                timestamp_str = timestamp

            response_lines.append(
                f"**Index: {index}** | Average Price: `{avg_price:,.2f}` | "
                f"By: {recorded_by} | {timestamp_str}"
            )

        full_response = '\n'.join(response_lines)

        if len(full_response) > 2000:
            current_message = response_lines[0] + '\n' + response_lines[1] + '\n'
            for line in response_lines[2:]:
                if len(current_message) + len(line) + 1 > 2000:
                    await ctx.send(current_message)
                    current_message = line + '\n'
                else:
                    current_message += line + '\n'
            if current_message:
                await ctx.send(current_message)
        else:
            await ctx.send(full_response)

    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาด: {str(e)}")
        traceback.print_exc()
