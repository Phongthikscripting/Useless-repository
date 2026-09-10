import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from tempmail import TempMail

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
user_mails = {}

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")

@bot.tree.command(name="tempmail", description="📧 Tạo email tạm thời")
async def create_tempmail(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    temp_mail = TempMail()
    email = temp_mail.generate()
    user_mails[interaction.user.id] = temp_mail
    
    embed = discord.Embed(
        title="✉️ Email Tạm Thời",
        description=f"**Email:** `{email}`\n\nDùng `/checkmail` để kiểm tra",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="checkmail", description="📬 Kiểm tra hộp thư")
async def check_mail(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    temp_mail = user_mails.get(interaction.user.id)
    if not temp_mail:
        await interaction.followup.send("❌ Dùng /tempmail trước!", ephemeral=True)
        return
    
    messages = await temp_mail.get_messages()
    if not messages:
        await interaction.followup.send(" Hộp thư trống", ephemeral=True)
        return
    
    msg_list = "\n".join([f"**{msg['subject']}** - ID: `{msg['id']}`" for msg in messages[:10]])
    embed = discord.Embed(title="📬 Hộp thư", description=msg_list, color=discord.Color.blue())
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="readmail", description="📖 Đọc tin nhắn")
@app_commands.describe(message_id="ID tin nhắn")
async def read_mail(interaction: discord.Interaction, message_id: str):
    await interaction.response.defer(ephemeral=True)
    temp_mail = user_mails.get(interaction.user.id)
    if not temp_mail:
        await interaction.followup.send("❌ Chưa có email", ephemeral=True)
        return
    
    msg = await temp_mail.read_message(message_id)
    if not msg:
        await interaction.followup.send("❌ Không tìm thấy", ephemeral=True)
        return
    
    content = msg.get('textBody', '')[:2000]
    embed = discord.Embed(title=f"📧 {msg.get('subject')}", description=content, color=discord.Color.purple())
    embed.add_field(name="Từ", value=msg.get('from', 'N/A'))
    await interaction.followup.send(embed=embed, ephemeral=True)

def run_bot():
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)

if __name__ == "__main__":
    run_bot()
