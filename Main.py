import os
import json
import time
import asyncio
import random
import string
import threading
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ── Flask (keeps bot alive via Render/UptimeRobot) ──────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is online! 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ── Trigger storage ──────────────────────────────────────────────────────────
TRIGGERS_FILE = "triggers.json"

def load_triggers():
    if os.path.exists(TRIGGERS_FILE):
        with open(TRIGGERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_triggers(triggers):
    with open(TRIGGERS_FILE, "w") as f:
        json.dump(triggers, f, indent=2)

# ── Temp Mail storage (persistent) ───────────────────────────────────────────
TEMPMAIL_FILE = "tempmails.json"

def load_temp_mails():
    if os.path.exists(TEMPMAIL_FILE):
        with open(TEMPMAIL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_temp_mail(user_id: str, data: dict):
    mails = load_temp_mails()
    mails[user_id] = data
    with open(TEMPMAIL_FILE, "w") as f:
        json.dump(mails, f, indent=2)

def get_temp_mail(user_id: str):
    mails = load_temp_mails()
    return mails.get(user_id)

# ── Discord bot ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Deduplication cache
processed_messages = {}
CACHE_DURATION = 3.0

def is_duplicate(message_id: str) -> bool:
    now = time.time()
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
        print(f"📋 Global commands registered: {len(synced)}")
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            print(f"📋 Synced to guild: {guild.name}")
    except Exception as e:
        print(f"❌ Failed to register commands: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  TEMP MAIL COMMANDS (Using 1secmail.com - Free & No API Key)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="tempmail", description="📧 Tạo email tạm thời (1secmail)")
async def tempmail(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    # Endpoint chuẩn để tạo email ngẫu nhiên của 1secmail
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        email = data[0]
                        login, domain = email.split('@')
                        
                        mail_data = {"login": login, "domain": domain, "email": email}
                        save_temp_mail(str(interaction.user.id), mail_data)
                        
                        embed = discord.Embed(
                            title="✉️ Email Tạm Thời Đã Tạo",
                            description=f"**Email:** `{email}`\n\n💡 Dùng `/checkmail` để kiểm tra thư đến.",
                            color=discord.Color.green()
                        )
                        embed.set_footer(text="⚠️ Email tự động xóa sau 1 giờ không hoạt động")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        await interaction.followup.send("❌ API không trả về email", ephemeral=True)
                else:
                    await interaction.followup.send(f" API lỗi: {resp.status}", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏱️ Timeout: API không phản hồi sau 15 giây", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)[:200]}", ephemeral=True)

@bot.tree.command(name="checkmail", description=" Kiểm tra hộp thư")
@app_commands.describe(email="Email (để trống nếu dùng email đã tạo)")
async def checkmail(interaction: discord.Interaction, email: str = None):
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    
    if not email:
        user_data = get_temp_mail(user_id)
        if not user_data:
            await interaction.followup.send(
                "❌ Bạn chưa tạo email nào.\nDùng `/tempmail` để tạo email mới!", 
                ephemeral=True
            )
            return
        login = user_data.get('login')
        domain = user_data.get('domain')
        email = user_data.get('email')
    else:
        if "@" not in email:
            await interaction.followup.send("❌ Email không hợp lệ!", ephemeral=True)
            return
        login, domain = email.split('@')

    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    messages = await resp.json()
                    if not messages:
                        await interaction.followup.send(
                            f"📭 Hộp thư `{email}` đang trống.\nThư sẽ xuất hiện khi có email gửi đến!", 
                            ephemeral=True
                        )
                    else:
                        msg_list = ""
                        for m in messages[:5]:
                            msg_id = m.get('id', 'N/A')
                            subject = m.get('subject', 'No subject')
                            from_addr = m.get('from', 'Unknown')
                            msg_list += f"**{subject}**\n  ID: `{msg_id}` | Từ: {from_addr}\n\n"
                        
                        embed = discord.Embed(
                            title=f"📬 Hộp thư: {email}",
                            description=f"Có **{len(messages)}** tin nhắn:\n\n{msg_list}",
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="Dùng /readmail <id> để đọc nội dung")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ API trả về lỗi: {resp.status}", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏱️ Timeout: API không phản hồi sau 15 giây", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi kết nối: {str(e)[:200]}", ephemeral=True)

@bot.tree.command(name="readmail", description=" Đọc nội dung tin nhắn")
@app_commands.describe(
    message_id="ID của tin nhắn (lấy từ /checkmail)",
    email="Email (để trống nếu dùng email đã tạo)"
)
async def readmail(interaction: discord.Interaction, message_id: str, email: str = None):
    await interaction.response.defer(ephemeral=True)
    
    user_id = str(interaction.user.id)
    
    if not email:
        user_data = get_temp_mail(user_id)
        if not user_data:
            await interaction.followup.send("❌ Bạn chưa tạo email nào. Dùng `/tempmail`!", ephemeral=True)
            return
        login = user_data.get('login')
        domain = user_data.get('domain')
        email = user_data.get('email')
    else:
        if "@" not in email:
            await interaction.followup.send("❌ Email không hợp lệ!", ephemeral=True)
            return
        login, domain = email.split('@')
    
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={message_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    msg = await resp.json()
                    content = msg.get('textBody', msg.get('body', 'Không có nội dung'))
                    if len(content) > 2000:
                        content = content[:1997] + "..."
                    
                    embed = discord.Embed(
                        title=f"📧 {msg.get('subject', 'No Subject')}",
                        description=content if content else "*Không có nội dung*",
                        color=discord.Color.purple()
                    )
                    embed.add_field(name="📨 Từ", value=msg.get('from', 'N/A'), inline=True)
                    embed.add_field(name="📅 Ngày", value=msg.get('date', 'N/A'), inline=True)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Không tìm thấy tin nhắn (lỗi {resp.status})", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏱️ Timeout: API không phản hồi", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)[:200]}", ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Test bot online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot đang hoạt động tốt! ✅", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  TRIGGER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="addtrigger", description="Add a new auto-response trigger")
@app_commands.describe(word="Word to trigger on", response="Bot reply message")
async def addtrigger(interaction: discord.Interaction, word: str, response: str):
    triggers = load_triggers()
    if any(t["word"].lower() == word.lower() for t in triggers):
        await interaction.response.send_message(f"⚠️ Trigger already exists: **{word}**", ephemeral=True)
        return
    triggers.append({
        "word": word,
        "response": response,
        "active": True,
        "added_by": interaction.user.display_name,
    })
    save_triggers(triggers)
    await interaction.response.send_message(f"✅ Added: **{word}** → *{response}*", ephemeral=True)

@bot.tree.command(name="removetrigger", description="Remove an existing trigger")
@app_commands.describe(word="Trigger word to remove")
async def removetrigger(interaction: discord.Interaction, word: str):
    triggers = load_triggers()
    new_triggers = [t for t in triggers if t["word"].lower() != word.lower()]
    if len(new_triggers) == len(triggers):
        await interaction.response.send_message(f"❌ Not found: **{word}**", ephemeral=True)
        return
    save_triggers(new_triggers)
    await interaction.response.send_message(f"🗑️ Removed: **{word}**", ephemeral=True)

@bot.tree.command(name="edittrigger", description="Edit an existing trigger response")
@app_commands.describe(word="Trigger word to edit", response="New reply message")
async def edittrigger(interaction: discord.Interaction, word: str, response: str):
    triggers = load_triggers()
    for t in triggers:
        if t["word"].lower() == word.lower():
            t["response"] = response
            save_triggers(triggers)
            await interaction.response.send_message(f"✏️ Updated: **{word}** → *{response}*", ephemeral=True)
            return
    await interaction.response.send_message(f"❌ Not found: **{word}**", ephemeral=True)

@bot.tree.command(name="triggerlist", description="List all configured triggers")
async def triggerlist(interaction: discord.Interaction):
    triggers = load_triggers()
    if not triggers:
        await interaction.response.send_message("📭 No triggers yet. Use `/addtrigger`!", ephemeral=True)
        return
    lines = []
    for t in triggers:
        status = "" if t.get("active", True) else " (Disabled)"
        by = t.get("added_by", "unknown")
        lines.append(f"• **{t['word']}**: {t['response']}{status} — *by {by}*")
    await interaction.response.send_message("**Triggers:**\n" + "\n".join(lines), ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="invitetovoicechannel", description="Invite Gamatoto to your voice channel")
async def invitetovoicechannel(interaction: discord.Interaction):
    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await interaction.response.send_message("❌ You need to be in a voice channel first!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    await interaction.response.defer(ephemeral=True)

    try:
        if interaction.guild.voice_client is not None:
            vc = interaction.guild.voice_client
            await vc.move_to(channel)
        else:
            vc = await channel.connect()

        await asyncio.sleep(1)

        if vc.is_playing():
            vc.stop()

        def play_loop(error):
            if error:
                print(f"❌ Player error: {error}")
                return
            if vc.is_connected():
                source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("gamatoto.mp3"), volume=0.5)
                vc.play(source, after=play_loop)

        if os.path.exists("gamatoto.mp3"):
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("gamatoto.mp3"), volume=0.5)
            vc.play(source, after=play_loop)
        else:
            print("⚠️ gamatoto.mp3 not found")

        await interaction.followup.send(f"✅ Gamatoto is going to work in **{channel.name}**! 🐸⛏️", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="stop", description="Stop Gamatoto and disconnect from voice")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message("❌ Gamatoto is not in a voice channel!", ephemeral=True)
        return
    await vc.disconnect()
    await interaction.response.send_message("👋 Gamatoto went home!", ephemeral=True)

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
