import discord
import os
import traceback
from utils.data_tools import load_data, normalize_item_name
from utils.price_tools import handle_price_submission
from utils.graph_tools import create_line_graph
from utils.reminder_tools import parse_reminder_args, add_reminder, get_user_reminders


async def process_price_redo(ctx, replied_msg, content):
    """Redo a !price message"""
    # Import here to avoid circular imports if price_tools uses redo_tools
    from utils.price_tools import parse_price_args

    args_str = content[len('!price'):].strip()
    item_name, server_name, manual_price = parse_price_args(args_str)
    attachment = replied_msg.attachments[0] if replied_msg.attachments else None

    data = load_data()
    normalized_name = normalize_item_name(item_name, server_name)

    if normalized_name in data:
        already_processed = any(r.get("message_id") == replied_msg.id for r in data[normalized_name])
        if already_processed:
            await ctx.send(f"ข้อความนี้ถูกบันทึกไปแล้วสำหรับ {item_name.title()} ({server_name.title()})")
            return

    await ctx.send(f"กำลังประมวลผลข้อมูลซ้ำจาก {replied_msg.author.display_name} สำหรับ {item_name} ({server_name})")

    await handle_price_submission(
        ctx.channel,
        replied_msg.author,
        replied_msg.id,
        item_name,
        server_name,
        manual_price,
        attachment
    )


async def process_graph_redo(ctx, replied_msg, content):
    """Redo a !graph message"""
    args_str = content[len('!graph'):].strip()
    parts = args_str.split()
    if not parts:
        await ctx.send("รูปแบบไม่ถูกต้อง: `!graph <item name> <server> [days=90]`")
        return

    days = 90
    server_name = parts[-1].lower()

    if len(parts) >= 3 and parts[-1].isdigit():
        days = int(parts[-1])
        server_name = parts[-2].lower()
        item_name = ' '.join(parts[:-2])
    else:
        item_name = ' '.join(parts[:-1])

    valid_servers = ["chaos", "thor", "baphomet", "debug"]
    if server_name not in valid_servers:
        await ctx.send(f"Server ต้องเป็นหนึ่งใน: {', '.join(valid_servers)}")
        return
    if days < 1 or days > 365:
        await ctx.send("จำนวนวันต้องอยู่ระหว่าง 1 ถึง 365")
        return

    await ctx.send(f"กำลังสร้างกราฟใหม่สำหรับ {item_name.title()} ({server_name.title()})...")

    data = load_data()
    normalized_name = normalize_item_name(item_name, server_name)
    if normalized_name not in data or not data[normalized_name]:
        await ctx.send(f"ไม่พบข้อมูลสำหรับ **{item_name}** ในเซิร์ฟเวอร์ **{server_name}**")
        return

    try:
        chart_filename = create_line_graph(
            data[normalized_name],
            item_name,
            server_name,
            days=days
        )
        if chart_filename:
            await ctx.send(
                f"**กราฟราคา: {item_name.title()} ({server_name.title()})** ย้อนหลัง {days} วัน",
                file=discord.File(chart_filename)
            )
            os.remove(chart_filename)
        else:
            await ctx.send("ไม่สามารถสร้างกราฟได้ อาจไม่มีข้อมูลเพียงพอ")
    except Exception as e:
        await ctx.send(f"เกิดข้อผิดพลาดในการสร้างกราฟ: {e}")
        traceback.print_exc()


# --- NEW FUNCTION FOR !remindme REDO ---

async def process_remindme_redo(ctx, replied_msg, content):
    """Redo a !remindme message (sets the reminder for the user who ran !redo)"""
    from ..price_reminders import MAX_REMINDERS  # Import the constant from the cog file

    # 1. Strip the command prefix and get arguments
    args_str = content[len('!remindme'):].strip()
    item_name, server_name, target_price = parse_reminder_args(args_str)

    if not item_name or not server_name or target_price is None:
        await ctx.send("ไม่สามารถแยกวิเคราะห์คำสั่ง `!remindme` ต้นฉบับได้")
        return

    if target_price <= 0:
        await ctx.send("ราคาต้องมากกว่า 0")
        return

    # 2. Check Reminder Limit
    current_reminders = get_user_reminders(ctx.author.id)
    item_name_lower = item_name.lower()
    server_name_lower = server_name.lower()

    reminder_exists = any(
        r['item_name'].lower() == item_name_lower and
        r['server_name'].lower() == server_name_lower
        for r in current_reminders
    )

    if not reminder_exists and len(current_reminders) >= MAX_REMINDERS:
        await ctx.send(
            f"**เกินขีดจำกัด:** คุณตั้งการแจ้งเตือนครบ {MAX_REMINDERS} รายการแล้ว "
            f"กรุณายกเลิกรายการเก่าก่อนจึงจะเพิ่มรายการใหม่ได้"
        )
        return

    # 3. Add/Update Reminder
    is_new = add_reminder(ctx.author.id, item_name, server_name, target_price)

    # 4. Send confirmation message
    if is_new:
        await ctx.send(
            f"**ทำซ้ำ:** ตั้งการแจ้งเตือนใหม่สำหรับ **{item_name.title()} ({server_name.title()})**\n"
            f"จะแจ้งเตือนเมื่อราคาต่ำกว่าหรือเท่ากับ **{target_price:,.2f}**"
        )
    else:
        await ctx.send(
            f"**ทำซ้ำ:** อัปเดตการแจ้งเตือนสำหรับ **{item_name.title()} ({server_name.title()})**\n"
            f"ราคาเป้าหมายใหม่: **{target_price:,.2f}**"
        )