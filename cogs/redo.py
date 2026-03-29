import discord
from discord.ext import commands
from utils.redo_tools import process_price_redo, process_graph_redo, process_remindme_redo


class Redo(commands.Cog):
    """Redo !price, !graph หรือ !remindme จากข้อความของผู้ใช้"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name='redo',
        help='Redo !price, !graph หรือ !remindme โดยตอบกลับข้อความต้นฉบับของผู้ใช้'
    )
    async def redo_command(self, ctx):
        """Redo a previous !price, !graph, or !remindme command"""

        if not ctx.message.reference or not ctx.message.reference.message_id:
            await ctx.send("โปรดใช้ `!redo` โดยตอบกลับข้อความ !price, !graph, หรือ !remindme ของผู้ใช้")
            return

        try:
            replied_msg = await ctx.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            await ctx.send("ไม่พบข้อความต้นฉบับ")
            return

        content = replied_msg.content.strip()
        lowered = content.lower().lstrip()

        if lowered.startswith('!price'):
            await process_price_redo(ctx, replied_msg, content)
        elif lowered.startswith('!graph'):
            await process_graph_redo(ctx, replied_msg, content)
        elif lowered.startswith('!remindme'):
            await process_remindme_redo(ctx, replied_msg, content)

        else:
            await ctx.send("ข้อความต้นฉบับไม่ใช่ !price, !graph, หรือ !remindme")


async def setup(bot):
    await bot.add_cog(Redo(bot))