import discord
from discord.ext import commands
from utils.reminder_tools import (
    add_reminder,
    remove_reminder,
    get_user_reminders,
    parse_reminder_args,
    parse_forget_args
)

# Maximum number of active reminders allowed per user
MAX_REMINDERS = 20


class Reminders(commands.Cog):
    """Cog for managing price alert reminders"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='remindme')
    async def remind_me(self, ctx, *, args: str):
        """Set a price alert reminder

        Usage: !remindme <lower|higher> <item> <server> <price>
        Example: !remindme lower Shadowdecon Thor 150000
        Example: !remindme higher Mithril Ore Odin 1000
        """
        try:
            # Parse returns 4 values now (added alert_type)
            item_name, server_name, target_price, alert_type = parse_reminder_args(args)

            if not item_name or not server_name or target_price is None or not alert_type:
                await ctx.send(
                    "การใช้งานไม่ถูกต้อง\n"
                    "ใช้: `!remindme <lower|higher> <item> <server> <price>`\n"
                    "ตัวอย่าง:\n"
                    "• `!remindme lower Shadowdecon Thor 150000`\n"
                    "• `!remindme higher Mithril Ore Odin 1000`"
                )
                return

            if target_price <= 0:
                await ctx.send("ราคาต้องมากกว่า 0")
                return

            # --- START: MAX REMINDER CHECK ---
            current_reminders = get_user_reminders(ctx.author.id)
            item_name_lower = item_name.lower()
            server_name_lower = server_name.lower()

            # Check if the user is updating an existing reminder (same item, server, AND alert_type)
            reminder_exists = any(
                r['item_name'].lower() == item_name_lower and
                r['server_name'].lower() == server_name_lower and
                r['alert_type'] == alert_type
                for r in current_reminders
            )

            # If it's a NEW reminder AND the limit is reached, block the action.
            if not reminder_exists and len(current_reminders) >= MAX_REMINDERS:
                await ctx.send(
                    f"**เกินขีดจำกัด:** คุณตั้งการแจ้งเตือนครบ {MAX_REMINDERS} รายการแล้ว "
                    f"กรุณายกเลิกการแจ้งเตือนบางรายการ (`!forgetme`) ก่อนจึงจะเพิ่มรายการใหม่ได้"
                )
                return
            # Pass alert_type to add_reminder
            is_new = add_reminder(ctx.author.id, item_name, server_name, target_price, alert_type)

            # Different messages based on alert type
            alert_text = "ต่ำกว่าหรือเท่ากับ" if alert_type == "lower" else "สูงกว่าหรือเท่ากับ"

            if is_new:
                await ctx.send(
                    f"ตั้งการแจ้งเตือนสำหรับ **{item_name.title()} ({server_name.title()})**\n"
                    f"จะแจ้งเตือนเมื่อราคา{alert_text} **{target_price:,.2f}**\n"
                    f"{ctx.author.mention} จะถูกแท็กเมื่อราคาถึงเป้าหมาย"
                )
            else:
                await ctx.send(
                    f"อัปเดตการแจ้งเตือนสำหรับ **{item_name.title()} ({server_name.title()})**\n"
                    f"ราคาเป้าหมายใหม่: {alert_text} **{target_price:,.2f}**"
                )
        except ValueError:
            await ctx.send("กรุณาระบุราคาเป็นตัวเลข")
        except Exception as e:
            print(f"Error in remind_me: {e}")
            await ctx.send("เกิดข้อผิดพลาดในการตั้งการแจ้งเตือน")

    @remind_me.error
    async def remind_me_error(self, ctx, error):
        """Error handler for remindme command"""
        if isinstance(error, commands.BadArgument):
            await ctx.send("เกิดข้อผิดพลาดในการประมวลผลคำสั่ง")

    @commands.command(name='forgetme', aliases=['cancelreminder'])
    async def forget_me(self, ctx, *, args: str):
        """Remove a price alert reminder

        Usage: !forgetme <item> <server> [lower|higher]
        Example: !forgetme Shadowdecon Thor
        Example: !forgetme Shadowdecon Thor lower
        """
        try:
            item_name, server_name, alert_type = parse_forget_args(args)

            if not item_name or not server_name:
                await ctx.send(
                    "การใช้งานไม่ถูกต้อง\n"
                    "ใช้: `!forgetme <item> <server> [lower|higher]`\n"
                    "ตัวอย่าง:\n"
                    "• `!forgetme Shadowdecon Thor` (ยกเลิกทั้ง lower และ higher)\n"
                    "• `!forgetme Shadowdecon Thor lower` (ยกเลิกเฉพาะ lower)"
                )
                return

            success = remove_reminder(ctx.author.id, item_name, server_name, alert_type)

            if success:
                if alert_type:
                    alert_text = "ต่ำกว่า" if alert_type == "lower" else "สูงกว่า"
                    await ctx.send(
                        f"ยกเลิกการแจ้งเตือน ({alert_text}) สำหรับ **{item_name.title()} ({server_name.title()})**"
                    )
                else:
                    await ctx.send(
                        f"ยกเลิกการแจ้งเตือนทั้งหมดสำหรับ **{item_name.title()} ({server_name.title()})**"
                    )
            else:
                if alert_type:
                    alert_text = "ต่ำกว่า" if alert_type == "lower" else "สูงกว่า"
                    await ctx.send(
                        f"ไม่พบการแจ้งเตือน ({alert_text}) สำหรับ **{item_name.title()} ({server_name.title()})**"
                    )
                else:
                    await ctx.send(
                        f"ไม่พบการแจ้งเตือนสำหรับ **{item_name.title()} ({server_name.title()})**"
                    )
        except Exception as e:
            print(f"Error in forget_me: {e}")
            await ctx.send("เกิดข้อผิดพลาดในการยกเลิกการแจ้งเตือน")

    @forget_me.error
    async def forget_me_error(self, ctx, error):
        """Error handler for forgetme command"""
        if isinstance(error, commands.BadArgument):
            await ctx.send("เกิดข้อผิดพลาดในการประมวลผลคำสั่ง")

    @commands.command(name='myreminders', aliases=['reminders', 'myreminder'])
    async def my_reminders(self, ctx):
        """List all your active price reminders

        Usage: !myreminders
        """
        try:
            reminders = get_user_reminders(ctx.author.id)

            if not reminders:
                await ctx.send("คุณยังไม่มีการแจ้งเตือนที่ตั้งไว้")
                return

            message = (
                f"**การแจ้งเตือนราคาของคุณ ({ctx.author.name})**\n"
            )

            # Build the list of reminders with alert type
            for i, reminder in enumerate(reminders, 1):
                item = reminder['item_name'].title()
                server = reminder['server_name'].title()
                price = f"{reminder['target_price']:,.2f}"
                alert_type = reminder.get('alert_type', 'lower')

                operator = "≤" if alert_type == "lower" else "≥"

                message += f"**{i}.** **{item}** **({server})** - เป้าหมาย: {operator} **{price}**\n"

            message += f"-# รวม {len(reminders)} การแจ้งเตือน"

            await ctx.send(message)

        except Exception as e:
            print(f"Error in my_reminders: {e}")
            await ctx.send("เกิดข้อผิดพลาดในการแสดงการแจ้งเตือน")


async def setup(bot):
    """Setup function to load the cog"""
    await bot.add_cog(Reminders(bot))