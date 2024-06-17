import discord
from discord.ext import commands, tasks
import feedparser
import os
import asyncio

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store configurations for each server
server_configs = {}

# Latest entries to keep track of updates per server
latest_entries = {}

# RSS feed URL
RSS_URL = "https://rssnovelupdates.com/rss.php?uid=588606&unq=6514b05d3eabc&type=4&lid=local"

# Function to check if a user is an admin
def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_guild_join(guild):
    # When the bot joins a server, prompt for channel and role IDs
    channel = guild.system_channel or discord.utils.get(guild.text_channels)
    if channel:
        try:
            await channel.send("Hello! Please use the `!setup` command to configure the bot.")
        except discord.Forbidden:
            print(f"Missing permissions to send a message in the system channel of {guild.name}")

@bot.command(name='setup')
@commands.check(is_admin)
async def setup(ctx):
    try:
        await ctx.send("Please provide the channel ID where I should post updates:")
    except discord.Forbidden:
        await ctx.send("I don't have permission to send messages in this channel. Please check my permissions and try again.")
        return

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for('message', check=check, timeout=300)
        channel_id = int(msg.content)
        await ctx.send("Now, please provide the role ID to ping for updates:")
        msg = await bot.wait_for('message', check=check, timeout=300)
        role_id = int(msg.content)

        server_configs[ctx.guild.id] = {'channel_id': channel_id, 'role_id': role_id}
        await ctx.send("Configuration saved! Starting to look for updates...")

        # Start the update checking task after setup is completed
        check_for_updates.start()

    except asyncio.TimeoutError:
        await ctx.send("Setup timed out. Please use the `!setup` command to try again.")
    except discord.Forbidden:
        await ctx.send("I don't have permission to send messages in this channel. Please check my permissions and try again.")

@bot.command(name='latest')
async def latest(ctx):
    config = server_configs.get(ctx.guild.id)
    if config:
        latest_entry = latest_entries.get(ctx.guild.id)
        if latest_entry:
            role = ctx.guild.get_role(config['role_id'])
            link = f"[{latest_entry['title']}]({latest_entry['link']})"
            await ctx.send(f"Latest chapter:\nTitle: {latest_entry['title']}\nLink: {link}")
        else:
            await ctx.send("No latest chapter found.")
    else:
        await ctx.send("Bot is not configured. Please ask an admin to use the `!setup` command.")

@bot.command(name='check')
async def check(ctx):
    await ctx.send("Checking for new chapter updates...")
    await check_for_updates_task(ctx.guild.id, ctx)

@tasks.loop(minutes=5)
async def check_for_updates():
    for guild_id in server_configs.keys():
        await check_for_updates_task(guild_id)

async def check_for_updates_task(guild_id, ctx=None):
    config = server_configs.get(guild_id)
    if not config:
        print(f"No configuration found for guild ID {guild_id}")
        return

    # Parse the RSS feed
    feed = feedparser.parse(RSS_URL)
    if feed.bozo:
        print("Failed to parse RSS feed.")
        return

    latest_entry = feed.entries[0] if feed.entries else None
    if not latest_entry:
        print("No entries found in the RSS feed.")
        return

    last_entry = latest_entries.get(guild_id)

    # Check if there's a new chapter
    if not last_entry or latest_entry.link != last_entry['link']:
        latest_entries[guild_id] = {
            'title': latest_entry.title,
            'link': latest_entry.link,
        }

        channel = bot.get_channel(config['channel_id'])
        role = bot.get_guild(guild_id).get_role(config['role_id'])
        if channel and role:
            try:
                await channel.send(f"{role.mention} \nNew chapter update!\nTitle: {latest_entry.title}\nLink: [{latest_entry.title}]({latest_entry.link})")
                if ctx:
                    await ctx.send("New chapter update found and notified.")
            except discord.Forbidden:
                if ctx:
                    await ctx.send("New chapter update found but failed to notify. Please check my permissions.")
        else:
            print(f"Channel or role not found for guild ID {guild_id}")
            if ctx:
                await ctx.send("New chapter update found but failed to notify.")
    else:
        if ctx:
            await ctx.send("No new chapter update found.")

@check_for_updates.before_loop
async def before_check_for_updates():
    await bot.wait_until_ready()

bot.run(TOKEN)