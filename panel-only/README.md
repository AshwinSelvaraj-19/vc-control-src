# VC Control Panel — designed version (Python / discord.py)

This is a **Python discord.py version of the DESIGNED panel** — the
web UI at `~/workspace/your_files/vc-control-panel/vc-control-panel.html`
(HEAVEN VOICE CONSOLE + Moderation / Channel / Voice / Heaven Console
— Original cards). It is **not** the old repo panel: the old panel
(`vc-control-src` @ `01c9d6f2`, `bot/utils/vc_control_panel.py`) had
only 14 buttons; this one implements all 30 unique actions from the
designed UI, with real Discord calls.

## Files

| File | Lines | What it is |
|---|---|---|
| `vc_control_panel.py` | — | The extended panel: main / Moderation / Voice Views, RenameModal, LimitModal, MemberActionView (extended), MoveChannelView (move + drag-all), ClearChatsConfirmView, bulk helpers, `create_control_embed`. |
| `ownership.py` | — | Trimmed ownership registry (old panel) + new in-memory state: VC banned set per channel, VDrag state, Clear Chats count. |
| `permissions.py` | — | `PermissionLevel` + `can_control_voice_channel()` (old panel, unchanged). |
| `open_panel.py` | — | Opener: `@Bot ?vc` (prefix, kept) **and** `/vcpanel` (slash, new). |
| `requirements.txt` | 1 | `discord.py>=2.3.0` — the only dependency. |

## Feature list (all 30, from the designed UI)

**Top console embed** — `𝐇𝐄𝐀𝐕𝐄𝐍 ・𝐕𝐎𝐈𝐂𝐄 𝐂𝐎𝐍𝐒𝐎𝐋𝐄`, colour
RGB 42,42,48, CHANNEL (NAME / MEMBERS n/limit / OWNER), ACCESS STATE
(LOCKED/OPEN · HIDDEN/VISIBLE), CONTROL (`VOICE / OWNER`), plus a
STATUS field with the web UI's pills: Banned · n (names), Muted · n,
Deafened · n, Drag, Chat.

**Moderation** — VC Kick, VC Ban, VC Unban, Clear Chats, VC Access,
VC Kick All, VC Ban All, VC Unban All.
**Channel** — Lock VC, Unlock VC, Hide VC, Show VC, Rename, Limit.
**Voice** — VMute 1, VUnmute 1, Mute All, Unmute All, Deafen 1,
Undeafen 1, Deafen All, Undeafen All, VDrag, VDrag Stop, Drag All.
**Heaven Console — Original** — Allow, Reject, Kick, Move, Pull,
Mute, Kick All. (Kick / Kick All / Mute All also appear in the
console/cards in the web UI; they are one action each here.)

## Emojis — how close to the image can Discord get? (2026-11-23)

**Plainly: Discord cannot look like the image.** The image is a web
page — coloured cards, gradients, and small monochrome SVG icons.
Discord renders every button as a plain grey (`secondary`, or blue
for nav) button with a text label and at most one emoji, and an embed
is plain text fields on a dark background. No colours, gradients, or
cards can be added to Discord buttons.

The closest Discord allows is what this pass does:

- **Every button (41 total) now has a unicode emoji** via
  `discord.py Button(emoji="...")`, with the text label kept —
  e.g. `🔒 LOCK`, `⛔ VC BAN`, `🎧 DEAFEN 1`. The nav buttons that
  previously had the emoji inside the label (`🛡 MODERATION`,
  `🎙 VOICE`, `← BACK`) now carry it as `emoji=` instead, so the
  label is clean text.
- **The embed mirrors the image sections.** `create_control_embed()`
  keeps the original CHANNEL / ACCESS STATE / CONTROL fields, colour
  RGB 42,42,48 and title `𝐇𝐄𝐀𝐕𝐄𝐍 ・𝐕𝐎𝐈𝐂𝐄 𝐂𝐎𝐍𝐒𝐎𝐋𝐄`, and its
  ACCESS OPERATIONS, MODERATION, MEMBER OPERATIONS, CHANNEL
  OPERATIONS and VOICE & MEMBER OPERATIONS fields (VOICE OPERATIONS
  renamed to VOICE & MEMBER OPERATIONS) now list every operation
  prefixed with its emoji. CHANNEL OPERATIONS was expanded to cover
  `LOCK VC / UNLOCK VC / HIDE VC / SHOW VC / RENAME / LIMIT`, not
  just RENAME / LIMIT.
- **No behaviour, handler, View split, or opener changed** — only
  button `emoji=` args and embed field text.

