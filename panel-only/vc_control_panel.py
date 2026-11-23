"""Designed VC control panel — Python (discord.py) version.

Source of the design: the web UI at
``~/workspace/your_files/vc-control-panel/vc-control-panel.html``
(HEAVEN VOICE CONSOLE + Moderation / Channel / Voice / Heaven
Console — Original cards). This file implements that design in
Discord, with real discord.py calls — it is NOT the old repo panel
(``vc-control-src`` @ 01c9d6f2, ``bot/utils/vc_control_panel.py``),
although it reuses that panel's patterns verbatim where the design
matches it: ``VCControlPanelView``, ``RenameModal``, ``LimitModal``,
``MemberActionView``, ``MoveChannelView``, ``create_control_embed``,
``can_control_voice_channel`` and ``get_ownership``.

Unique actions in the designed UI (30):
  Moderation: VC Kick, VC Ban, VC Unban, Clear Chats, VC Access,
    VC Kick All, VC Ban All, VC Unban All
  Channel: Lock VC, Unlock VC, Hide VC, Show VC, Rename, Limit
  Voice: VMute 1, VUnmute 1, Mute All, Unmute All, Deafen 1,
    Undeafen 1, Deafen All, Undeafen All, VDrag, VDrag Stop, Drag All
  Original: Allow, Reject, Kick, Move, Pull, Mute, Kick All
  (Kick / Kick All / Mute All appear in both the console and the cards
  in the web UI; they are one action each here.)

Emoji pass (2026-11-23): every button carries a unicode emoji
matching the reference image as closely as Discord allows — the image
uses small monochrome SVG icons, not emoji, so these are the closest
standard-emoji equivalents (see README.md for the full list and the
unclear ones). Discord buttons are always grey; no colours, gradients
or cards can be added to them. The embed fields below mirror the
image sections with the same emojis.

Discord limit — one View is max 5 rows x 5 buttons = 25 buttons, so
30 actions cannot live in one View. Split (see README.md):
  * VCControlPanelView — the original 14 buttons (rows 0-2) + nav
    row 3: MODERATION, VOICE  (16 buttons)
  * ModerationView — the 8 Moderation actions + BACK, VOICE nav
    (10 buttons)
  * VoiceView — the 11 Voice actions + BACK, MODERATION nav
    (13 buttons)
  Channel actions live in the main view (they are the original panel's
  rows 0 and 2), so no separate Channel view is needed.
No feature was dropped; card buttons in the web UI are duplicates of
console chips and map to the same handlers here.

New vs the old repo panel:
  * VC Ban / Unban / Ban All / Unban All — per-member overwrite
    connect=False (+ kick if in VC), kept in an in-memory banned set
    in ownership.py; banned members are blocked from Pull / VDrag /
    Move / Drag All until unbanned.
  * Clear Chats — VCs have no text chat. It purges up to 100 messages
    in the text channel the panel was opened from (stored on the View),
    after an ephemeral Confirm/Cancel step. Requires Manage Messages.
  * Deafen 1 / Undeafen 1 / Deafen All / Undeafen All —
    member.edit(deafen=True/False); deafening also server-mutes, as in
    the web UI.
  * VMute 1 / VUnmute 1 — single-member mute=True / mute=False
    (the old Mute button toggles).
  * Unmute All — the old panel only had Mute All.
  * VDrag / Drag All / VDrag Stop — move a picked member / all
    members to a picked destination VC; drag state is kept in
    ownership.py and shown in the embed.

WHAT IT STILL NEEDS:
  - discord.py >= 2.3.0 (``pip install -r requirements.txt``)
  - a discord.py Bot; open with ``@Bot ?vc`` (prefix) or ``/vcpanel``
    (slash) — see open_panel.py. Both require the user to be in a
    voice channel and to pass ``can_control_voice_channel``.
  - ownership registry in ownership.py (populated by whoever creates
    temp VCs; without it the embed shows OWNER = "Server Controlled").
"""

from __future__ import annotations

import discord
from discord.ui import (
    Button,
    ChannelSelect,
    Modal,
    TextInput,
    UserSelect,
    View,
)

from permissions import can_control_voice_channel
from ownership import (
    ban_member,
    clear_banned,
    clear_drag,
    get_banned,
    get_chat_clears,
    get_drag,
    get_ownership,
    increment_chat_clears,
    is_banned,
    set_drag,
    unban_member,
)

MAX_NAME_LENGTH = 100


# =====================================================================
# Helpers
# =====================================================================


def _get_control_channel(
    interaction: discord.Interaction,
) -> discord.VoiceChannel | None:
    """Return the voice channel the interacting member is currently in."""
    if not isinstance(interaction.user, discord.Member):
        return None
    voice_state = interaction.user.voice
    if voice_state is None:
        return None
    channel = voice_state.channel
    if not isinstance(channel, discord.VoiceChannel):
        return None
    return channel


async def _require_control(
    interaction: discord.Interaction,
    required_permission: str = "manage_channels",
) -> discord.VoiceChannel | None:
    """Validate channel and user authorization (old panel, unchanged)."""
    channel = _get_control_channel(interaction)
    if channel is None:
        await interaction.response.send_message(
            "❌ You must be connected to a voice channel.",
            ephemeral=True,
        )
        return None
    if not isinstance(interaction.user, discord.Member):
        return None
    allowed, _ = can_control_voice_channel(
        interaction.user,
        channel,
        required_permission,
    )
    if not allowed:
        await interaction.response.send_message(
            "❌ You don't have permission to control this voice channel.",
            ephemeral=True,
        )
        return None
    me = channel.guild.me
    if me is None:
        await interaction.response.send_message(
            "❌ I am not available in this server.",
            ephemeral=True,
        )
        return None
    return channel


