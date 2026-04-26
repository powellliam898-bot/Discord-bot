import os
import asyncio
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Keep-alive server to prevent bot from going idle
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # Suppress log messages
        pass

def run_keep_alive_server():
    server = HTTPServer(("0.0.0.0", 8000), KeepAliveHandler)
    server.serve_forever()

# Start the keep-alive server in a background thread
keep_alive_thread = threading.Thread(target=run_keep_alive_server, daemon=True)
keep_alive_thread.start()

WELCOME_CHANNEL_NAME = os.environ.get("WELCOME_CHANNEL_NAME", "welcome")
PROMOTION_CHANNEL_NAME = os.environ.get(
    "PROMOTION_CHANNEL_NAME", "1496934550553759920"
)
INFRACTION_CHANNEL_NAME = os.environ.get(
    "INFRACTION_CHANNEL_NAME", "1496934927130693883"
)
APPLICATION_CHANNEL_NAME = os.environ.get(
    "APPLICATION_CHANNEL_NAME", "1497863567276380220"
)
CALLSIGN_CHANNEL_NAME = os.environ.get(
    "CALLSIGN_CHANNEL_NAME", "1497269321293103244"
)

APPLICATION_QUESTIONS = [
    ("What is your full in-game name?", "In-game name"),
    ("What is your age?", "Age"),
    ("What is your Discord username?", "Discord username"),
    ("What is your time zone?", "Time zone"),
    ("How many hours per week can you be active?", "Weekly availability"),
    (
        "Do you have previous law enforcement roleplay experience? If yes, where?",
        "Prior LEO experience",
    ),
    ("Why do you want to join the LAPD?", "Why LAPD?"),
    ("Have you read and agree to the server rules? (yes/no)", "Agrees to rules"),
]

CALLSIGN_FORMAT_GUIDE = (
    "What callsign would you like?\n\n"
    "**Badge Number Format**\n"
    "`LA-0XX` Chief of Police  |  `LA-1XX` Assistant Chief\n"
    "`LA-2XX` Deputy Chief / Commander  |  `LA-3XX` Captain\n"
    "`LA-4XX` Lieutenant  |  `LA-5XX` Sergeant  |  `LA-6XX` Officer\n\n"
    "**In-game Callsign Format**\n"
    "Chief of Police: `X1-[UNIT]`\n"
    "Assistant Chief: `X2-[UNIT]`\n"
    "Deputy Chief: `X3-[UNIT]`\n"
    "Commander: `X4-[UNIT]`\n"
    "Captain: `X5-[UNIT]`\n"
    "Lieutenant II: `X6-[UNIT]`\n"
    "Lieutenant I: `X7-[UNIT]`\n"
    "Sergeant II: `X8-[UNIT]`\n"
    "Sergeant I: `X9-[UNIT]`\n"
    "Officer III+I: `X10-[UNIT]`\n"
    "Officer III: `X11-[UNIT]`\n"
    "Officer II: `X12-[UNIT]`\n"
    "Officer I: `X13-[UNIT]`\n\n"
    "**X codes**\n"
    "A (Adam) — 2-man Patrol  |  L (Lincoln) — 1-man Patrol\n"
    "D — Detective  |  M — Metropolitan  |  S — SWAT\n"
    "T — Traffic  |  E — Event / Training\n\n"
    "Unit number = last 3 digits of your badge number.\n"
    "Officers III+I and below must use a 2-digit unit number."
)

CALLSIGN_QUESTIONS = [
    ("What is your in-game name?", "In-game name"),
    ("What is your current rank?", "Current rank"),
    ("What is your badge number? (e.g. LA-512)", "Badge number"),
    (CALLSIGN_FORMAT_GUIDE, "Requested callsign"),
    ("Why do you want this specific callsign?", "Reason"),
]


