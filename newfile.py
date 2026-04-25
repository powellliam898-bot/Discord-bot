import discord
from discord.ext import commands

# Set up intents (required for newer Discord API versions)
intents = discord.Intents.default()
intents.message_content = True

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)

# Event: when bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Simple command
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Run the bot (replace with your token)
bot.run("MTQ5NzM0MzEzMTE3NDE3ODkwOA.G__nYO.T_HUzQZK7uYDuJ4fWtBrxjfM6e3jibdNXcZ21I")



# ========================
# SLASH COMMANDS
# ========================

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")

# ========================
# MODERATION COMMANDS
# ========================

# Kick
@bot.tree.command(name="kick", description="Kick a user")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member.mention}")

# Ban
@bot.tree.command(name="ban", description="Ban a user")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.mention}")

# Timeout (mute)
@bot.tree.command(name="timeout", description="Timeout a user (seconds)")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, seconds: int):
    import datetime
    until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
    await member.timeout(until)
    await interaction.response.send_message(f"Timed out {member.mention} for {seconds}s")

# Error handler (important)
@kick.error
@ban.error
@timeout.error
async def mod_error(interaction: discord.Interaction, error):
    await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

bot.run(TOKEN)