import os
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

# ── Discord bot ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"📋 Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")

@bot.tree.command(name="invitetovoicechannel", description="...")
async def invite_to_voice(interaction: discord.Interaction):
    # Check if user is in a voice channel
    if interaction.user.voice is None:
        await interaction.response.send_message(
            "❌ You need to be in a voice channel first!", ephemeral=True
        )
        return

    channel = interaction.user.voice.channel

    # Move or join
    if interaction.guild.voice_client is not None:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message(
        f"✅ Joined **{channel.name}**!", ephemeral=True
    )

# ── Start both ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Run Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run Discord bot (blocking)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not set!")
    else:
        bot.run(token)