def resolve_channel(guild: discord.Guild, identifier: str):
    """Look up a text channel by ID (if numeric) or by name."""
    if identifier.isdigit():
        channel = guild.get_channel(int(identifier))
        if isinstance(channel, discord.TextChannel):
            return channel
        return None
    return discord.utils.get(guild.text_channels, name=identifier)

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

    channel = resolve_channel(guild, LOG_CHANNEL_NAME)
    if channel is None:
        print(
            f"[mod-log] No channel matching '{LOG_CHANNEL_NAME}' found in "
            f"'{guild.name}'. Skipping log for {action}."
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
    if not getattr(bot, "_persistent_views_added", False):
        bot.add_view(CallsignReviewView())
        bot.add_view(ApplicationReviewView())
        bot._persistent_views_added = True
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    channel = resolve_channel(guild, WELCOME_CHANNEL_NAME)
    if channel is None:
        print(
            f"[welcome] No #{WELCOME_CHANNEL_NAME} channel found in "
            f"'{guild.name}'. Skipping welcome for {member}."
        )
        return

    embed = discord.Embed(
        title=f"Welcome to {guild.name}!",
        description=(
            f"Hey {member.mention}, glad to have you here! 🎉\n"
            f"You are member **#{guild.member_count}**."
        ),
        color=0x5865F2,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="Account created",
        value=discord.utils.format_dt(member.created_at, style="R"),
        inline=True,
    )
    embed.set_footer(text=f"User ID: {member.id}")

    try:
        await channel.send(content=member.mention, embed=embed)
    except discord.Forbidden:
        print(
            f"[welcome] Missing permission to send messages in "
            f"#{channel.name} ({guild.name})."
        )
    except discord.HTTPException as e:
        print(f"[welcome] Failed to send welcome: {e}")


@bot.command(name="ping")
async def ping_prefix(ctx: commands.Context):
    await ctx.send("Pong!")


@bot.tree.command(name="ping", description="Check bot latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong! {round(bot.latency * 1000)}ms"
    )


BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc)


def _format_uptime(delta: datetime.timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


@bot.tree.command(name="help", description="Show the list of available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Commands",
        description="Here's everything I can do:",
        color=0x5865F2,
    )

    embed.add_field(
        name="General",
        value=(
            "**/help** — Show this list of commands\n"
            "**/ping** — Check the bot's latency\n"
            "**/status** — Show bot uptime, latency, and server count\n"
            "**/embed** `title` `description` `[color]` — Post a custom embed message\n"
            "**/apply** — Start a department application (questions sent via DM)\n"
            "**/callsign** — Request a callsign (questions sent via DM)"
        ),
        inline=False,
    )

    embed.add_field(
        name="Moderation",
        value=(
            "**/kick** `member` `[reason]` — Kick a member\n"
            "**/ban** `member` `[reason]` — Ban a member\n"
            "**/timeout** `member` `seconds` — Timeout a member\n"
            "**/purge** `amount` — Bulk-delete recent messages (1-100)\n"
            "**/slowmode** `seconds` — Set channel slowmode (0 = off, max 21600)\n"
            "**/nickname** `member` `[nickname]` — Change a member's nickname\n"
            "**/promote** `member` — Promote a member by clicking a role button\n"
            "**/infract** `member` `reason` — Issue an infraction "
            "(Demotion / Written Warning / Warning / Notice)"
        ),
        inline=False,
    )

    embed.add_field(
        name="Restricted Roles",
        value=(
            "Moderation and `/embed` are limited to: "
            "Chief of Police, Assistant Chief, Deputy Chief, Board of Chiefs."
        ),
        inline=False,
    )

    embed.set_footer(text=f"Requested by {interaction.user}")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="Show bot uptime and latency")
async def status(interaction: discord.Interaction):
    now = datetime.datetime.now(datetime.timezone.utc)
    uptime = now - BOT_START_TIME
    latency_ms = round(bot.latency * 1000)

    embed = discord.Embed(
        title="Bot Status",
        color=0x2ECC71,
        timestamp=now,
    )
    embed.add_field(name="Status", value="🟢 Online", inline=True)
    embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)
    embed.add_field(name="Uptime", value=_format_uptime(uptime), inline=True)
    embed.add_field(
        name="Online since",
        value=discord.utils.format_dt(BOT_START_TIME, style="F"),
        inline=False,
    )
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.set_footer(text=f"Logged in as {bot.user}")

    await interaction.response.send_message(embed=embed)


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


