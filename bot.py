import discord
from discord.ext import commands
import asyncio
import uuid
import shutil

TOKEN = "YOUR_BOT_TOKEN_HERE"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

active_containers = {}

# ------------------------------------------------
# Check / Install Docker
# ------------------------------------------------
async def ensure_docker_installed():

    if shutil.which("docker"):
        print("✅ Docker already installed")
        return

    print("⚠ Docker not found. Installing...")

    install_cmd = """
apt-get update &&
apt-get install -y ca-certificates curl gnupg lsb-release &&
mkdir -p /etc/apt/keyrings &&
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg &&
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null &&
apt-get update &&
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin &&
systemctl enable docker &&
systemctl start docker
"""

    process = await asyncio.create_subprocess_shell(install_cmd)
    await process.communicate()

    print("✅ Docker installed")


# ------------------------------------------------
# Create VPS Container
# ------------------------------------------------
async def create_vps(user_id):

    container_name = f"freevps_{user_id}_{uuid.uuid4().hex[:6]}"

    docker_command = f"""
docker run -dit \
--memory="4g" \
--cpus="2" \
--storage-opt size=50G \
--pids-limit=200 \
--security-opt=no-new-privileges \
--name {container_name} ubuntu:22.04 bash -c "
apt update &&
apt install -y python3 python3-pip neofetch tmate curl openssh-server git &&
tmate -F"
"""

    process = await asyncio.create_subprocess_shell(
        docker_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return None, stderr.decode()

    # Wait for tmate session to start
    await asyncio.sleep(12)

    get_ssh = f"docker exec {container_name} tmate display -p '#{{tmate_ssh}}'"

    process2 = await asyncio.create_subprocess_shell(
        get_ssh,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    ssh_out, _ = await process2.communicate()
    ssh_link = ssh_out.decode().strip()

    return container_name, ssh_link


# ------------------------------------------------
# Auto Delete VPS
# ------------------------------------------------
async def auto_delete(user_id, container, hours=2):

    await asyncio.sleep(hours * 3600)

    if user_id in active_containers:
        await asyncio.create_subprocess_shell(f"docker rm -f {container}")
        del active_containers[user_id]
        print(f"🗑 Auto deleted VPS for {user_id}")


# ------------------------------------------------
# Bot Ready
# ------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await ensure_docker_installed()


# ------------------------------------------------
# FREE VPS COMMAND
# ------------------------------------------------
@bot.command()
async def freevps(ctx):

    user_id = ctx.author.id

    if user_id in active_containers:
        await ctx.reply("⚠ You already have an active VPS.")
        return

    await ctx.reply("🚀 Creating your VPS... this may take ~30 seconds.")

    container, ssh_link = await create_vps(user_id)

    if not container:
        await ctx.reply("❌ VPS creation failed.")
        return

    active_containers[user_id] = container
    bot.loop.create_task(auto_delete(user_id, container))

    try:
        await ctx.author.send(f"""
🖥 **Your Free VPS Is Ready**

📊 Specs:
• RAM: 4GB
• CPU: 2 Cores
• Disk: 50GB
• OS: Ubuntu 22.04

🔐 SSH Access:
{ssh_link}

⏳ Expires in 2 hours
""")

        await ctx.reply("✅ VPS created! Check your DMs.")

    except discord.Forbidden:
        await ctx.reply("❌ I cannot DM you. Enable DMs.")


# ------------------------------------------------
# STOP VPS COMMAND
# ------------------------------------------------
@bot.command()
async def stopvps(ctx):

    user_id = ctx.author.id

    if user_id not in active_containers:
        await ctx.reply("⚠ You don't have a VPS running.")
        return

    container = active_containers[user_id]

    await asyncio.create_subprocess_shell(f"docker rm -f {container}")
    del active_containers[user_id]

    await ctx.reply("🗑 VPS destroyed.")


# ------------------------------------------------
# RUN BOT
# ------------------------------------------------
bot.run(TOKEN)
