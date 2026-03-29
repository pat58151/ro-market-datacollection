import discord
from discord.ext import commands
from utils.data_tools import load_data, save_data, normalize_item_name
from utils.price_tools import (
    handle_price_submission,
    parse_price_args,
    check_rate_limit,
    undo_price_submission
)

class Prices(commands.Cog):
    """Cog for handling price submissions and updates"""

    def __init__(self, bot, ocr_reader):
        self.bot = bot
        self.ocr_reader = ocr_reader

    @commands.command(
        name='price',
        help='!price <item name> <server> [number] - บันทึกราคาสำหรับแต่ละเซิฟเวอร์'
    )
    async def record_price(self, ctx, *, args: str = None):
        """Handles price recording and reminder checking."""
        allowed_channels = ['market-price', 'dev-room']
        if ctx.channel.name not in allowed_channels:
            await ctx.send("คำสั่ง `!price` ใช้ได้เฉพาะใน #market-price เท่านั้น")
            return

        if not args:
            await ctx.send("โปรดกรอกชื่อไอเทมและเซิฟเวอร์: `!price <item name> <server> [number]`")
            return

        # Parse arguments
        item_name, server_name, manual_price = parse_price_args(args)
        if not item_name or not server_name:
            await ctx.send("วิธีใช้: `!price <ชื่อไอเทม> <เซิฟเวอร์> [ราคา]`")
            return

        server_name = server_name.lower()
        valid_servers = ["chaos", "thor", "baphomet", "debug"]
        if server_name not in valid_servers:
            await ctx.send(f"ชื่อเซิฟเวอร์ไม่ถูกต้อง: `{server_name}`")
            return

        # Check rate limit
        allowed, remaining, wait_time = check_rate_limit(ctx.author.id)
        if not allowed:
            await ctx.send(f"ถึงขีดจำกัดจำนวนโพสต์ กรุณารอ {wait_time:.0f} วินาที")
            return

        attachment = ctx.message.attachments[0] if ctx.message.attachments else None

        # Handle price submission - this now includes alert notifications
        await handle_price_submission(
            ctx.channel,
            ctx.author,
            ctx.message.id,
            item_name,
            server_name,
            manual_price,
            attachment,
            self.ocr_reader,
            self.bot
        )

    @commands.command(name='undo', help='!undo - ยกเลิกการบันทึกล่าสุดที่ผู้ใช้บันทึกเอง')
    async def undo_last_price(self, ctx):
        """Undo user's last price submission"""
        try:
            await undo_price_submission(ctx)
        except Exception as e:
            print(f"Error in undo_last_price: {e}")
            await ctx.send("เกิดข้อผิดพลาดในการยกเลิกบันทึกราคา")


async def setup(bot):
    """Setup function to load the cog"""
    # Get OCR reader from bot if available
    ocr_reader = getattr(bot, 'ocr_reader', None)
    await bot.add_cog(Prices(bot, ocr_reader=ocr_reader))