@bot.tree.command(
    name="purge", description="Bulk-delete recent messages in this channel"
)
@app_commands.describe(amount="How many messages to delete (1-100)")
@has_allowed_role()
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message(
            "Amount must be between 1 and 100.", ephemeral=True
        )
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "This command only works in text channels.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(limit=amount)
    except discord.Forbidden:
        await interaction.followup.send(
            "I need the **Manage Messages** permission in this channel.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"Discord rejected the purge: {e}", ephemeral=True
        )
        return

    await interaction.followup.send(
        f"🧹 Deleted **{len(deleted)}** message(s) in {interaction.channel.mention}.",
        ephemeral=True,
    )

    if interaction.guild is not None:
        log_channel = resolve_channel(interaction.guild, LOG_CHANNEL_NAME)
        if log_channel is not None:
            log_embed = discord.Embed(
                title="Messages purged",
                color=0x95A5A6,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                description=(
                    f"**{interaction.user.mention}** deleted "
                    f"**{len(deleted)}** message(s) in "
                    f"{interaction.channel.mention}."
                ),
            )
            try:
                await log_channel.send(embed=log_embed)
            except discord.HTTPException:
                pass


@purge.error
async def purge_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, "
            "Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print(f"[purge.error] Could not respond to interaction: {error}")


@bot.tree.command(
    name="slowmode",
    description="Set slowmode on this channel (0 to disable, max 21600 = 6h)",
)
@app_commands.describe(
    seconds="Slowmode delay in seconds (0 to disable, max 21600)"
)
@has_allowed_role()
async def slowmode(interaction: discord.Interaction, seconds: int):
    if seconds < 0 or seconds > 21600:
        await interaction.response.send_message(
            "Seconds must be between 0 and 21600 (6 hours).", ephemeral=True
        )
        return

    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "This command only works in text channels.", ephemeral=True
        )
        return

    try:
        await interaction.channel.edit(
            slowmode_delay=seconds,
            reason=f"Slowmode set by {interaction.user}",
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I need the **Manage Channels** permission in this channel.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"Discord rejected the change: {e}", ephemeral=True
        )
        return

    if seconds == 0:
        msg = f"🐢 Slowmode disabled in {interaction.channel.mention}."
    else:
        msg = (
            f"🐢 Slowmode set to **{seconds}s** in "
            f"{interaction.channel.mention}."
        )
    await interaction.response.send_message(msg)

    if interaction.guild is not None:
        log_channel = resolve_channel(interaction.guild, LOG_CHANNEL_NAME)
        if log_channel is not None:
            log_embed = discord.Embed(
                title="Slowmode changed",
                color=0x95A5A6,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                description=(
                    f"**{interaction.user.mention}** set slowmode to "
                    f"**{seconds}s** in {interaction.channel.mention}."
                ),
            )
            try:
                await log_channel.send(embed=log_embed)
            except discord.HTTPException:
                pass


@slowmode.error
async def slowmode_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, "
            "Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print(f"[slowmode.error] Could not respond to interaction: {error}")


