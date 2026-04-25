import os
import datetime

import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN environment variable is not set. "
        "Add it in the Replit Secrets tab."
    )

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


@bot.command(name="ping")
async def ping_prefix(ctx: commands.Context):
    await ctx.send("Pong!")


@bot.tree.command(name="ping", description="Check bot latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong! {round(bot.latency * 1000)}ms"
    )


@bot.tree.command(name="kick", description="Kick a user")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member.mention}")


@bot.tree.command(name="ban", description="Ban a user")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.mention}")


@bot.tree.command(name="timeout", description="Timeout a user (seconds)")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    seconds: int,
):
    until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
    await member.timeout(until)
    await interaction.response.send_message(
        f"Timed out {member.mention} for {seconds}s"
    )


@kick.error
@ban.error
@timeout.error
async def mod_error(interaction: discord.Interaction, error):
    await interaction.response.send_message(
        "You don't have permission to use this command.", ephemeral=True
    )


if __name__ == "__main__":
    bot.run(TOKEN)
