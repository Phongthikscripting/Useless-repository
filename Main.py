import os
import json
import time
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ── Flask (keeps bot alive via UptimeRobot) ──────────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "bot is online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ── Trigger storage (JSON file) ───────────────────────────────────────────────
TRIGGERS_FILE = "triggers.json"

def load_triggers():
    if os.path.exists(TRIGGERS_FILE):
        with open(TRIGGERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_triggers(triggers):
    with open(TRIGGERS_FILE, "w") as f:
        json.dump(triggers, f, indent=2)

# ── Discord bot ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Deduplication cache
processed_messages = {}
CACHE_DURATION = 3.0  # seconds

def is_duplicate(message_id: str) -> bool:
    now = time.time()
    # Clean old entries
    expired = [k for k, v in processed_messages.items() if now - v > CACHE_DURATION * 2]
    for k in expired:
        del processed_messages[k]
    if message_id in processed_messages and now - processed_messages[message_id] < CACHE_DURATION:
        return True
    processed_messages[message_id] = now
    return False

@bot.event
async def on_ready():
    print(f"✅ Bot ready as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📋 Commands registered: {len(synced)}")
    except Exception as e:
        print(f"❌ Failed to register commands: {e}")

# ── /addtrigger ───────────────────────────────────────────────────────────────
@bot.tree.command(name="addtrigger", description="...")
@app_commands.describe(word="...", response="...")
async def addtrigger(interaction: discord.Interaction, word: str, response: str):
    triggers = load_triggers()
    if any(t["word"].lower() == word.lower() for t in triggers):
        await interaction.response.send_message(
            f"⚠️ Trigger already exists: **{word}**", ephemeral=True
        )
        return
    triggers.append({"word": word, "response": response, "active": True})
    save_triggers(triggers)
    await interaction.response.send_message(
        f"✅ Added: **{word}** → *{response}*", ephemeral=True
    )

# ── /removetrigger ────────────────────────────────────────────────────────────
@bot.tree.command(name="removetrigger", description="...")
@app_commands.describe(word="...")
async def removetrigger(interaction: discord.Interaction, word: str):
    triggers = load_triggers()
    new_triggers = [t for t in triggers if t["word"].lower() != word.lower()]
    if len(new_triggers) == len(triggers):
        await interaction.response.send_message(
            f"❌ Not found: **{word}**", ephemeral=True
        )
        return
    save_triggers(new_triggers)
    await interaction.response.send_message(
        f"🗑️ Removed: **{word}**", ephemeral=True
    )

# ── /edittrigger ──────────────────────────────────────────────────────────────
@bot.tree.command(name="edittrigger", description="...")
@app_commands.describe(word="...", response="...")
async def edittrigger(interaction: discord.Interaction, word: str, response: str):
    triggers = load_triggers()
    for t in triggers:
        if t["word"].lower() == word.lower():
            t["response"] = response
            save_triggers(triggers)
            await interaction.response.send_message(
                f"✏️ Updated: **{word}** → *{response}*", ephemeral=True
            )
            return
    await interaction.response.send_message(
        f"❌ Not found: **{word}**", ephemeral=True
    )

# ── /triggerlist ──────────────────────────────────────────────────────────────
@bot.tree.command(name="triggerlist", description="...")
async def triggerlist(interaction: discord.Interaction):
    triggers = load_triggers()
    if not triggers:
        await interaction.response.send_message(
            "📭 No triggers yet. Use `/addtrigger`!", ephemeral=True
        )
        return
    lines = [
        f"• **{t['word']}**: {t['response']}{'' if t.get('active', True) else ' (Disabled)'}"
        for t in triggers
    ]
    await interaction.response.send_message(
        f"**Triggers:**\n" + "\n".join(lines), ephemeral=True
    )

# ── /invitetovoicechannel ─────────────────────────────────────────────────────
@bot.tree.command(name="invitetovoicechannel", description="...")
async def invitetovoicechannel(interaction: discord.Interaction):
    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await interaction.response.send_message(
            "❌ You need to be in a voice channel first!", ephemeral=True
        )
        return
    channel = interaction.user.voice.channel
    try:
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        await interaction.response.send_message(
            f"✅ Joined **{channel.name}**!", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error: {e}", ephemeral=True
        )

# ── Message trigger listener ──────────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.content.startswith("/"):
        return
    if is_duplicate(str(message.id)):
        return

    triggers = load_triggers()
    lower = message.content.lower()
    for t in triggers:
        if t.get("active", True) and t["word"].lower() in lower:
            await message.reply(t["response"])
            return

    await bot.process_commands(message)

# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
    else:
        bot.run(token)
