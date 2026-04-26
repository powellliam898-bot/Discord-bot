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
    "APPLICATION_CHANNEL_NAME", "applications"
)
CALLSIGN_CHANNEL_NAME = os.environ.get(
    "CALLSIGN_CHANNEL_NAME", "callsign-requests"
)

APPLICATION_QUESTIONS = [
    "What is your full in-game name?",
    "What is your age?",
    "What is your Discord username?",
    "What is your timezone?",
    "How many hours per week can you be active?",
    "Do you have previous law enforcement roleplay experience? If yes, where?",
    "Why do you want to join the LAPD?",
    "Have you read and agree to the server rules? (yes/no)",
]

CALLSIGN_QUESTIONS = [
    "What is your in-game name?",
    "What is your current rank?",
    "What callsign would you like? (e.g. 1-Adam-12)",
    "Why do you want this specific callsign?",
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


async def run_dm_questionnaire(
    interaction: discord.Interaction,
    user: discord.Member,
    title: str,
    questions: list[str],
    review_channel_identifier: str,
    color: int,
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
        await dm.send(f"**Question {index}/{len(questions)}:** {question}")
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

        answers.append((question, content if content else "—"))

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
    for question, answer in answers:
        submission.add_field(
            name=question[:256],
            value=answer[:1024],
            inline=False,
        )
    submission.set_footer(text=f"User ID: {user.id}")

    try:
        await channel.send(embed=submission)
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