The image itself uses tiny monochrome SVG glyphs, **not unicode
emoji**, so no emoji can be read off it exactly — the glyphs below
are the closest standard-emoji equivalents, checked against the web
UI's SVG meanings (lock = padlock, hide = eye-off, kick = log-out
arrow, ban = prohibition circle, unban = check, clear chats =
chat-bubble-with-X, rename = pencil, VMute = mic-off, deafen =
headphones-off, VDrag = 4-way move arrows).

| Button | Emoji | Notes |
|---|---|---|
| LOCK / UNLOCK | 🔒 / 🔓 | Image: padlock / open padlock — exact match |
| HIDE / SHOW | 👁️‍🗨️ / 👁️ | **Unclear:** image is eye-with-slash / eye. There is no eye-slash unicode emoji, so HIDE uses 👁️‍🗨️ (eye in speech bubble) as the closest available; SHOW is 👁️ |
| ALLOW / REJECT | ✅ / ❌ | Image: green check / red X — exact match |
| KICK, VC KICK, VC KICK ALL, KICK ALL | 🚪 | Image: log-out arrow — 🚪 (exit) is the closest single emoji |
| MOVE / VDRAG / DRAG ALL | ↔️ | Image: 4-way move arrows — ↔️ is the closest single emoji |
| PULL | ⬇️ | Image: down-arrow into a user |
| RENAME / LIMIT | ✏️ / ➕ | Image: pencil / users-with-plus |
| MUTE, MUTE ALL, VMUTE 1 | 🔇 | Image: speaker/mic with X |
| VUNMUTE 1, UNMUTE ALL | 🔊 | Image: mic / speaker with sound waves |
| VC BAN, VC BAN ALL | ⛔ | Image: red prohibition circle |
| VC UNBAN, VC UNBAN ALL | ✅ | Image: green check |
| CLEAR CHATS, CLEAR (confirm) | 🧹 | **Unclear:** image is a chat bubble with an X — no single emoji for that; 🧹 (broom, "clear") is used, matching the bot's own reply text |
| VC ACCESS | 🔓 | Image: padlock — open padlock = granted access |
| DEAFEN 1 / ALL, UNDEAFEN 1 / ALL | 🎧 | **Unclear / duplicates:** image shows headphones with/without a slash for deafen vs undeafen; there is no slashed-headphones emoji, so all four use 🎧 and are told apart by their labels |
| VDRAG STOP | ⏹️ | Image: stop square in a circle |
| CANCEL (confirm) | ❌ | — |
| MODERATION nav / VOICE nav | 🛡️ / 🎙️ | Shield / microphone — as before, now as `emoji=` |
| BACK / VOICE → / MODERATION → nav | ⬅️ / ➡️ | Labels are now clean `BACK` / `VOICE` / `MODERATION`; the arrow lives in the emoji |

## View split — why, and where each button lives

Discord allows **max 5 rows × 5 buttons = 25 buttons per View**.
The designed UI has 30 unique actions, so one View cannot hold them.
Nothing was dropped; the split is:

| View | Buttons | Rows |
|---|---|---|
| `VCControlPanelView` (main) | LOCK, UNLOCK, HIDE, SHOW (row 0); ALLOW, REJECT, KICK, MOVE, PULL (row 1); RENAME, LIMIT, MUTE, KICK ALL, MUTE ALL (row 2); 🛡 MODERATION, 🎙 VOICE nav (row 3) | 16 |
| `ModerationView` | VC KICK, VC BAN, VC UNBAN, CLEAR CHATS, VC ACCESS (row 0); VC KICK ALL, VC BAN ALL, VC UNBAN ALL (row 1); ← BACK, VOICE → (row 2) | 10 |
| `VoiceView` | VMUTE 1, VUNMUTE 1, MUTE ALL, UNMUTE ALL, DEAFEN 1 (row 0); UNDEAFEN 1, DEAFEN ALL, UNDEAFEN ALL, VDRAG, VDRAG STOP (row 1); DRAG ALL (row 2); ← BACK, MODERATION → (row 3) | 13 |

Channel actions live in the main view (they are the old panel's
rows 0 and 2), so no separate Channel view is needed. Nav buttons
swap the panel message to the other View with the same embed
(`_switch_view`); every View re-renders the embed on refresh, so
counts/pills stay in step whichever page you are on. All Views time
out after 900 s, pickers/modals after 60 s, as in the old panel.

## How each new feature works in Discord

- **VC Ban / Unban (1 / All)** — *not* a guild ban. Sets a
  per-member overwrite `connect=False` on the VC, kicks the member
  out of the VC if they are in it, and records them in an in-memory
  banned set (`ownership.banned_channels`). Unban removes the set
  entry and sets the overwrite `connect=None`. Banned members are
  blocked from Pull, VDrag, Move and Drag All until unbanned.