def _bot_can(channel: discord.VoiceChannel, permission: str) -> bool:
    """Check whether the bot has a channel permission (old panel)."""
    me = channel.guild.me
    if me is None:
        return False
    return bool(getattr(channel.permissions_for(me), permission, False))


async def _refresh_view(
    view: View,
    interaction: discord.Interaction,
) -> None:
    """Re-render the panel message with the given view's embed."""
    try:
        channel = _get_control_channel(interaction)
        if channel is None:
            return
        await interaction.message.edit(
            embed=create_control_embed(channel),
            view=view,
        )
    except Exception:
        pass


async def _switch_view(
    interaction: discord.Interaction,
    new_view: View,
) -> None:
    """Swap the panel message to another section View (nav buttons)."""
    channel = _get_control_channel(interaction)
    if channel is None:
        await interaction.response.send_message(
            "❌ You must be connected to a voice channel.",
            ephemeral=True,
        )
        return
    await interaction.response.edit_message(
        embed=create_control_embed(channel),
        view=new_view,
    )


# =====================================================================
# Rename modal (old panel, unchanged)
# =====================================================================


class RenameModal(Modal, title="Rename Voice Channel"):
    name = TextInput(
        label="New channel name",
        placeholder="Enter the new channel name",
        min_length=1,
        max_length=MAX_NAME_LENGTH,
        required=True,
    )

    def __init__(self, view: View) -> None:
        super().__init__()
        self.panel = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        new_name = str(self.name.value).strip()
        if not new_name:
            await interaction.response.send_message(
                "❌ Channel name cannot be empty.", ephemeral=True,
            )
            return
        if not _bot_can(channel, "manage_channels"):
            await interaction.response.send_message(
                "❌ I don't have **Manage Channels** permission.",
                ephemeral=True,
            )
            return
        if get_ownership(channel.id) is not None:
            new_name = f"︱{new_name}"
        try:
            old_name = channel.name
            await channel.edit(
                name=new_name,
                reason="Heaven VC Control Panel — rename",
            )
            await interaction.response.send_message(
                f"✏️ Renamed **{old_name}** → **{new_name}**.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to rename this channel.",
                ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Discord rejected the channel rename.",
                ephemeral=True,
            )


# =====================================================================
# Limit modal (old panel, unchanged)
# =====================================================================


