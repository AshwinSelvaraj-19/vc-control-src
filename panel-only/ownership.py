"""Trimmed ownership registry — only what vc_control_panel.py uses.

Source: AshwinSelvaraj-19/vc-control-src @ 01c9d6f2
Original file: bot/utils/ownership.py (117 lines).

Kept: ChannelOwnership, temp_channels / user_channels, register_channel,
unregister_channel, get_ownership (used by the panel embed + RenameModal),
get_channel_for_user.
Removed: delete_task field + set_delete_task / clear_delete_task (used only
by temp-channel autodelete), as_dict(), is_on_cooldown / mark_cooldown
(used only by temp-channel creation).

In the original bot, register_channel() is called when a temp VC is
created. In this panel-only build
nothing creates channels, so the registry stays empty unless the host
bot calls register_channel() itself — in that case the panel embed shows
OWNER = "Server Controlled".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ChannelOwnership:
    """Metadata for a single temporary voice channel."""

    owner: int
    guild: int
    created_at: float = field(default_factory=time.time)


# channel_id -> ChannelOwnership
temp_channels: dict[int, ChannelOwnership] = {}

# user_id -> channel_id (fast reverse lookup)
user_channels: dict[int, int] = {}


def register_channel(channel_id: int, owner_id: int, guild_id: int) -> ChannelOwnership:
    """Record a new temp channel and its owner."""
    ownership = ChannelOwnership(owner=owner_id, guild=guild_id)
    temp_channels[channel_id] = ownership
    user_channels[owner_id] = channel_id
    return ownership


def unregister_channel(channel_id: int) -> ChannelOwnership | None:
    """Remove a temp channel from tracking. Returns the removed record, if any."""
    ownership = temp_channels.pop(channel_id, None)
    if ownership is not None:
        user_channels.pop(ownership.owner, None)
    return ownership


def get_ownership(channel_id: int) -> ChannelOwnership | None:
    """Return the ownership record for a channel, or None."""
    return temp_channels.get(channel_id)


def get_channel_for_user(user_id: int) -> int | None:
    """Return the channel id owned by ``user_id``, or None."""
    return user_channels.get(user_id)


# =====================================================================
# Designed-panel state (new, not in the old repo panel)
# All in-memory only, lost on bot restart — same as ownership above.
# =====================================================================

# channel_id -> set of banned member ids (VC ban, not a guild ban)
banned_channels: dict[int, set[int]] = {}

# channel_id -> {"uid": int, "name": str} while VDrag is active
drag_state: dict[int, dict] = {}

# channel_id -> number of times Clear Chats was run (web UI "Chat" pill)
chat_clears: dict[int, int] = {}


def is_banned(channel_id: int, member_id: int) -> bool:
    return member_id in banned_channels.get(channel_id, set())


def get_banned(channel_id: int) -> set[int]:
    return set(banned_channels.get(channel_id, set()))


def ban_member(channel_id: int, member_id: int) -> None:
    banned_channels.setdefault(channel_id, set()).add(member_id)


def unban_member(channel_id: int, member_id: int) -> None:
    banned_channels.get(channel_id, set()).discard(member_id)


def clear_banned(channel_id: int) -> int:
    n = len(banned_channels.get(channel_id, set()))
    banned_channels[channel_id] = set()
    return n


def get_drag(channel_id: int) -> dict | None:
    return drag_state.get(channel_id)


def set_drag(channel_id: int, member_id: int, name: str) -> None:
    drag_state[channel_id] = {"uid": member_id, "name": name}


def clear_drag(channel_id: int) -> dict | None:
    return drag_state.pop(channel_id, None)


def increment_chat_clears(channel_id: int) -> int:
    chat_clears[channel_id] = chat_clears.get(channel_id, 0) + 1
    return chat_clears[channel_id]


def get_chat_clears(channel_id: int) -> int:
    return chat_clears.get(channel_id, 0)
