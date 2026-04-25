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

ALLOWED_ROLES = {
    "chief of police",
    "assistant chief",
    "deputy chief",
    "board of chiefs",
}

LOG_CHANNEL_NAME = os.environ.get("LOG_CHANNEL_NAME", "mod-logs")


async def send_mod_log(
    interaction: discord.Interaction,
    action: str,
    target: discord.abc.User,
    reason: str,
    color: int,
):
    guild = interaction.guild
    if guild is None:
        return

    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if channel is None:
        print(
            f"[mod-log] No #{LOG_CHANNEL_NAME} channel found in '{guild.name}'. "
            f"Skipping log for {action}."
        )
        return

    log_embed = discord.Embed(
        title=f"Member {action}",
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    log_embed.add_field(
        name="User", value=f"{target.mention} (`{target}` — {target.id})", inline=False
    )
    log_embed.add_field(
        name="Moderator",
        value=f"{interaction.user.mention} (`{interaction.user}`)",
        inline=False,
    )
    log_embed.add_field(name="Reason", value=reason or "No reason", inline=False)

    try:
        await channel.send(embed=log_embed)
    except discord.Forbidden:
        print(
            f"[mod-log] Missing permission to send messages in "
            f"#{channel.name} ({guild.name})."
        )
    except discord.HTTPException as e:
        print(f"[mod-log] Failed to send log: {e}")


def has_allowed_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        return any(role.name.lower() in ALLOWED_ROLES for role in member.roles)

    return app_commands.check(predicate)


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


async def _explain_forbidden(action: str, member: discord.Member) -> str:
    return (
        f"I couldn't {action} {member.mention}. This is usually one of:\n"
        f"• My bot role is **below** {member.mention}'s highest role "
        f"(move my role above theirs in Server Settings → Roles).\n"
        f"• I'm missing the required Discord permission for this action.\n"
        f"• You're trying to act on the server owner (not allowed)."
    )


@bot.tree.command(name="kick", description="Kick a user")
@has_allowed_role()
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    try:
        await member.kick(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            await _explain_forbidden("kick", member), ephemeral=True
        )
        return
    await interaction.response.send_message(f"Kicked {member.mention}")
    await send_mod_log(interaction, "kicked", member, reason, color=0xE67E22)


@bot.tree.command(name="ban", description="Ban a user")
@has_allowed_role()
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    try:
        await member.ban(reason=reason)
    except discord.Forbidden:
        await interaction.response.send_message(
            await _explain_forbidden("ban", member), ephemeral=True
        )
        return
    await interaction.response.send_message(f"Banned {member.mention}")
    await send_mod_log(interaction, "banned", member, reason, color=0xE74C3C)


@bot.tree.command(name="timeout", description="Timeout a user (seconds)")
@has_allowed_role()
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    seconds: int,
):
    until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
    try:
        await member.timeout(until)
    except discord.Forbidden:
        await interaction.response.send_message(
            await _explain_forbidden("timeout", member), ephemeral=True
        )
        return
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"Discord rejected the timeout: {e}", ephemeral=True
        )
        return
    await interaction.response.send_message(
        f"Timed out {member.mention} for {seconds}s"
    )
    await send_mod_log(
        interaction,
        f"timed out for {seconds}s",
        member,
        reason="No reason",
        color=0xF1C40F,
    )


@bot.tree.command(name="embed", description="Create an embed message")
@app_commands.describe(
    title="Embed title",
    description="Embed description",
    color="Hex color (example: ff0000 for red)",
)
@has_allowed_role()
async def embed(
    interaction: discord.Interaction,
    title: str,
    description: str,
    color: str = "2f3136",
):
    try:
        color_int = int(color, 16)
    except ValueError:
        color_int = 0x2F3136

    emb = discord.Embed(
        title=title,
        description=description,
        color=color_int,
    )
    emb.set_footer(text=f"Requested by {interaction.user}")

    await interaction.response.send_message(embed=emb)


@kick.error
@ban.error
@timeout.error
@embed.error
async def restricted_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