@bot.tree.command(
    name="nickname", description="Change a member's server nickname"
)
@app_commands.describe(
    member="The member whose nickname to change",
    nickname="New nickname (leave blank to reset to their username)",
)
@has_allowed_role()
async def nickname(
    interaction: discord.Interaction,
    member: discord.Member,
    nickname: str = "",
):
    new_nick = nickname.strip() or None
    old_nick = member.display_name

    if new_nick is not None and len(new_nick) > 32:
        await interaction.response.send_message(
            "Nicknames can be at most 32 characters.", ephemeral=True
        )
        return

    try:
        await member.edit(
            nick=new_nick,
            reason=f"Nickname changed by {interaction.user}",
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            f"I can't change {member.mention}'s nickname. My role must be "
            f"**above** theirs in Server Settings → Roles, and I need the "
            f"**Manage Nicknames** permission.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"Discord rejected the change: {e}", ephemeral=True
        )
        return

    if new_nick is None:
        msg = f"✏️ Reset {member.mention}'s nickname (was **{old_nick}**)."
    else:
        msg = (
            f"✏️ Changed {member.mention}'s nickname: "
            f"**{old_nick}** → **{new_nick}**."
        )
    await interaction.response.send_message(msg)

    await send_mod_log(
        interaction,
        "nickname changed",
        member,
        reason=(
            f"`{old_nick}` → `{new_nick or member.name}`"
        ),
        color=0x3498DB,
    )


@nickname.error
async def nickname_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, "
            "Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print(f"[nickname.error] Could not respond to interaction: {error}")


class PromoteRoleButton(discord.ui.Button):
    def __init__(
        self,
        role: discord.Role,
        target: discord.Member,
        invoker: discord.Member,
    ):
        label = role.name[:80]
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.role = role
        self.target = target
        self.invoker = invoker

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the person who ran /promote can use these buttons.",
                ephemeral=True,
            )
            return

        try:
            await self.target.add_roles(
                self.role, reason=f"Promoted by {self.invoker}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"I can't assign **{self.role.name}** — my role must be above "
                f"it in Server Settings → Roles, and I need **Manage Roles** "
                f"permission.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Discord rejected the role change: {e}", ephemeral=True
            )
            return

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"Promoted {self.target.mention} → **{self.role.name}** ✓",
            view=self.view,
        )
        await send_mod_log(
            interaction,
            "promoted",
            self.target,
            reason=f"Added role {self.role.mention}",
            color=0x2ECC71,
        )
        await send_promotion_announcement(
            interaction, self.target, self.role
        )


async def send_promotion_announcement(
    interaction: discord.Interaction,
    target: discord.Member,
    role: discord.Role,
):
    guild = interaction.guild
    if guild is None:
        return

    channel = resolve_channel(guild, PROMOTION_CHANNEL_NAME)
    if channel is None:
        print(
            f"[promotion] No #{PROMOTION_CHANNEL_NAME} channel found in "
            f"'{guild.name}'. Skipping announcement."
        )
        return

    embed = discord.Embed(
        title="🎖️ Promotion Announcement",
        description=(
            f"Congratulations {target.mention}!\n"
            f"You have been promoted to **{role.mention}**."
        ),
        color=0x2ECC71,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="New Rank", value=role.mention, inline=True)
    embed.add_field(
        name="Promoted by",
        value=interaction.user.mention,
        inline=True,
    )
    embed.set_footer(text=f"User ID: {target.id}")

    try:
        await channel.send(content=target.mention, embed=embed)
    except discord.Forbidden:
        print(
            f"[promotion] Missing permission to send messages in "
            f"#{channel.name} ({guild.name})."
        )
    except discord.HTTPException as e:
        print(f"[promotion] Failed to send announcement: {e}")


class PromoteView(discord.ui.View):
    def __init__(
        self,
        target: discord.Member,
        invoker: discord.Member,
        roles: list[discord.Role],
    ):
        super().__init__(timeout=120)
        for role in roles[:25]:
            self.add_item(PromoteRoleButton(role, target, invoker))