class LimitModal(Modal, title="Voice Channel Limit"):
    limit = TextInput(
        label="Member limit",
        placeholder="0 = unlimited, maximum 99",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, view: View) -> None:
        super().__init__()
        self.panel = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        try:
            value = int(str(self.limit.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Enter a valid number between **0 and 99**.",
                ephemeral=True,
            )
            return
        if value < 0 or value > 99:
            await interaction.response.send_message(
                "❌ Limit must be between **0 and 99**.", ephemeral=True,
            )
            return
        if not _bot_can(channel, "manage_channels"):
            await interaction.response.send_message(
                "❌ I don't have **Manage Channels** permission.",
                ephemeral=True,
            )
            return
        try:
            await channel.edit(
                user_limit=value,
                reason="Heaven VC Control Panel — user limit",
            )
            display = "Unlimited" if value == 0 else str(value)
            await interaction.response.send_message(
                f"👥 Voice limit set to **{display}**.", ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to change the limit.",
                ephemeral=True,
            )


# =====================================================================
# Member selector — extended with the designed UI's single-member
# actions: vc_ban, vc_unban, vc_access, vmute1, vunmute1, deafen1,
# undeafen1, vdrag. Old actions (allow, reject, kick, pull, mute)
# keep the old panel's exact behaviour.
# =====================================================================


class MemberActionView(View):
    def __init__(self, panel: View, action: str) -> None:
        super().__init__(timeout=60)
        self.panel = panel
        self.action = action
        self.selector = UserSelect(
            placeholder="Select a member...",
            min_values=1,
            max_values=1,
        )
        self.selector.callback = self._selected
        self.add_item(self.selector)

    async def _selected(self, interaction: discord.Interaction) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        member = self.selector.values[0]
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Invalid member.", ephemeral=True,
            )
            return

        # Banned members cannot be pulled / dragged back in.
        if self.action in ("pull", "vdrag") and is_banned(channel.id, member.id):
            await interaction.response.send_message(
                f"❌ {member.mention} is banned from this VC — unban first.",
                ephemeral=True,
            )
            return

        if self.action == "allow":
            try:
                overwrite = channel.overwrites_for(member)
                overwrite.view_channel = True
                overwrite.connect = True
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — allow member",
                )
                await interaction.response.send_message(
                    f"👤 Allowed {member.mention} to access **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to change member access.",
                    ephemeral=True,
                )
            return

        if self.action == "vc_access":
            # Web UI: "Grant access to this VC (also unbans them)".
            try:
                unban_member(channel.id, member.id)
                overwrite = channel.overwrites_for(member)
                overwrite.view_channel = True
                overwrite.connect = True
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — VC access",
                )
                await interaction.response.send_message(
                    f"👤 Granted {member.mention} access to **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to change member access.",
                    ephemeral=True,
                )
            return

        if self.action == "reject":
            try:
                overwrite = channel.overwrites_for(member)
                overwrite.connect = False
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — reject member",
                )
                await interaction.response.send_message(
                    f"🚫 Rejected {member.mention} from **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to change member access.",
                    ephemeral=True,
                )
            return

        if self.action in ("kick", "vc_kick"):
            if not _bot_can(channel, "move_members"):
                await interaction.response.send_message(
                    "❌ I don't have **Move Members** permission.",
                    ephemeral=True,
                )
                return
            if member not in channel.members:
                await interaction.response.send_message(
                    "❌ That member is not in your voice channel.",
                    ephemeral=True,
                )
                return
            try:
                await member.move_to(
                    None, reason="Heaven VC Control Panel — kick",
                )
                await interaction.response.send_message(
                    f"🎙️ Kicked {member.mention} from **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I cannot move that member.", ephemeral=True,
                )
            return

        if self.action == "vc_ban":
            # VC ban (not a guild ban): deny Connect, kick if in VC,
            # remember in the in-memory banned set.
            if not _bot_can(channel, "manage_channels"):
                await interaction.response.send_message(
                    "❌ I don't have **Manage Channels** permission.",
                    ephemeral=True,
                )
                return
            try:
                ban_member(channel.id, member.id)
                overwrite = channel.overwrites_for(member)
                overwrite.connect = False
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — VC ban",
                )
                if member in channel.members and _bot_can(channel, "move_members"):
                    await member.move_to(
                        None, reason="Heaven VC Control Panel — VC ban",
                    )
                await interaction.response.send_message(
                    f"⛔ Banned {member.mention} from **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to ban that member.",
                    ephemeral=True,
                )
            return

        if self.action == "vc_unban":
            if not is_banned(channel.id, member.id):
                await interaction.response.send_message(
                    f"❌ {member.mention} is not banned from this VC.",
                    ephemeral=True,
                )
                return
            try:
                unban_member(channel.id, member.id)
                overwrite = channel.overwrites_for(member)
                overwrite.connect = None
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — VC unban",
                )
                await interaction.response.send_message(
                    f"✅ Unbanned {member.mention} — they can join "
                    f"**{channel.name}** again.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I don't have permission to unban that member.",
                    ephemeral=True,
                )
            return

        if self.action == "pull":
            if not _bot_can(channel, "move_members"):
                await interaction.response.send_message(
                    "❌ I don't have **Move Members** permission.",
                    ephemeral=True,
                )
                return
            if member.voice is None:
                await interaction.response.send_message(
                    "❌ That member is not connected to voice.",
                    ephemeral=True,
                )
                return
            try:
                await member.move_to(
                    channel, reason="Heaven VC Control Panel — pull",
                )
                await interaction.response.send_message(
                    f"⬇️ Pulled {member.mention} into **{channel.name}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I cannot move that member.", ephemeral=True,
                )
            return

        if self.action == "vdrag":
            # Web UI: drag a member into this VC and keep VDrag active.
            if not _bot_can(channel, "move_members"):
                await interaction.response.send_message(
                    "❌ I don't have **Move Members** permission.",
                    ephemeral=True,
                )
                return
            if member.voice is None:
                await interaction.response.send_message(
                    "❌ That member is not connected to voice.",
                    ephemeral=True,
                )
                return
            try:
                await member.move_to(
                    channel, reason="Heaven VC Control Panel — VDrag",
                )
                set_drag(channel.id, member.id, member.display_name)
                await interaction.response.send_message(
                    f"↔️ VDrag started — dragging {member.mention} into "
                    f"**{channel.name}**. Use VDrag Stop to stop.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I cannot move that member.", ephemeral=True,
                )
            return

        if self.action in ("mute", "vmute1", "vunmute1"):
            if not _bot_can(channel, "mute_members"):
                await interaction.response.send_message(
                    "❌ I don't have **Mute Members** permission.",
                    ephemeral=True,
                )
                return
            if member not in channel.members:
                await interaction.response.send_message(
                    "❌ That member is not in your voice channel.",
                    ephemeral=True,
                )
                return
            if self.action == "mute":
                new_mute_state = not bool(
                    member.voice and member.voice.mute
                )
            elif self.action == "vmute1":
                new_mute_state = True
            else:  # vunmute1
                new_mute_state = False
            try:
                await member.edit(
                    mute=new_mute_state,
                    reason="Heaven VC Control Panel — mute",
                )
                status = "muted" if new_mute_state else "unmuted"
                await interaction.response.send_message(
                    f"🔇 {member.mention} has been **{status}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I cannot mute/unmute that member.", ephemeral=True,
                )
            except discord.HTTPException:
                await interaction.response.send_message(
                    "❌ Discord rejected the mute operation.", ephemeral=True,
                )
            return

        if self.action in ("deafen1", "undeafen1"):
            # Web UI: deafening also mutes; undeafening also unmutes.
            if not _bot_can(channel, "mute_members"):
                await interaction.response.send_message(
                    "❌ I don't have **Mute Members** permission.",
                    ephemeral=True,
                )
                return
            if member not in channel.members:
                await interaction.response.send_message(
                    "❌ That member is not in your voice channel.",
                    ephemeral=True,
                )
                return
            new_state = self.action == "deafen1"
            try:
                await member.edit(
                    deafen=new_state, mute=new_state,
                    reason="Heaven VC Control Panel — deafen",
                )
                status = "deafened" if new_state else "undeafened"
                await interaction.response.send_message(
                    f"🎧 {member.mention} has been **{status}**.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ I cannot deafen/undeafen that member.",
                    ephemeral=True,
                )
            return


# =====================================================================
# Target channel selector — Move (all) and Drag All.
# mode="move": move everyone (old panel). mode="drag_all": same, but
# banned members are skipped and drag state is cleared, as in the web UI.
# =====================================================================


