#!/usr/bin/env python3
"""Generate the public commands page (ataraxia-bot.com/commands) from the bot source.

The script scans ``bot/cogs/**`` for hybrid commands (no bot import, no
dependencies – it only parses the source with ``ast``), groups them with the
curated layout in ``CATEGORIES`` below and fills ``commands_template.html``.

Usage (from the repository root)::

    python3 website/generate_commands.py            # -> website/build/commands/index.html
    python3 website/generate_commands.py --list     # only print the commands found
    python3 website/generate_commands.py --out /some/path/index.html

Deploy the result to the web server::

    scp website/build/commands/index.html root@<server>:/var/www/ataraxia-bot.com/commands/index.html

When a command is added, renamed or removed in the bot, the script stops with a
list of commands that are missing from (or unknown to) ``CATEGORIES``. Add the
new command to the fitting group there and run it again.

Hidden prefix commands (``hidden=True``) are owner-only and never listed;
further commands to leave out go into ``EXCLUDED``.
"""
from __future__ import annotations

import argparse
import ast
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COGS_DIR = ROOT / "bot" / "cogs"
TEMPLATE = Path(__file__).resolve().parent / "commands_template.html"
DEFAULT_OUT = Path(__file__).resolve().parent / "build" / "commands" / "index.html"

ADMIN, PREMIUM = "admin", "premium"