@bot.tree.command(name="promote", description="Promote a member by giving them a role")
@app_commands.describe(member="The member to promote")
@has_allowed_role()
async def promote(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await interaction.followup.send(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    invoker = interaction.user
    bot_top = guild.me.top_role
    invoker_top = invoker.top_role if isinstance(invoker, discord.Member) else None

    eligible = [
        r
        for r in guild.roles
        if not r.is_default()
        and not r.managed
        and r < bot_top
        and (invoker_top is None or r < invoker_top)
        and r not in member.roles
    ]
    eligible.sort(key=lambda r: r.position, reverse=True)

    if not eligible:
        await interaction.followup.send(
            f"No roles available to promote {member.mention} to. "
            f"(They may already have all roles below your rank, or my role "
            f"isn't high enough to assign any.)",
            ephemeral=True,
        )
        return

    view = PromoteView(member, invoker, eligible)
    extra = ""
    if len(eligible) > 25:
        extra = f"\n_Showing the top 25 of {len(eligible)} roles._"

    await interaction.followup.send(
        f"Choose a role to promote {member.mention} to:{extra}",
        view=view,
        ephemeral=True,
    )


@promote.error
async def promote_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print(f"[promote.error] Could not respond to interaction: {error}")


INFRACTION_TYPES = {
    "Demotion": {"color": 0xE74C3C, "emoji": "⬇️", "style": discord.ButtonStyle.danger},
    "Written Warning": {"color": 0xE67E22, "emoji": "📝", "style": discord.ButtonStyle.danger},
    "Warning": {"color": 0xF1C40F, "emoji": "⚠️", "style": discord.ButtonStyle.primary},
    "Notice": {"color": 0x3498DB, "emoji": "📌", "style": discord.ButtonStyle.secondary},
}

WARNING_ROLE_NAMES = ["Warning 1", "Warning 2", "Warning 3"]


class WarningRoleButton(discord.ui.Button):
    def __init__(
        self,
        role: discord.Role,
        target: discord.Member,
        invoker: discord.Member,
        reason: str,
    ):
        super().__init__(
            label=role.name[:80],
            style=discord.ButtonStyle.danger,
            emoji="⚠️",
        )
        self.role = role
        self.target = target
        self.invoker = invoker
        self.reason = reason

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the person who issued the warning can use these buttons.",
                ephemeral=True,
            )
            return

        try:
            await self.target.add_roles(
                self.role, reason=f"Warning issued by {self.invoker}: {self.reason}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"I can't assign **{self.role.name}** — my role must be above "
                f"it in Server Settings → Roles, and I need **Manage Roles** "
                f"permission.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Discord rejected the role change: {e}", ephemeral=True
            )
            return

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                f"Added **{self.role.name}** to {self.target.mention} ✓"
            ),
            view=self.view,
        )
        await send_mod_log(
            interaction,
            "warning role added",
            self.target,
            reason=f"Added {self.role.mention} ({self.reason})",
            color=0xF1C40F,
        )


class WarningRoleView(discord.ui.View):
    def __init__(
        self,
        roles: list[discord.Role],
        target: discord.Member,
        invoker: discord.Member,
        reason: str,
    ):
        super().__init__(timeout=120)
        for role in roles:
            self.add_item(WarningRoleButton(role, target, invoker, reason))


