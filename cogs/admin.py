import discord
from discord.ext import commands
from utils.admin_tools import clear_chat_command, delete_item_command, strike_price_record, clean_debug_entries
import json

DB_FILEPATH = 'item_prices.json'

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='clear', help='!clear [amount] - ลบข้อความในห้อง (admin only, default: ลบทั้งหมด)')
    @commands.has_permissions(manage_messages=True)
    async def clear_chat(self, ctx, amount: int = None):
        await clear_chat_command(ctx, amount)

    @commands.command(name='delete', help='!delete <item name> <server> - ลบข้อมูลทั้งหมดสำหรับไอเทม (Admin only)')
    @commands.has_permissions(administrator=True)
    async def delete_item(self, ctx, *, args: str = None):
        await delete_item_command(ctx, args)

    @commands.command(name='strike', help='!strike <item name> <server> <record number> - ลบข้อมูลด้วยหมายเลข record (admin only)')
    async def remove_specific_record(self, ctx, *, args: str = None):
        await strike_price_record(ctx, args)

    @commands.command(
        name='cleandb',
        aliases=['clean'],
        help='ลบข้อมูลใน db ที่มี __debug Owner only.'
    )
    @commands.is_owner()
    async def cleanup_db_command(self, ctx):
        """
        Runs the database cleaning utility and reports the result to the channel.
        """
        # Confirmation message
        await ctx.send(f"Starting database cleanup on `{DB_FILEPATH}`. Please wait...")

        try:
            # Call the utility function to perform the actual cleanup
            removed_count = clean_debug_entries(DB_FILEPATH)

            if removed_count > 0:
                await ctx.send(
                    f"Cleanup complete! Successfully removed **{removed_count}** debug entries from the database."
                )
            else:
                await ctx.send("ℹNo entries ending in `__debug` were found. The database was not modified.")

        except (FileNotFoundError, ValueError, IOError) as e:
            # Catch specific errors from the utility function
            print(f"Error during DB cleanup: {e}")
            await ctx.send(f"A critical file error occurred during cleanup: `{e.__class__.__name__}: {e}`")
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred during DB cleanup: {e}")
            await ctx.send(f"An unhandled error occurred during cleanup: `{e.__class__.__name__}: {e}`")


    @cleanup_db_command.error
    async def cleanup_db_error(self, ctx, error):
        """Error handler for the cleanup command."""
        if isinstance(error, commands.NotOwner):
            await ctx.send("**Permission Denied:** You must be the bot owner to run this command.")
        else:
            print(f"Unhandled error in cleanup_db_command: {error}")
            await ctx.send(f"An unexpected command error occurred.")


async def setup(bot):
    await bot.add_cog(Admin(bot))