# --------------------------------------------------------------------------- #
# Curated layout: (id, emoji, title, blurb, [(group title, group blurb, [commands])])
# Every public command must appear exactly once.
# --------------------------------------------------------------------------- #
CATEGORIES = [
    ("general", "🌸", "General", "The basics: help, bot info and server insights.", [
        ("Bot", None, ["help", "about", "hello"]),
        ("/info", "Server and member information", ["info server", "info member"]),
    ]),
    ("moderation", "🛡️", "Moderation", "Warnings, punishments, cleanup and verification.", [
        ("Warnings", None, ["warn", "warnings", "delwarn"]),
        ("Punishments", None, ["timeout", "kick", "ban"]),
        ("Cleanup", None, ["channel cleanup"]),
        ("Verification", None, ["verification setup"]),
    ]),
    ("roles", "🎭", "Roles", "Automatic, self-assignable and custom roles.", [
        ("/autorole", "Give roles to new members automatically",
         ["autorole enable", "autorole disable", "autorole add", "autorole remove", "autorole list", "autorole clear"]),
        ("/reactionroles", "Self-assignable roles via reactions, buttons and menus", ["reactionroles dashboard"]),
        ("/parentrole", "Category roles that follow their child roles",
         ["parentrole create", "parentrole addchild", "parentrole removechild", "parentrole delete", "parentrole list"]),
        ("/customrole", "Let members design their own role",
         ["customrole setup", "customrole toggle", "customrole manage"]),
    ]),
    ("leveling", "📈", "Leveling", "Ranks, XP settings, multipliers and level rewards.", [
        ("Rank & leaderboard", None, ["rank", "leaderboard"]),
        ("/levelrole", "Role rewards for reaching a level",
         ["levelrole add", "levelrole remove", "levelrole list", "levelrole sync"]),
        ("/xp", "How XP is earned on the server",
         ["xp info", "xp cooldown", "xp messagexp", "xp voiceinterval", "xp voicexp", "xp embed"]),
        ("/xp – manage members", "Change the XP and level of individual members",
         ["xp add", "xp remove", "xp setlevel", "xp transfer"]),
        ("/xpmultiplier", "Boost XP in channels or for roles",
         ["xpmultiplier channel", "xpmultiplier removechannel", "xpmultiplier role", "xpmultiplier removerole",
          "xpmultiplier list"]),
        ("/voicexp-requirements", "Who earns XP in voice channels",
         ["voicexp-requirements view", "voicexp-requirements set-afk", "voicexp-requirements set-deaf",
          "voicexp-requirements set-muted", "voicexp-requirements set-alone", "voicexp-requirements reset"]),
    ]),
    ("economy", "💰", "Economy", "Earn coins, gamble and spend them in the shop.", [
        ("Wallet & bank", None, ["balance", "deposit", "withdraw", "gift", "richest"]),
        ("Earning", None, ["daily", "weekly", "work", "beg", "crime", "rob"]),
        ("Gambling", None, ["coinflip", "dice", "slots", "roulette", "blackjack", "crash"]),
        ("Shop & inventory", None, ["shop", "buy", "inventory", "use"]),
        ("/shopadmin", "Manage the server shop", ["shopadmin addrole", "shopadmin remove", "shopadmin list"]),
    ]),
    ("server", "⚙️", "Server Setup", "Configure the bot for your server.", [
        ("Quick start", None, ["quicksetup"]),
        ("/welcome", "Welcome messages for new members", ["welcome dashboard", "welcome disable"]),
        ("/log", "Log channels and traffic embeds",
         ["log set", "log clear", "log disable", "log status", "log embed", "log embed-reset"]),
        ("/serverstats", "Auto-updating statistics channels", ["serverstats setup", "serverstats reset"]),
        ("/settings color", "Embed colors", ["settings color set", "settings color view", "settings color reset"]),
        ("/settings prefix", "Custom text prefixes",
         ["settings prefix add", "settings prefix remove", "settings prefix view", "settings prefix reset"]),
        ("/bump", "Bump reminders", ["bump enable", "bump disable", "bump status"]),
        ("/botannouncements", "News and updates from the Ataraxia team",
         ["botannouncements set", "botannouncements clear", "botannouncements status"]),
    ]),
    ("tickets", "🎫", "Tickets & Voice", "Support tickets and temporary voice channels.", [
        ("/ticket", "Support ticket system",
         ["ticket setup", "ticket panel", "ticket paneledit", "ticket panellist", "ticket opendashboard",
          "ticket openpreview", "ticket add", "ticket remove"]),
        ("/tempvoice", "Join-to-create voice channels",
         ["tempvoice setup", "tempvoice panel", "tempvoice info", "tempvoice remove", "tempvoice reset"]),
    ]),
    ("messages", "🎨", "Embeds & Messages", "Embed builder, auto-responses, sticky messages and quotes.", [
        ("/embed", "Visual embed builder", ["embed create", "embed edit"]),
        ("/triggerembed", "Embeds that are sent when a trigger word is used",
         ["triggerembed create", "triggerembed edit", "triggerembed list", "triggerembed delete"]),
        ("/stickymessage", "Keep a message at the bottom of a channel",
         ["stickymessage set", "stickymessage clear", "stickymessage refresh", "stickymessage status"]),
        ("Quotes", None, ["quote", "quoteset"]),
        ("Other", None, ["say", "steal"]),
    ]),
    ("ai", "🤖", "AI & Chat", "AI assistant, translation and the chat personality.", [
        ("/ai", "Ataraxia AI assistant", ["ai ask", "ai status", "ai clearhistory"]),
        ("Translation", None, ["tr", "trset"]),
        ("/chatpersona", "Let the bot join the chat with its own personality",
         ["chatpersona status", "chatpersona enable", "chatpersona test", "chatpersona chance", "chatpersona cooldown",
          "chatpersona gifchance", "chatpersona stickerchance", "chatpersona stickercooldown", "chatpersona language",
          "chatpersona traits", "chatpersona profanity", "chatpersona replymode", "chatpersona ai",
          "chatpersona resetlearning"]),
        ("/chatpersona blacklist", "Limit the chat personality to certain channels",
         ["chatpersona blacklist add", "chatpersona blacklist remove", "chatpersona blacklist list",
          "chatpersona blacklist clear", "chatpersona blacklist mode"]),
    ]),
    ("math", "🧮", "Math", "Calculator, equation solver, calculus and matrices.", [
        ("/math", "Calculate and solve",
         ["math help", "math calc", "math solve", "math solve_system", "math derivative", "math integrate",
          "math sum", "math limit"]),
        ("/math matrix", "Matrix operations",
         ["math matrix multiply", "math matrix determinant", "math matrix inverse", "math matrix eigenvalues"]),
    ]),
    ("fun", "🎮", "Fun & Games", "Small games and the counting channel.", [
        ("Fun", None, ["8ball", "flipcoin", "poll", "joke"]),
        ("/counting", "Counting channel",
         ["counting setup", "counting remove", "counting reset", "counting status", "counting leaderboard"]),
    ]),
    ("premium", "💎", "Premium", "Premium status and premium-only extras.", [
        ("/premium", None, ["premium info", "premium redeem"]),
        ("Server profile", "Give the bot its own look on your server",
         ["premium set_server_profile", "premium view_server_profile", "premium reset_server_profile"]),
    ]),
]

