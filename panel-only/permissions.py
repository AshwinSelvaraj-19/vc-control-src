"""Trimmed permission check — only what vc_control_panel.py uses.

Source: AshwinSelvaraj-19/vc-control-src @ 01c9d6f2
Original file: bot/utils/permissions.py (76 lines).

Kept: PermissionLevel, can_control_voice_channel() (the only function
the panel calls, via _require_control()).
Removed: is_admin() — used by the settings cog, not by the panel.

Permission model (unchanged):
  1. Server owner -> allow (ADMIN)
  2. Administrator -> allow (ADMIN)
  3. Temp-VC owner (via ownership.get_ownership) -> allow (OWNER)
  4. Member with the required permission (e.g. mute_members /
     move_members) -> allow (MOD)
  5. Otherwise deny (NONE)
"""

from __future__ import annotations

from enum import Enum

import discord

from ownership import get_ownership


class PermissionLevel(Enum):
    """Permission levels for VC commands."""
    OWNER = "owner"  # Temp VC owner
    ADMIN = "admin"  # Server owner or Administrator permission
    MOD = "mod"  # Specific moderation permissions
    NONE = "none"  # No permission


def can_control_voice_channel(
    member: discord.Member,
    channel: discord.VoiceChannel,
    required_permission: str | None = None,
) -> tuple[bool, PermissionLevel]:
    """Determine if a member can control a voice channel."""
    # 1. Server owner
    if member.guild.owner_id == member.id:
        return True, PermissionLevel.ADMIN

    # 2. Administrator permission
    if member.guild_permissions.administrator:
        return True, PermissionLevel.ADMIN

    # 3. Temporary VC owner
    ownership = get_ownership(channel.id)
    if ownership is not None and ownership.owner == member.id:
        return True, PermissionLevel.OWNER

    # 4. Specific moderation permission
    if required_permission is not None:
        if hasattr(member.guild_permissions, required_permission):
            if getattr(member.guild_permissions, required_permission):
                return True, PermissionLevel.MOD

    # 5. No permission
    return False, PermissionLevel.NONE