class MoveChannelView(View):
    def __init__(self, panel: View, mode: str = "move") -> None:
        super().__init__(timeout=60)
        self.panel = panel
        self.mode = mode
        self.selector = ChannelSelect(
            placeholder="Select destination voice channel...",
            channel_types=[discord.ChannelType.voice],
            min_values=1,
            max_values=1,
        )
        self.selector.callback = self._selected
        self.add_item(self.selector)

    async def _selected(self, interaction: discord.Interaction) -> None:
        source = await _require_control(interaction, "move_members")
        if source is None:
            return
        target = self.selector.values[0]
        if not isinstance(target, discord.VoiceChannel):
            await interaction.response.send_message(
                "❌ Invalid target channel.", ephemeral=True,
            )
            return
        if target.id == source.id:
            await interaction.response.send_message(
                "❌ The target is already your current channel.",
                ephemeral=True,
            )
            return
        me = source.guild.me
        if me is None or not me.guild_permissions.move_members:
            await interaction.response.send_message(
                "❌ I don't have **Move Members** permission.",
                ephemeral=True,
            )
            return
        moved = 0
        skipped = 0
        for member in list(source.members):
            if member.id == me.id:
                continue
            if is_banned(source.id, member.id):
                skipped += 1
                continue
            try:
                await member.move_to(
                    target,
                    reason=f"Heaven VC Control Panel — {self.mode}",
                )
                moved += 1
            except (discord.Forbidden, discord.HTTPException):
                skipped += 1
        if self.mode == "drag_all":
            clear_drag(source.id)
        verb = "Dragged" if self.mode == "drag_all" else "Moved"
        message = (
            f"🔀 {verb} **{moved}** member"
            f"{'' if moved == 1 else 's'} to {target.mention}."
        )
        if skipped:
            message += (
                f"\n⚠️ Skipped **{skipped}** member"
                f"{'' if skipped == 1 else 's'} (banned / could not move)."
            )
        await interaction.response.send_message(message, ephemeral=True)


# =====================================================================
# Clear Chats — confirm step. VCs have no text chat, so this purges
# the text channel the panel was opened from (stored on the View).
# =====================================================================