# Public slash commands that are bot-owner only and therefore not listed.
EXCLUDED = {"premium grant"}

# Badges for commands whose permission check is not a plain
# ``@commands.has_permissions(administrator=True)`` decorator (check inside the
# function body, on the parent group, a different permission, or Premium).
# "mod:<text>" renders an orange permission badge with that text.
BADGES = {
    "warn": ["mod:Moderate Members"], "warnings": ["mod:Moderate Members"], "delwarn": ["mod:Moderate Members"],
    "timeout": ["mod:Moderate Members"], "kick": ["mod:Kick Members"], "ban": ["mod:Ban Members"],
    "bump enable": [ADMIN], "bump disable": [ADMIN], "say": [ADMIN],
    "chatpersona blacklist add": [ADMIN], "chatpersona blacklist remove": [ADMIN],
    "chatpersona blacklist list": [ADMIN], "chatpersona blacklist clear": [ADMIN],
    "chatpersona blacklist mode": [ADMIN],
    "ticket add": ["staff"], "ticket remove": ["staff"],
    "settings prefix add": [ADMIN, PREMIUM],
    "xp add": [ADMIN, PREMIUM], "xp remove": [ADMIN, PREMIUM],
    "xp setlevel": [ADMIN, PREMIUM], "xp transfer": [ADMIN, PREMIUM],
    "premium set_server_profile": ["mod:Manage Server", PREMIUM],
    "premium reset_server_profile": ["mod:Manage Server", PREMIUM],
    "premium view_server_profile": ["mod:Manage Server", PREMIUM],
}

# Descriptions that are missing or unclear in the source.
DESCRIPTIONS = {
    "8ball": "Ask the magic 8-ball a question",
    "flipcoin": "Flip a coin",
    "poll": "Create a reaction poll with 2–10 comma-separated options",
    "hello": "Says hello",
    "say": "Make the bot send a message or attachment, optionally as a reply",
    "quicksetup": "Step-by-step interactive setup wizard for your server",
    "balance": "View your wallet and bank balance, or another member's",
    "xp add": "Add XP to a user",
    "xp remove": "Remove XP from a user",
    "xp setlevel": "Set a user to a specific level (up or down)",
    "xp transfer": "Transfer XP from one user to another",
    "settings prefix add": "Add a custom prefix for this server",
    "customrole manage": "Create or edit your own custom role (if your roles are allowed to)",
    "customrole setup": "Set the anchor role and the roles allowed to create custom roles",
    "customrole toggle": "Turn custom roles on or off for the server",
    "ai ask": "Ask the AI a question (daily limit depends on your tier)",
    "tr": "Translate text or the message you reply to, optionally AI-powered",
    "quote": "Quote a message to the quotes channel – also available via right-click → Apps → Quote Message",
    "quoteset": "Set the channel quotes are sent to (leave empty to disable)",
    "premium set_server_profile": "Set the bot's nickname, bio, avatar and banner for this server",
    "premium reset_server_profile": "Reset the bot's server-specific profile fields",
    "premium view_server_profile": "View the bot's server-specific profile",
    "steal": "Copy a custom emoji or sticker from a message to this server",
    "reactionroles dashboard": "Open the Reaction Roles setup dashboard",
    "parentrole create": "Create a parent role that is given automatically with its child roles",
    "counting setup": "Set up a counting channel",
    "counting remove": "Remove the counting channel",
}