async def send_infraction_announcement(
    interaction: discord.Interaction,
    target: discord.Member,
    infraction_type: str,
    reason: str,
):
    guild = interaction.guild
    if guild is None:
        return

    channel = resolve_channel(guild, INFRACTION_CHANNEL_NAME)
    if channel is None:
        print(
            f"[infraction] No channel matching '{INFRACTION_CHANNEL_NAME}' "
            f"found in '{guild.name}'. Skipping announcement."
        )
        return

    cfg = INFRACTION_TYPES[infraction_type]
    embed = discord.Embed(
        title=f"{cfg['emoji']} Infraction — {infraction_type}",
        color=cfg["color"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Member", value=target.mention, inline=True)
    embed.add_field(name="Issued by", value=interaction.user.mention, inline=True)
    embed.add_field(name="Type", value=infraction_type, inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_footer(text=f"User ID: {target.id}")

    try:
        await channel.send(content=target.mention, embed=embed)
    except discord.Forbidden:
        print(
            f"[infraction] Missing permission to send messages in "
            f"#{channel.name} ({guild.name})."
        )
    except discord.HTTPException as e:
        print(f"[infraction] Failed to send announcement: {e}")

    dm_embed = discord.Embed(
        title=f"{cfg['emoji']} You received an infraction",
        description=(
            f"You have been issued an infraction in **{guild.name}**."
        ),
        color=cfg["color"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    dm_embed.add_field(name="Type", value=infraction_type, inline=True)
    dm_embed.add_field(name="Issued by", value=str(interaction.user), inline=True)
    dm_embed.add_field(
        name="Reason", value=reason or "No reason provided", inline=False
    )
    dm_embed.set_footer(text=f"Server: {guild.name}")

    try:
        await target.send(embed=dm_embed)
    except discord.Forbidden:
        print(
            f"[infraction] Could not DM {target} — they have DMs closed "
            f"or block the bot."
        )
    except discord.HTTPException as e:
        print(f"[infraction] Failed to DM {target}: {e}")


class InfractionTypeButton(discord.ui.Button):
    def __init__(
        self,
        infraction_type: str,
        target: discord.Member,
        invoker: discord.Member,
        reason: str,
    ):
        cfg = INFRACTION_TYPES[infraction_type]
        super().__init__(
            label=infraction_type,
            emoji=cfg["emoji"],
            style=cfg["style"],
        )
        self.infraction_type = infraction_type
        self.target = target
        self.invoker = invoker
        self.reason = reason

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message(
                "Only the person who ran /infract can use these buttons.",
                ephemeral=True,
            )
            return

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                f"Issued **{self.infraction_type}** to {self.target.mention} ✓"
            ),
            view=self.view,
        )
        await send_infraction_announcement(
            interaction, self.target, self.infraction_type, self.reason
        )
        await send_mod_log(
            interaction,
            f"received infraction ({self.infraction_type})",
            self.target,
            reason=self.reason,
            color=INFRACTION_TYPES[self.infraction_type]["color"],
        )

        if self.infraction_type == "Warning" and interaction.guild is not None:
            warning_roles = []
            missing = []
            for role_name in WARNING_ROLE_NAMES:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role is not None:
                    warning_roles.append(role)
                else:
                    missing.append(role_name)

            if not warning_roles:
                await interaction.followup.send(
                    "Couldn't find any of these warning roles in the server: "
                    + ", ".join(f"`{n}`" for n in WARNING_ROLE_NAMES)
                    + ". Create them (exact names) and try again.",
                    ephemeral=True,
                )
                return

            picker_embed = discord.Embed(
                title="⚠️ Add a warning role",
                description=(
                    f"Pick which warning role to add to {self.target.mention}."
                ),
                color=0xF1C40F,
            )
            picker_embed.add_field(name="Reason", value=self.reason, inline=False)
            if missing:
                picker_embed.add_field(
                    name="Missing roles (skipped)",
                    value=", ".join(f"`{n}`" for n in missing),
                    inline=False,
                )

            picker_view = WarningRoleView(
                warning_roles, self.target, self.invoker, self.reason
            )
            await interaction.followup.send(
                embed=picker_embed, view=picker_view, ephemeral=True
            )


class InfractionView(discord.ui.View):
    def __init__(
        self,
        target: discord.Member,
        invoker: discord.Member,
        reason: str,
    ):
        super().__init__(timeout=120)
        for infraction_type in INFRACTION_TYPES:
            self.add_item(
                InfractionTypeButton(infraction_type, target, invoker, reason)
            )


@bot.tree.command(
    name="infract", description="Issue an infraction to a member"
)
@app_commands.describe(
    member="The member to infract",
    reason="Why are they being infracted?",
)
@has_allowed_role()
async def infract(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str,
):
    await interaction.response.defer(ephemeral=True)

    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    view = InfractionView(member, interaction.user, reason)
    await interaction.followup.send(
        content=(
            f"Choose the infraction type for {member.mention}:\n"
            f"**Reason:** {reason}"
        ),
        view=view,
        ephemeral=True,
    )


@infract.error
async def infract_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CheckFailure):
        message = (
            "You don't have permission to use this command. "
            "It's restricted to: Chief of Police, Assistant Chief, Deputy Chief, Board of Chiefs."
        )
    else:
        message = f"Something went wrong: {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.NotFound:
        print(f"[infract.error] Could not respond to interaction: {error}")


def _is_staff_member(member: discord.abc.User) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return any(r.name.lower() in ALLOWED_ROLES for r in member.roles)


def _extract_user_id_from_footer(embed: discord.Embed):
    if embed.footer and embed.footer.text:
        text = embed.footer.text
        if text.startswith("User ID: "):
            try:
                return int(text.removeprefix("User ID: ").strip())
            except ValueError:
                return None
    return None


async def _finalize_review(
    interaction: discord.Interaction,
    view: discord.ui.View,
    submission_label: str,
    accepted: bool,
    summary_field_keywords: list[str] | None = None,
):
    if not _is_staff_member(interaction.user):
        await interaction.response.send_message(
            "Only staff (Chief of Police, Assistant Chief, Deputy Chief, "
            f"Board of Chiefs) can review {submission_label.lower()}s.",
            ephemeral=True,
        )
        return

    original = (
        interaction.message.embeds[0] if interaction.message.embeds else None
    )
    if original is None:
        await interaction.response.send_message(
            "Couldn't find the original submission embed.", ephemeral=True
        )
        return

    status_label = "Accepted" if accepted else "Cancelled"
    new_color = 0x2ECC71 if accepted else 0xE74C3C

    updated = discord.Embed(
        title=original.title,
        color=new_color,
        timestamp=original.timestamp,
    )
    if original.thumbnail and original.thumbnail.url:
        updated.set_thumbnail(url=original.thumbnail.url)
    for field in original.fields:
        updated.add_field(
            name=field.name, value=field.value, inline=field.inline
        )
    updated.add_field(
        name="Status",
        value=f"**{status_label}** by {interaction.user.mention}",
        inline=False,
    )
    if original.footer and original.footer.text:
        updated.set_footer(text=original.footer.text)

    for child in view.children:
        child.disabled = True

    await interaction.response.edit_message(embed=updated, view=view)

    requester_id = _extract_user_id_from_footer(original)
    if requester_id is None or interaction.guild is None:
        return

    requester = interaction.guild.get_member(requester_id)
    if requester is None:
        try:
            requester = await interaction.client.fetch_user(requester_id)
        except discord.HTTPException:
            requester = None
    if requester is None:
        return

    summary_value = "—"
    if summary_field_keywords:
        for field in original.fields:
            if all(k in field.name.lower() for k in summary_field_keywords):
                summary_value = field.value
                break

    dm_embed = discord.Embed(
        title=f"{submission_label} {status_label}",
        color=new_color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if summary_field_keywords:
        dm_embed.add_field(
            name="Your request", value=summary_value, inline=False
        )
    dm_embed.add_field(
        name="Reviewed by", value=str(interaction.user), inline=False
    )
    dm_embed.set_footer(text=f"Server: {interaction.guild.name}")
    try:
        await requester.send(embed=dm_embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


class CallsignReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="callsign_review:accept",
    )
    async def accept(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await _finalize_review(
            interaction,
            self,
            "Callsign Request",
            accepted=True,
            summary_field_keywords=["requested", "callsign"],
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="callsign_review:cancel",
    )
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await _finalize_review(
            interaction,
            self,
            "Callsign Request",
            accepted=False,
            summary_field_keywords=["requested", "callsign"],
        )


class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="application_review:accept",
    )
    async def accept(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await _finalize_review(
            interaction, self, "Department Application", accepted=True
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="application_review:cancel",
    )
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await _finalize_review(
            interaction, self, "Department Application", accepted=False
        )


async def run_dm_questionnaire(
    interaction: discord.Interaction,
    user: discord.Member,
    title: str,
    questions: list[str],
    review_channel_identifier: str,
    color: int,
    review_view: discord.ui.View | None = None,
    ping_role_name: str | None = None,
):
    try:
        dm = await user.create_dm()
        await dm.send(
            f"**{title}**\n"
            f"Please answer each question below.\n"
            f"Type `cancel` at any time to stop. You have 5 minutes per question."
        )
    except discord.Forbidden:
        try:
            await interaction.followup.send(
                "I couldn't DM you. Please open your DMs from server members "
                "(User Settings → Privacy & Safety) and run the command again.",
                ephemeral=True,
            )
        except discord.HTTPException:
            pass
        return
    except discord.HTTPException as e:
        print(f"[questionnaire] Failed to open DM with {user}: {e}")
        return

    answers: list[tuple[str, str]] = []
    for index, question in enumerate(questions, start=1):
        if isinstance(question, tuple):
            prompt_text, field_label = question
        else:
            prompt_text = question
            field_label = question

        await dm.send(f"**Question {index}/{len(questions)}:** {prompt_text}")
        try:
            msg = await bot.wait_for(
                "message",
                check=lambda m: m.author.id == user.id
                and isinstance(m.channel, discord.DMChannel),
                timeout=300,
            )
        except asyncio.TimeoutError:
            await dm.send(
                "⏰ Timed out waiting for an answer. Run the command again to retry."
            )
            return

        content = msg.content.strip()
        if content.lower() == "cancel":
            await dm.send("❌ Cancelled. Run the command again if you change your mind.")
            return

        answers.append((field_label, content if content else "—"))

    guild = interaction.guild
    if guild is None:
        await dm.send("Submission failed: not in a server context.")
        return

    channel = resolve_channel(guild, review_channel_identifier)
    if channel is None:
        await dm.send(
            f"Submission failed: review channel `{review_channel_identifier}` "
            f"not found. Please contact a moderator."
        )
        return

    submission = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    submission.set_thumbnail(url=user.display_avatar.url)
    submission.add_field(
        name="Submitted by",
        value=f"{user.mention} (`{user}` — {user.id})",
        inline=False,
    )
    for field_label, answer in answers:
        submission.add_field(
            name=field_label[:256],
            value=answer[:1024],
            inline=False,
        )
    submission.set_footer(text=f"User ID: {user.id}")

    ping_content = None
    if ping_role_name:
        ping_role = discord.utils.find(
            lambda r: r.name.lower() == ping_role_name.lower(), guild.roles
        )
        if ping_role is not None:
            ping_content = ping_role.mention

    try:
        kwargs = {"embed": submission}
        if review_view is not None:
            kwargs["view"] = review_view
        if ping_content:
            kwargs["content"] = ping_content
            kwargs["allowed_mentions"] = discord.AllowedMentions(roles=True)
        await channel.send(**kwargs)
        await dm.send(
            f"✅ Your **{title}** has been submitted! Staff will review it shortly."
        )
    except discord.Forbidden:
        await dm.send(
            "Submission failed: I don't have permission to post in the "
            "review channel. Please contact a moderator."
        )
    except discord.HTTPException as e:
        await dm.send(f"Submission failed: {e}")


@bot.tree.command(
    name="apply", description="Apply to join the department (questions sent via DM)"
)
async def apply(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(
            "This command only works in a server.", ephemeral=True
        )
        return

    await interaction.followup.send(
        "📬 Check your DMs! I've started your application.", ephemeral=True
    )
    await run_dm_questionnaire(
        interaction,
        interaction.user,
        "Department Application",
        APPLICATION_QUESTIONS,
        APPLICATION_CHANNEL_NAME,
        0x3498DB,
        review_view=ApplicationReviewView(),
        ping_role_name="Supervisor",
    )


@bot.tree.command(
    name="callsign", description="Request a callsign (questions sent via DM)"
)
async def callsign(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(
            "This command only works in a server.", ephemeral=True
        )
        return

    await interaction.followup.send(
        "📬 Check your DMs! I've started your callsign request.", ephemeral=True
    )
    await run_dm_questionnaire(
        interaction,
        interaction.user,
        "Callsign Request",
        CALLSIGN_QUESTIONS,
        CALLSIGN_CHANNEL_NAME,
        0x9B59B6,
        review_view=CallsignReviewView(),
        ping_role_name="Supervisor",
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