class ClearChatsConfirmView(View):
    def __init__(
        self,
        panel: View,
        text_channel: discord.TextChannel | None,
        vc_channel: discord.VoiceChannel,
    ) -> None:
        super().__init__(timeout=60)
        self.panel = panel
        self.text_channel = text_channel
        self.vc_channel = vc_channel

    @discord.ui.button(
        label="CLEAR", emoji="🧹",
        style=discord.ButtonStyle.danger,
        row=0,
    )
    async def confirm(
        self, interaction: discord.Interaction, button: Button,
    ) -> None:
        text_channel = self.text_channel
        if text_channel is None and isinstance(
            interaction.channel, discord.TextChannel
        ):
            text_channel = interaction.channel
        if text_channel is None:
            await interaction.response.send_message(
                "❌ Clear Chats needs a text channel — open the panel "
                "from a text channel with `?vc` / `/vcpanel`.",
                ephemeral=True,
            )
            return
        me = text_channel.guild.me
        if me is None or not text_channel.permissions_for(me).manage_messages:
            await interaction.response.send_message(
                "❌ I don't have **Manage Messages** in "
                f"{text_channel.mention}.",
                ephemeral=True,
            )
            return
        try:
            deleted = await text_channel.purge(
                limit=100,
                reason="Heaven VC Control Panel — clear chats",
            )
            increment_chat_clears(self.vc_channel.id)
            await interaction.response.send_message(
                f"🧹 Cleared **{len(deleted)}** messages in "
                f"{text_channel.mention}.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I cannot delete messages there.", ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Discord rejected the purge (messages older than "
                "14 days cannot be bulk-deleted).",
                ephemeral=True,
            )

    @discord.ui.button(
        label="CANCEL", emoji="❌",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def cancel(
        self, interaction: discord.Interaction, button: Button,
    ) -> None:
        await interaction.response.send_message(
            "Cancelled — nothing was deleted.", ephemeral=True,
        )


# =====================================================================
# Bulk helpers — shared by the main / moderation / voice views so the
# same action does the same thing whichever button triggers it.
# Each sends one ephemeral reply; callers must not have responded yet.
# =====================================================================


async def _bulk_voice_edit(
    interaction: discord.Interaction,
    channel: discord.VoiceChannel,
    *,
    mute: bool | None = None,
    deafen: bool | None = None,
    verb: str,
) -> None:
    """Server-mute/deafen every member in the VC (except the bot)."""
    me = channel.guild.me
    if me is None:
        await interaction.response.send_message(
            "❌ I am not available in this server.", ephemeral=True,
        )
        return
    changed = 0
    skipped = 0
    for member in list(channel.members):
        if member.id == me.id or member.voice is None:
            continue
        kwargs: dict = {}
        if mute is not None and member.voice.mute != mute:
            kwargs["mute"] = mute
        if deafen is not None and member.voice.deaf != deafen:
            kwargs["deafen"] = deafen
            if deafen:
                kwargs["mute"] = True
            elif mute is None:
                kwargs["mute"] = False
        if not kwargs:
            continue
        try:
            await member.edit(
                **kwargs, reason=f"Heaven VC Control Panel — {verb}",
            )
            changed += 1
        except (discord.Forbidden, discord.HTTPException):
            skipped += 1
    message = f"{verb.capitalize()} **{changed}** member{'s' if changed != 1 else ''}."
    if skipped:
        message += f"\n⚠️ Skipped **{skipped}**."
    await interaction.response.send_message(message, ephemeral=True)


async def _do_kick_all(
    interaction: discord.Interaction, channel: discord.VoiceChannel,
) -> None:
    me = channel.guild.me
    if me is None:
        await interaction.response.send_message(
            "❌ I am not available in this server.", ephemeral=True,
        )
        return
    kicked = skipped = 0
    for member in list(channel.members):
        if member.id == me.id:
            continue
        try:
            await member.move_to(
                None, reason="Heaven VC Control Panel — kick all",
            )
            kicked += 1
        except (discord.Forbidden, discord.HTTPException):
            skipped += 1
    message = f"👥 Kicked **{kicked}** member{'s' if kicked != 1 else ''}."
    if skipped:
        message += f"\n⚠️ Skipped **{skipped}**."
    await interaction.response.send_message(message, ephemeral=True)


async def _do_ban_all(
    interaction: discord.Interaction, channel: discord.VoiceChannel,
) -> None:
    if not _bot_can(channel, "manage_channels"):
        await interaction.response.send_message(
            "❌ I don't have **Manage Channels** permission.", ephemeral=True,
        )
        return
    me = channel.guild.me
    banned = skipped = 0
    for member in list(channel.members):
        if me is not None and member.id == me.id:
            continue
        try:
            ban_member(channel.id, member.id)
            overwrite = channel.overwrites_for(member)
            overwrite.connect = False
            await channel.set_permissions(
                member, overwrite=overwrite,
                reason="Heaven VC Control Panel — VC ban all",
            )
            if _bot_can(channel, "move_members"):
                await member.move_to(
                    None, reason="Heaven VC Control Panel — VC ban all",
                )
            banned += 1
        except (discord.Forbidden, discord.HTTPException):
            skipped += 1
    message = f"⛔ Banned **{banned}** member{'s' if banned != 1 else ''}."
    if skipped:
        message += f"\n⚠️ Skipped **{skipped}**."
    await interaction.response.send_message(message, ephemeral=True)


async def _do_unban_all(
    interaction: discord.Interaction, channel: discord.VoiceChannel,
) -> None:
    banned_ids = get_banned(channel.id)
    if not banned_ids:
        await interaction.response.send_message(
            f"No one is banned from **{channel.name}** right now.",
            ephemeral=True,
        )
        return
    cleared = 0
    for member_id in list(banned_ids):
        unban_member(channel.id, member_id)
        member = channel.guild.get_member(member_id)
        if member is not None:
            try:
                overwrite = channel.overwrites_for(member)
                overwrite.connect = None
                await channel.set_permissions(
                    member, overwrite=overwrite,
                    reason="Heaven VC Control Panel — VC unban all",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
        cleared += 1
    await interaction.response.send_message(
        f"✅ Unbanned **{cleared}** member{'s' if cleared != 1 else ''} — "
        f"they can join **{channel.name}** again.",
        ephemeral=True,
    )


# =====================================================================
# Main panel — the original 14 buttons + nav row.
# =====================================================================


class VCControlPanelView(View):
    """Interactive Heaven VC management panel (main section)."""

    def __init__(
        self,
        bot: discord.Client,
        text_channel: discord.TextChannel | None = None,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.text_channel = text_channel

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await _refresh_view(self, interaction)

    def _nav_views(self) -> tuple["ModerationView", "VoiceView"]:
        return (
            ModerationView(self.bot, self.text_channel),
            VoiceView(self.bot, self.text_channel),
        )

    # -- Row 0: LOCK / UNLOCK / HIDE / SHOW (old panel, unchanged) --
    @discord.ui.button(label="LOCK", emoji="🔒", style=discord.ButtonStyle.secondary, row=0)
    async def lock(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None or not _bot_can(channel, "manage_channels"):
            if channel is not None:
                await interaction.response.send_message(
                    "❌ I don't have **Manage Channels** permission.", ephemeral=True,
                )
            return
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            overwrite.connect = False
            await channel.set_permissions(
                channel.guild.default_role, overwrite=overwrite,
                reason="Heaven VC Control Panel — lock",
            )
            await interaction.response.send_message("🔒 Channel locked.", ephemeral=True)
            await self._refresh(interaction)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot lock this channel.", ephemeral=True)

    @discord.ui.button(label="UNLOCK", emoji="🔓", style=discord.ButtonStyle.secondary, row=0)
    async def unlock(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None or not _bot_can(channel, "manage_channels"):
            if channel is not None:
                await interaction.response.send_message(
                    "❌ I don't have **Manage Channels** permission.", ephemeral=True,
                )
            return
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            overwrite.connect = None
            await channel.set_permissions(
                channel.guild.default_role, overwrite=overwrite,
                reason="Heaven VC Control Panel — unlock",
            )
            await interaction.response.send_message("🔓 Channel unlocked.", ephemeral=True)
            await self._refresh(interaction)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot unlock this channel.", ephemeral=True)

    @discord.ui.button(label="HIDE", emoji="🙈", style=discord.ButtonStyle.secondary, row=0)
    async def hide(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None or not _bot_can(channel, "manage_channels"):
            if channel is not None:
                await interaction.response.send_message(
                    "❌ I don't have **Manage Channels** permission.", ephemeral=True,
                )
            return
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            overwrite.view_channel = False
            await channel.set_permissions(
                channel.guild.default_role, overwrite=overwrite,
                reason="Heaven VC Control Panel — hide",
            )
            owner = interaction.user
            if isinstance(owner, discord.Member):
                owner_overwrite = channel.overwrites_for(owner)
                owner_overwrite.view_channel = True
                owner_overwrite.connect = True
                await channel.set_permissions(
                    owner, overwrite=owner_overwrite,
                    reason="Heaven VC Control Panel — owner access",
                )
            await interaction.response.send_message("👁️ Channel hidden.", ephemeral=True)
            await self._refresh(interaction)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot hide this channel.", ephemeral=True)

    @discord.ui.button(label="SHOW", emoji="👁️", style=discord.ButtonStyle.secondary, row=0)
    async def show(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None or not _bot_can(channel, "manage_channels"):
            if channel is not None:
                await interaction.response.send_message(
                    "❌ I don't have **Manage Channels** permission.", ephemeral=True,
                )
            return
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            overwrite.view_channel = None
            await channel.set_permissions(
                channel.guild.default_role, overwrite=overwrite,
                reason="Heaven VC Control Panel — show",
            )
            await interaction.response.send_message("👁️ Channel visible.", ephemeral=True)
            await self._refresh(interaction)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I cannot show this channel.", ephemeral=True)

    # -- Row 1: ALLOW / REJECT / KICK / MOVE / PULL (old panel) --
    @discord.ui.button(label="ALLOW", emoji="✅", style=discord.ButtonStyle.secondary, row=1)
    async def allow(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "👤 Select the member you want to allow:",
            view=MemberActionView(self, "allow"), ephemeral=True,
        )

    @discord.ui.button(label="REJECT", emoji="❌", style=discord.ButtonStyle.secondary, row=1)
    async def reject(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "🚫 Select the member you want to reject:",
            view=MemberActionView(self, "reject"), ephemeral=True,
        )

    @discord.ui.button(label="KICK", emoji="🚪", style=discord.ButtonStyle.secondary, row=1)
    async def kick(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "🎙️ Select the member to kick:",
            view=MemberActionView(self, "kick"), ephemeral=True,
        )

    @discord.ui.button(label="MOVE", emoji="↔️", style=discord.ButtonStyle.secondary, row=1)
    async def move(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "🔀 Select the destination voice channel:",
            view=MoveChannelView(self, "move"), ephemeral=True,
        )

    @discord.ui.button(label="PULL", emoji="⬇️", style=discord.ButtonStyle.secondary, row=1)
    async def pull(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "⬇️ Select the member to pull:",
            view=MemberActionView(self, "pull"), ephemeral=True,
        )

    # -- Row 2: RENAME / LIMIT / MUTE / KICK ALL / MUTE ALL (old panel) --
    @discord.ui.button(label="RENAME", emoji="✏️", style=discord.ButtonStyle.secondary, row=2)
    async def rename(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        await interaction.response.send_modal(RenameModal(self))

    @discord.ui.button(label="LIMIT", emoji="➕", style=discord.ButtonStyle.secondary, row=2)
    async def limit(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        await interaction.response.send_modal(LimitModal(self))

    @discord.ui.button(label="MUTE", emoji="🔇", style=discord.ButtonStyle.secondary, row=2)
    async def mute(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "🔇 Select the member to mute/unmute:",
            view=MemberActionView(self, "mute"), ephemeral=True,
        )

    @discord.ui.button(label="KICK ALL", emoji="🚪", style=discord.ButtonStyle.secondary, row=2)
    async def kick_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "move_members")
        if channel is None:
            return
        if not _bot_can(channel, "move_members"):
            await interaction.response.send_message(
                "❌ I don't have **Move Members** permission.", ephemeral=True,
            )
            return
        await _do_kick_all(interaction, channel)
        await self._refresh(interaction)

    @discord.ui.button(label="MUTE ALL", emoji="🔇", style=discord.ButtonStyle.secondary, row=2)
    async def mute_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "mute_members")
        if channel is None:
            return
        if not _bot_can(channel, "mute_members"):
            await interaction.response.send_message(
                "❌ I don't have **Mute Members** permission.", ephemeral=True,
            )
            return
        await _bulk_voice_edit(
            interaction, channel, mute=True, verb="muted",
        )
        await self._refresh(interaction)

    # -- Row 3: navigation to the designed UI's other sections --
    @discord.ui.button(label="MODERATION", emoji="🛡️", style=discord.ButtonStyle.primary, row=3)
    async def go_moderation(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, ModerationView(self.bot, self.text_channel))

    @discord.ui.button(label="VOICE", emoji="🎙️", style=discord.ButtonStyle.primary, row=3)
    async def go_voice(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, VoiceView(self.bot, self.text_channel))


# =====================================================================
# Moderation section — the designed UI's Moderation card.
# =====================================================================


class ModerationView(View):
    """Moderation section of the designed panel (10 buttons)."""

    def __init__(
        self,
        bot: discord.Client,
        text_channel: discord.TextChannel | None = None,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.text_channel = text_channel

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await _refresh_view(self, interaction)

    @discord.ui.button(label="VC KICK", emoji="🚪", style=discord.ButtonStyle.secondary, row=0)
    async def vc_kick(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "🎙️ Select the member to kick from this VC:",
            view=MemberActionView(self, "vc_kick"), ephemeral=True,
        )

    @discord.ui.button(label="VC BAN", emoji="⛔", style=discord.ButtonStyle.secondary, row=0)
    async def vc_ban(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "⛔ Select the member to ban from this VC:",
            view=MemberActionView(self, "vc_ban"), ephemeral=True,
        )

    @discord.ui.button(label="VC UNBAN", emoji="✅", style=discord.ButtonStyle.secondary, row=0)
    async def vc_unban(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "✅ Select the banned member to unban:",
            view=MemberActionView(self, "vc_unban"), ephemeral=True,
        )

    @discord.ui.button(label="CLEAR CHATS", emoji="🧹", style=discord.ButtonStyle.secondary, row=0)
    async def clear_chats(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction)
        if channel is None:
            return
        await interaction.response.send_message(
            "🧹 Clear the last 100 messages in the text channel this "
            "panel was opened from? (Voice channels have no text chat.)",
            view=ClearChatsConfirmView(self, self.text_channel, channel),
            ephemeral=True,
        )

    @discord.ui.button(label="VC ACCESS", emoji="🔓", style=discord.ButtonStyle.secondary, row=0)
    async def vc_access(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "👤 Select the member to grant VC access:",
            view=MemberActionView(self, "vc_access"), ephemeral=True,
        )

    @discord.ui.button(label="VC KICK ALL", emoji="🚪", style=discord.ButtonStyle.secondary, row=1)
    async def vc_kick_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "move_members")
        if channel is None:
            return
        await _do_kick_all(interaction, channel)
        await self._refresh(interaction)

    @discord.ui.button(label="VC BAN ALL", emoji="⛔", style=discord.ButtonStyle.secondary, row=1)
    async def vc_ban_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "manage_channels")
        if channel is None:
            return
        await _do_ban_all(interaction, channel)
        await self._refresh(interaction)

    @discord.ui.button(label="VC UNBAN ALL", emoji="✅", style=discord.ButtonStyle.secondary, row=1)
    async def vc_unban_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "manage_channels")
        if channel is None:
            return
        await _do_unban_all(interaction, channel)
        await self._refresh(interaction)

    @discord.ui.button(label="BACK", emoji="⬅️", style=discord.ButtonStyle.primary, row=2)
    async def back(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, VCControlPanelView(self.bot, self.text_channel))

    @discord.ui.button(label="VOICE", emoji="➡️", style=discord.ButtonStyle.primary, row=2)
    async def go_voice(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, VoiceView(self.bot, self.text_channel))


# =====================================================================
# Voice section — the designed UI's Voice card.
# =====================================================================


class VoiceView(View):
    """Voice section of the designed panel (13 buttons)."""

    def __init__(
        self,
        bot: discord.Client,
        text_channel: discord.TextChannel | None = None,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.text_channel = text_channel

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await _refresh_view(self, interaction)

    def _picker(self, interaction: discord.Interaction, action: str, text: str):
        return interaction.response.send_message(
            text, view=MemberActionView(self, action), ephemeral=True,
        )

    @discord.ui.button(label="VMUTE 1", emoji="🔇", style=discord.ButtonStyle.secondary, row=0)
    async def vmute1(self, interaction: discord.Interaction, button: Button) -> None:
        await self._picker(interaction, "vmute1", "🔇 Select the one member to server-mute:")

    @discord.ui.button(label="VUNMUTE 1", emoji="🔊", style=discord.ButtonStyle.secondary, row=0)
    async def vunmute1(self, interaction: discord.Interaction, button: Button) -> None:
        await self._picker(interaction, "vunmute1", "🔊 Select the one member to unmute:")

    @discord.ui.button(label="MUTE ALL", emoji="🔇", style=discord.ButtonStyle.secondary, row=0)
    async def mute_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "mute_members")
        if channel is None:
            return
        await _bulk_voice_edit(interaction, channel, mute=True, verb="muted")
        await self._refresh(interaction)

    @discord.ui.button(label="UNMUTE ALL", emoji="🔊", style=discord.ButtonStyle.secondary, row=0)
    async def unmute_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "mute_members")
        if channel is None:
            return
        await _bulk_voice_edit(interaction, channel, mute=False, verb="unmuted")
        await self._refresh(interaction)

    @discord.ui.button(label="DEAFEN 1", emoji="🎧", style=discord.ButtonStyle.secondary, row=0)
    async def deafen1(self, interaction: discord.Interaction, button: Button) -> None:
        await self._picker(interaction, "deafen1", "🎧 Select the one member to deafen:")

    @discord.ui.button(label="UNDEAFEN 1", emoji="🎧", style=discord.ButtonStyle.secondary, row=1)
    async def undeafen1(self, interaction: discord.Interaction, button: Button) -> None:
        await self._picker(interaction, "undeafen1", "🎧 Select the one member to undeafen:")

    @discord.ui.button(label="DEAFEN ALL", emoji="🎧", style=discord.ButtonStyle.secondary, row=1)
    async def deafen_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "mute_members")
        if channel is None:
            return
        await _bulk_voice_edit(
            interaction, channel, deafen=True, verb="deafened",
        )
        await self._refresh(interaction)

    @discord.ui.button(label="UNDEAFEN ALL", emoji="🎧", style=discord.ButtonStyle.secondary, row=1)
    async def undeafen_all(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "mute_members")
        if channel is None:
            return
        await _bulk_voice_edit(
            interaction, channel, deafen=False, mute=False,
            verb="undeafened",
        )
        await self._refresh(interaction)

    @discord.ui.button(label="VDRAG", emoji="↔️", style=discord.ButtonStyle.secondary, row=1)
    async def vdrag(self, interaction: discord.Interaction, button: Button) -> None:
        channel = _get_control_channel(interaction)
        if channel is not None and get_drag(channel.id) is not None:
            await interaction.response.send_message(
                "↔️ VDrag is already active — use VDrag Stop first.",
                ephemeral=True,
            )
            return
        await self._picker(interaction, "vdrag", "↔️ Select the member to drag into this VC:")

    @discord.ui.button(label="VDRAG STOP", emoji="⏹️", style=discord.ButtonStyle.secondary, row=1)
    async def vdrag_stop(self, interaction: discord.Interaction, button: Button) -> None:
        channel = await _require_control(interaction, "move_members")
        if channel is None:
            return
        drag = clear_drag(channel.id)
        if drag is None:
            await interaction.response.send_message(
                "↔️ VDrag is not active.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"⏹️ VDrag stopped for **{drag['name']}**.", ephemeral=True,
        )
        await self._refresh(interaction)

    @discord.ui.button(label="DRAG ALL", emoji="↔️", style=discord.ButtonStyle.secondary, row=2)
    async def drag_all(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.send_message(
            "↔️ Select the destination voice channel to drag everyone to:",
            view=MoveChannelView(self, "drag_all"), ephemeral=True,
        )

    @discord.ui.button(label="BACK", emoji="⬅️", style=discord.ButtonStyle.primary, row=3)
    async def back(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, VCControlPanelView(self.bot, self.text_channel))

    @discord.ui.button(label="MODERATION", emoji="➡️", style=discord.ButtonStyle.primary, row=3)
    async def go_moderation(self, interaction: discord.Interaction, button: Button) -> None:
        await _switch_view(interaction, ModerationView(self.bot, self.text_channel))


# =====================================================================
# Embed — old panel's embed, extended with the designed UI's status
# pills (Banned / Muted / Deafened / Drag / Chat) and the new sections.
# =====================================================================


def create_control_embed(channel: discord.VoiceChannel) -> discord.Embed:
    """Create the Heaven voice command console."""
    member_limit = channel.user_limit
    limit_text = "∞" if member_limit == 0 else str(member_limit)
    ownership = get_ownership(channel.id)
    owner_text = (
        f"<@{ownership.owner}>" if ownership is not None else "Server Controlled"
    )
    default_role = channel.guild.default_role
    overwrite = channel.overwrites_for(default_role)
    locked = overwrite.connect is False
    hidden = overwrite.view_channel is False
    access_text = "LOCKED" if locked else "OPEN"
    visibility_text = "HIDDEN" if hidden else "VISIBLE"

    # Designed UI status pills, computed live from Discord state.
    banned_ids = get_banned(channel.id)
    banned_names = []
    for member_id in sorted(banned_ids):
        member = channel.guild.get_member(member_id)
        banned_names.append(member.display_name if member else f"<@{member_id}>")
    muted_n = sum(
        1 for m in channel.members
        if m.voice is not None and m.voice.mute
    )
    deafened_n = sum(
        1 for m in channel.members
        if m.voice is not None and m.voice.deaf
    )
    drag = get_drag(channel.id)
    drag_text = f"{drag['name']} → {channel.name}" if drag else "Off"
    chat_text = (
        f"Cleared ×{get_chat_clears(channel.id)}"
        if get_chat_clears(channel.id)
        else "—"
    )

    embed = discord.Embed(
        title="𝐇𝐄𝐀𝐕𝐄𝐍 ・𝐕𝐎𝐈𝐂𝐄 𝐂𝐎𝐍𝐒𝐎𝐋𝐄",
        description=(
            "Private voice management interface\n"
            "Select an operation below to modify this channel."
        ),
        color=discord.Color.from_rgb(42, 42, 48),
    )
    embed.add_field(
        name="CHANNEL",
        value=(
            "```text\n"
            f"NAME       {channel.name}\n"
            f"MEMBERS    {len(channel.members)} / {limit_text}\n"
            f"OWNER      {owner_text}\n"
            "```"
        ),
        inline=False,
    )
    embed.add_field(
        name="ACCESS STATE",
        value=f"`{access_text}`   ·   `{visibility_text}`",
        inline=True,
    )
    embed.add_field(name="CONTROL", value="`VOICE / OWNER`", inline=True)
    embed.add_field(
        name="STATUS",
        value=(
            f"Banned · **{len(banned_ids)}**"
            + (f" — {', '.join(banned_names)}" if banned_names else "")
            + f"\nMuted · **{muted_n}**   Deafened · **{deafened_n}**"
            + f"\nDrag · **{drag_text}**   Chat · **{chat_text}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="ACCESS OPERATIONS",
        value="🔒 `LOCK`  🔓 `UNLOCK`  👁️‍🗨️ `HIDE`  👁️ `SHOW`",
        inline=False,
    )
    embed.add_field(
        name="MODERATION",
        value=(
            "🚪 `VC KICK`  ⛔ `VC BAN`  ✅ `VC UNBAN`  🧹 `CLEAR CHATS`  "
            "🔓 `VC ACCESS`  🚪 `VC KICK ALL`  ⛔ `VC BAN ALL`  "
            "✅ `VC UNBAN ALL`  (🛡️ MODERATION page)"
        ),
        inline=False,
    )
    embed.add_field(
        name="MEMBER OPERATIONS",
        value=(
            "✅ `ALLOW`  ❌ `REJECT`  🚪 `KICK`  ↔️ `MOVE`  ⬇️ `PULL`  "
            "🔇 `MUTE`  🚪 `KICK ALL`  🔇 `MUTE ALL`"
        ),
        inline=False,
    )
    embed.add_field(
        name="VOICE & MEMBER OPERATIONS",
        value=(
            "🔇 `VMUTE 1`  🔊 `VUNMUTE 1`  🔇 `MUTE ALL`  🔊 `UNMUTE ALL`  "
            "🎧 `DEAFEN 1`  🎧 `UNDEAFEN 1`  🎧 `DEAFEN ALL`  "
            "🎧 `UNDEAFEN ALL`  ↔️ `VDRAG`  ⏹️ `VDRAG STOP`  "
            "↔️ `DRAG ALL`  (🎙️ VOICE page)"
        ),
        inline=False,
    )
    embed.add_field(
        name="CHANNEL OPERATIONS",
        value=(
            "🔒 `LOCK VC`  🔓 `UNLOCK VC`  👁️‍🗨️ `HIDE VC`  👁️ `SHOW VC`  "
            "✏️ `RENAME`  ➕ `LIMIT`"
        ),
        inline=False,
    )
    embed.set_footer(
        text="𝑯𝑬𝑨𝑽𝑬𝑵 𝑺𝒀𝑺𝑻𝑬𝑴𝑺  ・  𝑽𝑶𝑰𝑪𝑬 𝑴𝑨𝑵𝑨𝑮𝑬𝑴𝑬𝑵𝑻"
    )
    return embed