BADGE_HTML = {
    ADMIN: '<span class="badge badge-admin">🔒 Admin</span>',
    PREMIUM: '<span class="badge badge-premium">💎 Premium</span>',
    "staff": '<span class="badge badge-mod">🎫 Support staff</span>',
}


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _kwarg(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            try:
                return ast.literal_eval(kw.value)
            except ValueError:
                return ast.unparse(kw.value)
    return None


def _command_decorators(func):
    """Yield (decorator, attribute name, base expression) for ``@x.y(...)`` decorators."""
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            yield dec, dec.func.attr, ast.unparse(dec.func.value)


def extract_commands(cogs_dir: Path = COGS_DIR) -> dict[str, dict]:
    """Return ``{qualified name: info}`` for every non-hidden command in the cogs."""
    found: dict[str, dict] = {}
    for path in sorted(cogs_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            # ``class X(commands.GroupCog, group_name="...")`` prefixes all its commands
            cog_group = next((ast.literal_eval(k.value) for k in cls.keywords if k.arg == "group_name"), None)
            funcs = [n for n in cls.body if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))]

            # 1) groups: function name -> qualified group name ("math matrix")
            declared = []
            for func in funcs:
                for dec, attr, base in _command_decorators(func):
                    if attr in ("hybrid_group", "group"):
                        parent = base if base != "commands" else _kwarg(dec, "parent")
                        declared.append((func.name, _kwarg(dec, "name") or func.name, parent))
            groups: dict[str, str] = {}
            for _ in range(len(declared) + 1):  # resolve nesting regardless of order
                for func_name, name, parent in declared:
                    groups[func_name] = f"{groups[parent]} {name}" if parent in groups else name

            # 2) commands
            for func in funcs:
                info, perms, describe = None, [], {}
                for dec, attr, base in _command_decorators(func):
                    if attr in ("hybrid_command", "command"):
                        name = _kwarg(dec, "name") or func.name
                        if base in groups:
                            name = f"{groups[base]} {name}"
                        elif cog_group and base == "commands":
                            name = f"{cog_group} {name}"
                        info = {"name": name, "desc": _kwarg(dec, "description"), "hidden": bool(_kwarg(dec, "hidden"))}
                    elif attr == "has_permissions":
                        perms += [k.arg for k in dec.keywords]
                    elif attr == "describe":
                        for k in dec.keywords:
                            try:
                                describe[k.arg] = ast.literal_eval(k.value)
                            except ValueError:
                                pass
                if not info or info["hidden"]:
                    continue

                args = func.args
                positional_defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
                params = []
                for arg, default in zip(args.args + args.kwonlyargs, positional_defaults + list(args.kw_defaults)):
                    if arg.arg in ("self", "ctx", "interaction"):
                        continue
                    annotation = ast.unparse(arg.annotation) if arg.annotation else ""
                    params.append({
                        "name": arg.arg,
                        "optional": default is not None or "Optional" in annotation,
                        "help": describe.get(arg.arg),
                    })
                info.update(params=params, perms=perms,
                            doc=(ast.get_docstring(func) or "").split("\n")[0],
                            source=f"{path.relative_to(ROOT)}:{func.lineno}")
                if info["name"] in found:
                    sys.exit(f"Duplicate command /{info['name']}: {found[info['name']]['source']} and {info['source']}")
                found[info["name"]] = info
    return found


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _badges(cmd: dict) -> str:
    kinds = BADGES.get(cmd["name"])
    if kinds is None:
        kinds = [ADMIN] if "administrator" in cmd["perms"] else []
    return "".join(
        BADGE_HTML[k] if k in BADGE_HTML else f'<span class="badge badge-mod">🛡️ {html.escape(k[4:])}</span>'
        for k in kinds)


def _description(cmd: dict) -> str:
    text = DESCRIPTIONS.get(cmd["name"]) or cmd["desc"] or cmd["doc"] or ""
    return re.sub(r"^\[(ADMIN|PREMIUM)\]\s*", "", text).rstrip(".")


