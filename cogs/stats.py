import discord
from discord.ext import commands
from utils.stats_tools import show_stats, list_recent_records, get_latest_record_index, list_server_items, create_items_text, get_recent_items
from utils.data_tools import normalize_item_name, load_data
from utils.graph_tools import create_line_graph
import os
import traceback

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name='graph',
        help='!graph <item name> <server> [days=90] - สร้างกราฟราคาย้อนหลัง'
    )
    async def show_graph(self, ctx, *, args: str = None):
        if not args:
            await ctx.send("วิธีใช้: `!graph <item name> <server> [days=90]`")
            return

        loading_msg = await ctx.send("กำลังสร้างกราฟ...")

        try:
            parts = args.split()
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

            data = load_data()
            normalized_name = normalize_item_name(item_name, server_name)
            if normalized_name not in data or not data[normalized_name]:
                await ctx.send(f"ไม่พบข้อมูลสำหรับ **{item_name}** ในเซิร์ฟเวอร์ **{server_name}**")
                return

            chart_filename = create_line_graph(data[normalized_name], item_name, server_name, days=days)
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
        finally:
            await loading_msg.delete()

    @commands.command(
        name='stats',
        help='!stats <item name> <server> [days=30] - แสดงสถิติราคา'
    )
    async def stats_command(self, ctx, *, args: str = None):
        await show_stats(ctx, args=args)

    @commands.command(
        name='index',
        aliases=['idx', 'record_num'],
        help='!index <item name> <server> - แสดงบันทึกข้อมูลรายไอเทมย้อนหลังพร้อม Index'
    )
    async def index_command(self, ctx, *, args: str):
        parts = args.split()
        if len(parts) < 2:
            await ctx.send("วิธีใช้: `!index <item name> <server>`")
            return
        server_name = parts[-1].lower()
        item_name = ' '.join(parts[:-1])
        await get_latest_record_index(ctx, item_name, server_name)

    @commands.command(
        name='items',
        aliases=['item', 'serveritems'],
        help='!items <server> - แสดงรายการไอเทม 50 รายการล่าสุดในเซิร์ฟเวอร์'
    )
    async def items_command(self, ctx, *, server_name: str):
        """Command: Show 50 most recently updated items in a specific server."""
        try:
            # Get the latest items once
            items = get_recent_items(server_name)

            # Create Discord-safe text chunks
            chunks = create_items_text(server_name, items)
            header = f"# รายการไอเทมล่าสุด (เซิร์ฟเวอร์ {server_name.title()})"

            if not chunks:
                await ctx.send(f"{header}\nไม่พบข้อมูลในเซิร์ฟเวอร์ `{server_name}`")
                return

            # Send the first chunk with the header
            await ctx.send(f"{header}\n```{chunks[0]}```")

            # Send remaining chunks
            for chunk in chunks[1:]:
                await ctx.send(f"```{chunk}```")

        except Exception as e:
            await ctx.send(f"เกิดข้อผิดพลาด: {str(e)}")
            print(f"Error in !items command: {traceback.format_exc()}")

async def setup(bot):
    await bot.add_cog(Stats(bot))