- **Clear Chats** — voice channels have **no text chat**, so there is
  nothing to purge inside a VC. This purges up to 100 messages in
  the **text channel the panel was opened from** (stored on the View
  when `?vc` / `/vcpanel` runs), after an ephemeral Confirm/Cancel
  step. Requires Manage Messages in that text channel. Messages
  older than 14 days cannot be bulk-deleted (Discord limit) and the
  purge will report that. If the panel was opened from a DM / no
  text channel, Clear Chats tells you to open it from a text channel.
- **Deafen 1 / Undeafen 1 / Deafen All / Undeafen All** —
  `member.edit(deafen=True/False)` (server deafen). Deafening also
  server-mutes, undeafening also unmutes, matching the web UI.
- **VMute 1 / VUnmute 1** — `member.edit(mute=True/False)` for one
  picked member. The old Mute button still toggles.
  **Unmute All** — the old panel had no unmute-all; added here.
- **VDrag / Drag All / VDrag Stop** — VDrag picks a member, moves
  them into this VC (`member.move_to(channel)`) and stores
  `{uid, name}` in `ownership.drag_state` (shown in the embed).
  VDrag Stop clears it. Drag All picks a destination VC and moves
  everyone there (banned members skipped), then clears drag state.
  Move (original) is the same move-all, also skipping banned members.
- **Lock / Unlock / Hide / Show / Rename / Limit / Allow / Reject /
  Kick / Pull / Mute / Kick All / Mute All** — the old panel's exact
  behaviour, reused verbatim (overwrites on `@everyone` / the member,
  RenameModal with the `︱` prefix for owned temp VCs, LimitModal
  0–99, 0 = unlimited).

## How to add it to a bot

```bash
pip install -r requirements.txt
```

In your bot's startup code (discord.py 2.x, `commands.Bot` with
`message_content`, `voice_states`, `guilds`, `members` intents;
the bot needs Manage Channels / Move Members / Mute Members in the
server):

```python
await bot.load_extension("open_panel")
```

Then, in Discord, join a voice channel and run either:

- `@Bot ?vc` — prefix opener (mention the bot + ` ?`), or
- `/vcpanel` — slash command (see below).

The panel appears as the `𝐇𝐄𝐀𝐕𝐄𝐍 ・𝐕𝐎𝐈𝐂𝐄 𝐂𝐎𝐍𝐒𝐎𝐋𝐄` embed.
Use the 🛡 MODERATION / 🎙 VOICE buttons (row 3) to switch sections,
← BACK to return.

### /vcpanel registration / sync

`setup()` in `open_panel.py` calls `await bot.tree.sync()` once when
the cog loads, registering `/vcpanel` globally. **Global commands can
take up to ~1 hour to appear the first time.** For instant testing,
sync to one guild instead in your startup code:

```python
guild = discord.Object(id=YOUR_GUILD_ID)
await bot.tree.sync(guild=guild)
```

Do not call `tree.sync()` on every message or in an `on_ready` loop
— Discord rate-limits it. After the first sync, restarts do not need
a re-sync unless commands change. If `/vcpanel` does not show up yet,
`?vc` still works — it needs no sync at all.

## What is in-memory only

Ownership, the VC banned set, VDrag state and the Clear Chats count
are all in-memory (`ownership.py`) and are **lost on bot restart** —
same as the old panel's ownership registry. If nothing registers a
channel, the embed shows OWNER = "Server Controlled" and the `︱`
rename prefix is not applied; a host bot can call
`ownership.register_channel(channel_id, owner_id, guild_id)`.
Bans do not survive a restart either — re-ban after a restart if
needed. There is no database / Supabase in this package.

## What could NOT be implemented in Discord

- **A single 30-button View** — Discord's hard limit is 25 buttons
  per View (5×5). Solved with the 3-View split above; no feature
  was dropped.
- **Clear Chats inside the VC itself** — voice channels have no
  message history to purge. Implemented as a purge of the text
  channel the panel was opened from (see above).
- **A "VC ban" as a Discord guild ban** — there is no per-VC ban in
  Discord. Implemented as a per-member `connect=False` overwrite +
  kick + in-memory banned set, which is what the web UI's ban
  behaviour amounts to.
- **Live speaking / drag-following** — VDrag in the web UI is a
  state flag; in Discord it is a one-time move + a stored drag state,
  not a live follow. There is no Discord API to keep dragging a
  member as they move channels.

## Verification

- `python3 -m py_compile` passes on every `.py` in this folder.
- Harness (see parent report): imports the panel in a venv with
  discord.py 2.7.1, instantiates every View, lists all buttons by
  label/row, and renders `create_control_embed` with a fake channel.
- This is a syntax + instantiation check only, **not** a live
  Discord test. Confirm live by running the bot and using
  `/vcpanel` (or `?vc`) in a server.