def _row(cmd: dict) -> str:
    args = ""
    for p in cmd["params"]:
        text = ("[%s]" if p["optional"] else "<%s>") % p["name"]
        title = f' title="{html.escape(p["help"], quote=True)}"' if p["help"] else ""
        args += f' <span class="arg {"opt" if p["optional"] else "req"}"{title}>{html.escape(text)}</span>'
    desc = _description(cmd)
    search = html.escape(f"{cmd['name']} {desc}".lower(), quote=True)
    return (f'<li class="cmd-row" data-search="{search}">'
            f'<div class="cmd-line"><code class="cmd-usage"><span class="cmd-name">/{html.escape(cmd["name"])}</span>{args}</code>'
            f'<span class="badges">{_badges(cmd)}</span></div>'
            f'<p class="cmd-desc">{html.escape(desc)}</p></li>')


def check_layout(commands: dict[str, dict]) -> list[str]:
    """Make sure CATEGORIES covers every public command exactly once; return the placed names."""
    placed = [name for *_, groups in CATEGORIES for _, _, names in groups for name in names]
    missing = sorted(set(commands) - set(placed) - EXCLUDED)
    unknown = sorted(set(placed) - set(commands))
    dupes = sorted({n for n in placed if placed.count(n) > 1})
    problems = []
    if missing:
        problems.append("Commands in the bot that are not in CATEGORIES (add them to a group, or to EXCLUDED):\n"
                        + "\n".join(f"  /{n}   ({commands[n]['source']})" for n in missing))
    if unknown:
        problems.append("Commands in CATEGORIES that no longer exist in the bot (remove or rename them):\n"
                        + "\n".join(f"  /{n}" for n in unknown))
    if dupes:
        problems.append("Commands listed more than once in CATEGORIES:\n" + "\n".join(f"  /{n}" for n in dupes))
    if problems:
        sys.exit("\n\n".join(problems))
    return placed


def render(commands: dict[str, dict]) -> tuple[str, int]:
    placed = check_layout(commands)
    nav, panels = [], []
    for cat_id, emoji, title, blurb, groups in CATEGORIES:
        count = sum(len(names) for _, _, names in groups)
        nav.append(
            f'<li><a href="#{cat_id}" class="cat-link" data-cat="{cat_id}"><span class="cat-emoji" aria-hidden="true">{emoji}</span>'
            f'<span class="cat-label">{html.escape(title)}</span><span class="cat-count">{count}</span></a></li>')
        group_html = []
        for group_title, group_blurb, names in groups:
            sub = f'<p class="group-desc">{html.escape(group_blurb)}</p>' if group_blurb else ""
            mono = " mono" if group_title.startswith("/") else ""
            group_html.append(
                f'<div class="cmd-group"><div class="group-head"><h3 class="group-title{mono}">{html.escape(group_title)}</h3>{sub}</div>'
                f'<ul class="cmd-list">{"".join(_row(commands[n]) for n in names)}</ul></div>')
        panels.append(
            f'<section class="cat-panel" id="{cat_id}" data-cat="{cat_id}">'
            f'<div class="panel-head"><h2><span aria-hidden="true">{emoji}</span> {html.escape(title)}</h2>'
            f'<p>{html.escape(blurb)}</p></div>{"".join(group_html)}</section>')

    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{NAV}}", "\n".join(nav))
            .replace("{{PANELS}}", "\n".join(panels))
            .replace("{{TOTAL}}", str(len(placed)))
            .replace("{{NCATS}}", str(len(CATEGORIES))))
    if "{{" in page:
        sys.exit(f"Unfilled placeholder left in {TEMPLATE.name}")
    return page, len(placed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output file (default: {DEFAULT_OUT.relative_to(ROOT)})")
    parser.add_argument("--list", action="store_true", help="print the commands found in the bot and exit")
    args = parser.parse_args()

    commands = extract_commands()
    if args.list:
        for name, cmd in sorted(commands.items()):
            usage = " ".join(("[%s]" if p["optional"] else "<%s>") % p["name"] for p in cmd["params"])
            print(f"/{name} {usage}".rstrip().ljust(70), cmd["source"])
        return

    page, total = render(commands)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"{total} commands in {len(CATEGORIES)} categories -> {args.out}")


if __name__ == "__main__":
    main()
