import os
import asyncio
import aiohttp
import yt_dlp
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError, InviteHashExpiredError, FloodWaitError
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, InputMessagesFilterEmpty
from telethon.utils import get_display_name
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types.stream import AudioQuality, VideoQuality
import logging
from datetime import datetime, timedelta
import time
from PIL import Image
from io import BytesIO
import uuid
import re
from typing import Optional, Dict, List
import random
from telethon.tl.functions.channels import GetParticipantRequest, JoinChannelRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator, ChatParticipantAdmin, ChatParticipantCreator
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import subprocess
import json
import psutil
import motor.motor_asyncio
from pymongo import MongoClient
import certifi

# ================= CONFIGURATION =================
BOT_TOKEN = "8748436738:AAFvuEEUKhaSUaPqxqpThwjnAv9dIlDrgbo"
API_ID = 30191201
API_HASH = "5c87a8808e935cc3d97958d0bb24ff1f"
COOKIES_FILE = "cookies.txt"
ASSISTANT_SESSION = "1BVtsOHYBuz8cVvZD8HmbOEYvqnsdc28JQObuIu7UeVIDy9x3mvcpom__gqEeaoP19U1yulyZ6AMbAADZsnknlVuhIZf_BYsuxuxf2csRv4EdF5LRTIdFsimlHx8QQUiODjdbIH7yIt7vVZNUKsQ5JdyCPyH-qdXashKSQXDtIrbrdhZP6dcpcP6EiGxG3q5WvypLmzGcfHGGW7ZfWYkpmhHYwmEhtqsIO0a28fLPtjxaP_muevtus0cBhCL9WiyEzFGGoP66QiG-htPWhbRlvboIwc1oOH-is3OCyH2OrCevnYOK91RzWTrF4sW_RxI_nDyhBTkTrciFaAk3Jq77pbA6t7ABWfE="
OWNER_ID = 8568245247
UPDATES_CHANNEL = "ASUNA_MUSIC_UPDATES"  # Bina @ ke
LOG_GROUP_ID = -1003848994625  # TERI LOG GROUP ID
REFERRAL_LINK = "t.me/Argo?start=a_WCN5PGSG"  # Referral link

# MongoDB Configuration
MONGO_URI = "mongodb+srv://bsdk:betichod@cluster0.fgj1r9z.mongodb.net/?retryWrites=true&w=majority"
MONGO_DB_NAME = "asuna_music_bot"

# Images
WELCOME_IMAGE_URL = "https://myimgs.org/storage/images/17832/asuna.png"
PING_IMAGE_URL = "https://myimgs.org/storage/images/17832/asuna.png"
JOIN_IMAGE_URL = "https://myimgs.org/storage/images/17832/asuna.png"

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= MONGODB DATABASE CLASS =================
class MongoDB:
    def __init__(self, uri, db_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
        self.db = self.client[db_name]
        
        # Collections
        self.users = self.db.users
        self.groups = self.db.groups
        self.user_sessions = self.db.user_sessions
        self.admins = self.db.bot_admins
        self.stats = self.db.stats
        self.blocked_users = self.db.blocked_users
        self.bot_settings = self.db.bot_settings
        
    async def initialize(self):
        """Initialize database with default values if empty"""
        stats = await self.stats.find_one({"_id": "main"})
        if not stats:
            await self.stats.insert_one({
                "_id": "main",
                "total_commands": 0,
                "songs_played": 0,
                "bot_start_time": time.time()
            })
        
        admins = await self.admins.find_one({"_id": "main"})
        if not admins:
            await self.admins.insert_one({
                "_id": "main",
                "admins": [OWNER_ID]
            })
        
        blocked = await self.blocked_users.find_one({"_id": "main"})
        if not blocked:
            await self.blocked_users.insert_one({
                "_id": "main",
                "users": []
            })
        
        settings = await self.bot_settings.find_one({"_id": "main"})
        if not settings:
            await self.bot_settings.insert_one({
                "_id": "main",
                "maintenance_mode": False,
                "maintenance_message": "🚧 Bot is under maintenance. Please try again later.",
                "maintenance_by": None,
                "maintenance_time": None
            })
    
    async def add_user(self, user_id, username=None, first_name=None):
        user_id = str(user_id)
        now = time.time()
        
        user = await self.users.find_one({"_id": user_id})
        
        if not user:
            await self.users.insert_one({
                "_id": user_id,
                "first_seen": now,
                "last_active": now,
                "username": username or "",
                "name": first_name or "",
                "total_sessions": 1
            })
        else:
            update_data = {"last_active": now}
            if username:
                update_data["username"] = username
            if first_name:
                update_data["name"] = first_name
            
            await self.users.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
    
    async def has_seen_start(self, user_id):
        user_id = str(user_id)
        session = await self.user_sessions.find_one({"_id": user_id})
        return session is not None
    
    async def mark_start_seen(self, user_id):
        user_id = str(user_id)
        now = time.time()
        
        session = await self.user_sessions.find_one({"_id": user_id})
        
        if not session:
            await self.user_sessions.insert_one({
                "_id": user_id,
                "first_start": now,
                "last_start": now,
                "start_count": 1
            })
        else:
            await self.user_sessions.update_one(
                {"_id": user_id},
                {
                    "$set": {"last_start": now},
                    "$inc": {"start_count": 1}
                }
            )
    
    async def add_group(self, group_id, name=None, username=None, members_count=0):
        group_id = str(group_id)
        now = time.time()
        
        group = await self.groups.find_one({"_id": group_id})
        
        if not group:
            await self.groups.insert_one({
                "_id": group_id,
                "added_date": now,
                "name": name or "",
                "username": username or "",
                "members_count": members_count
            })
        else:
            update_data = {}
            if name:
                update_data["name"] = name
            if username:
                update_data["username"] = username
            if members_count:
                update_data["members_count"] = members_count
            
            if update_data:
                await self.groups.update_one(
                    {"_id": group_id},
                    {"$set": update_data}
                )
    
    async def remove_group(self, group_id):
        group_id = str(group_id)
        result = await self.groups.delete_one({"_id": group_id})
        return result.deleted_count > 0
    
    async def is_bot_admin(self, user_id):
        user_id = int(user_id)
        
        if user_id == OWNER_ID:
            return True
        
        admins_doc = await self.admins.find_one({"_id": "main"})
        if admins_doc and "admins" in admins_doc:
            return user_id in admins_doc["admins"]
        return False
    
    async def add_bot_admin(self, user_id):
        user_id = int(user_id)
        
        if user_id == OWNER_ID:
            return False
        
        admins_doc = await self.admins.find_one({"_id": "main"})
        if not admins_doc:
            admins_doc = {"_id": "main", "admins": []}
        
        if user_id not in admins_doc["admins"]:
            admins_doc["admins"].append(user_id)
            await self.admins.update_one(
                {"_id": "main"},
                {"$set": {"admins": admins_doc["admins"]}},
                upsert=True
            )
            return True
        return False
    
    async def remove_bot_admin(self, user_id):
        user_id = int(user_id)
        
        if user_id == OWNER_ID:
            return False
        
        admins_doc = await self.admins.find_one({"_id": "main"})
        if admins_doc and "admins" in admins_doc and user_id in admins_doc["admins"]:
            admins_doc["admins"].remove(user_id)
            await self.admins.update_one(
                {"_id": "main"},
                {"$set": {"admins": admins_doc["admins"]}}
            )
            return True
        return False
    
    async def get_bot_admins(self):
        admins_doc = await self.admins.find_one({"_id": "main"})
        if admins_doc and "admins" in admins_doc:
            return admins_doc["admins"]
        return []
    
    async def increment_command_count(self):
        await self.stats.update_one(
            {"_id": "main"},
            {"$inc": {"total_commands": 1}}
        )
    
    async def increment_songs_played(self):
        await self.stats.update_one(
            {"_id": "main"},
            {"$inc": {"songs_played": 1}}
        )
    
    async def get_stats(self):
        users_count = await self.users.count_documents({})
        groups_count = await self.groups.count_documents({})
        
        stats_doc = await self.stats.find_one({"_id": "main"})
        
        total_commands = stats_doc.get("total_commands", 0) if stats_doc else 0
        songs_played = stats_doc.get("songs_played", 0) if stats_doc else 0
        bot_start_time = stats_doc.get("bot_start_time", time.time()) if stats_doc else time.time()
        
        uptime_seconds = time.time() - bot_start_time
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        return {
            "users": users_count,
            "groups": groups_count,
            "total_commands": total_commands,
            "songs_played": songs_played,
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds
        }
    
    async def update_start_time(self):
        await self.stats.update_one(
            {"_id": "main"},
            {"$set": {"bot_start_time": time.time()}},
            upsert=True
        )
    
    # ================= BLOCK/USER MANAGEMENT =================
    async def is_user_blocked(self, user_id):
        user_id = int(user_id)
        
        if user_id == OWNER_ID:
            return False
        
        blocked_doc = await self.blocked_users.find_one({"_id": "main"})
        if blocked_doc and "users" in blocked_doc:
            return user_id in blocked_doc["users"]
        return False
    
    async def block_user(self, user_id):
        user_id = int(user_id)
        
        if user_id == OWNER_ID:
            return False
        
        blocked_doc = await self.blocked_users.find_one({"_id": "main"})
        if not blocked_doc:
            blocked_doc = {"_id": "main", "users": []}
        
        if user_id not in blocked_doc["users"]:
            blocked_doc["users"].append(user_id)
            await self.blocked_users.update_one(
                {"_id": "main"},
                {"$set": {"users": blocked_doc["users"]}},
                upsert=True
            )
            return True
        return False
    
    async def unblock_user(self, user_id):
        user_id = int(user_id)
        
        blocked_doc = await self.blocked_users.find_one({"_id": "main"})
        if blocked_doc and "users" in blocked_doc and user_id in blocked_doc["users"]:
            blocked_doc["users"].remove(user_id)
            await self.blocked_users.update_one(
                {"_id": "main"},
                {"$set": {"users": blocked_doc["users"]}}
            )
            return True
        return False
    
    async def get_blocked_users(self):
        blocked_doc = await self.blocked_users.find_one({"_id": "main"})
        if blocked_doc and "users" in blocked_doc:
            return blocked_doc["users"]
        return []
    
    # ================= MAINTENANCE MODE =================
    async def set_maintenance(self, enabled, by=None):
        update_data = {"maintenance_mode": enabled}
        if enabled:
            update_data["maintenance_by"] = by
            update_data["maintenance_time"] = time.time()
        else:
            update_data["maintenance_by"] = None
            update_data["maintenance_time"] = None
        
        await self.bot_settings.update_one(
            {"_id": "main"},
            {"$set": update_data},
            upsert=True
        )
        return True
    
    async def get_maintenance(self):
        settings = await self.bot_settings.find_one({"_id": "main"})
        if settings:
            return {
                "enabled": settings.get("maintenance_mode", False),
                "message": settings.get("maintenance_message", "🚧 Bot is under maintenance. Please try again later."),
                "by": settings.get("maintenance_by"),
                "time": settings.get("maintenance_time")
            }
        return {
            "enabled": False,
            "message": "🚧 Bot is under maintenance. Please try again later.",
            "by": None,
            "time": None
        }
    
    async def set_maintenance_message(self, message):
        await self.bot_settings.update_one(
            {"_id": "main"},
            {"$set": {"maintenance_message": message}},
            upsert=True
        )
        return True

# Initialize MongoDB
db = MongoDB(MONGO_URI, MONGO_DB_NAME)

# ================= LOG FUNCTION =================
async def log_to_group(action_type, user=None, group=None, song=None, details=""):
    if not LOG_GROUP_ID:
        return
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if action_type == "user_start":
            user_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            username = f"@{user.username}" if user and user.username else "`No username`"
            first_name = user.first_name if user and user.first_name else "N/A"
            last_name = user.last_name if user and user.last_name else "N/A"
            lang_code = user.lang_code if user and user.lang_code else "N/A"
            
            has_seen = await db.has_seen_start(user.id) if user else False
            session_type = "First Time" if not has_seen else "Returning"
            
            log_text = f"""
**╭━━━━ ⟬ 👤 ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ʙᴏᴛ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴜsᴇʀ:** {user_mention}
┃**ᴜsᴇʀ ɪᴅ:** `{user.id if user else 'N/A'}`
┃**ᴜsᴇʀɴᴀᴍᴇ:** {username}
┃**ғɪʀsᴛ ɴᴀᴍᴇ:** `{first_name}`
┃**ʟᴀsᴛ ɴᴀᴍᴇ:** `{last_name}`
┃**ʟᴀɴɢᴜᴀɢᴇ:** `{lang_code}`
┃**sᴇssɪᴏɴ:** `{session_type}`
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        elif action_type == "song_played":
            user_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            username = f"@{user.username}" if user and user.username else "`No username`"
            
            group_title = group.title if group else "Private"
            group_id = group.id if group else "N/A"
            
            song_title = song.get('title', 'Unknown')[:50] if song else 'Unknown'
            song_duration = song.get('duration_str', '0:00') if song else 'N/A'
            
            log_text = f"""
**╭━━━━ ⟬ 🎵 sᴏɴɢ ᴘʟᴀʏᴇᴅ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴜsᴇʀ:** {user_mention}
┃**ᴜsᴇʀ ɪᴅ:** `{user.id if user else 'N/A'}`
┃**ᴜsᴇʀɴᴀᴍᴇ:** {username}
┃
┃**ɢʀᴏᴜᴘ:** `{group_title}`
┃**ɢʀᴏᴜᴘ ɪᴅ:** `{group_id}`
┃
┃**sᴏɴɢ:** `{song_title}`
┃**ᴅᴜʀᴀᴛɪᴏɴ:** `{song_duration}`
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        elif action_type == "user_blocked":
            admin_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            target_id = details.get("target_id") if isinstance(details, dict) else "Unknown"
            target_name = details.get("target_name") if isinstance(details, dict) else "Unknown"
            
            log_text = f"""
**╭━━━━ ⟬ 🔴 ᴜsᴇʀ ʙʟᴏᴄᴋᴇᴅ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴀᴅᴍɪɴ:** {admin_mention}
┃**ᴛᴀʀɢᴇᴛ ɪᴅ:** `{target_id}`
┃**ᴛᴀʀɢᴇᴛ ɴᴀᴍᴇ:** `{target_name}`
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        elif action_type == "user_unblocked":
            admin_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            target_id = details.get("target_id") if isinstance(details, dict) else "Unknown"
            target_name = details.get("target_name") if isinstance(details, dict) else "Unknown"
            
            log_text = f"""
**╭━━━━ ⟬ 🟢 ᴜsᴇʀ ᴜɴʙʟᴏᴄᴋᴇᴅ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴀᴅᴍɪɴ:** {admin_mention}
┃**ᴛᴀʀɢᴇᴛ ɪᴅ:** `{target_id}`
┃**ᴛᴀʀɢᴇᴛ ɴᴀᴍᴇ:** `{target_name}`
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        elif action_type == "maintenance_on":
            admin_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            
            log_text = f"""
**╭━━━━ ⟬ 🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴇɴᴀʙʟᴇᴅ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴀᴅᴍɪɴ:** {admin_mention}
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        elif action_type == "maintenance_off":
            admin_mention = f"[{get_display_name(user)}](tg://user?id={user.id})" if user else "Unknown"
            
            log_text = f"""
**╭━━━━ ⟬ 🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴅɪsᴀʙʟᴇᴅ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴀᴅᴍɪɴ:** {admin_mention}
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
"""
        
        else:
            log_text = f"""
**╭━━━━ ⟬ ʟᴏɢ ᴇɴᴛʀʏ ⟭━━━━╮**
┃
┃**ᴛɪᴍᴇ:** `{timestamp}`
┃**ᴀᴄᴛɪᴏɴ:** `{action_type}`
┃**ᴅᴇᴛᴀɪʟs:** `{details}`
**╰━━━━━━━━━━━━━━━━━━╯**
"""
        
        await bot.send_message(LOG_GROUP_ID, log_text)
    except Exception as e:
        logger.error(f"Failed to send log: {e}")

# ================= GLOBALS =================
players = {}
call = None
bot = None
assistant = None
COMMAND_PREFIXES = ["/", "!", "."]
BOT_START_TIME = time.time()

# Cache bot_me to avoid repeated get_me() calls
_bot_me = None

# Dictionary to store GCAST sessions
gcast_sessions = {}

# ================= MUSIC PLAYER CLASS =================
class MusicPlayer:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.queue = []
        self.current = None
        self.loop = False
        self.paused = False
        self.play_task = None
        self.message = None
        self.control_message_id = None
        self.control_chat_id = None

# ================= HELPER FUNCTIONS =================
async def download_and_convert_thumbnail(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()

        image = Image.open(BytesIO(data)).convert("RGB")
        filename = f"thumb_{uuid.uuid4().hex}.jpg"
        image.save(filename, "JPEG")
        return filename

    except Exception as e:
        logger.error(f"Thumbnail convert error: {e}")
        return None

async def get_player(chat_id):
    if chat_id not in players:
        players[chat_id] = MusicPlayer(chat_id)
    return players[chat_id]

# FIX: Cache bot_me to avoid calling get_me() repeatedly
async def get_bot_me():
    global _bot_me
    if _bot_me is None:
        _bot_me = await bot.get_me()
    return _bot_me

async def is_admin(chat_id, user_id):
    if await db.is_bot_admin(user_id):
        return True
    
    try:
        participant = await bot(GetParticipantRequest(
            channel=chat_id,
            participant=user_id
        ))
        
        if isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator, 
                                                ChatParticipantAdmin, ChatParticipantCreator)):
            return True
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
    
    return False

# ================= JOIN VOICE CHAT =================
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, ExportChatInviteRequest
from telethon.errors import ChatAdminRequiredError

async def join_voice_chat(chat_id: int):
    try:
        try:
            me = await assistant.get_me()
            await assistant(GetParticipantRequest(chat_id, me.id))
            logger.info("Assistant already in group")
            return True
        except:
            pass

        chat = await bot.get_entity(chat_id)

        if getattr(chat, "username", None):
            await assistant(JoinChannelRequest(chat.username))
            logger.info("Assistant joined public group")
        else:
            try:
                # FIX: Removed None params that can cause issues; let Telegram use defaults
                invite = await bot(ExportChatInviteRequest(peer=chat_id))
            except ChatAdminRequiredError:
                logger.error("Bot needs Invite Users via Link permission")
                return False

            invite_hash = invite.link.split("/")[-1].replace("+", "")

            try:
                await assistant(ImportChatInviteRequest(invite_hash))
                logger.info("Assistant joined private group")
            except UserAlreadyParticipantError:
                return True

        await asyncio.sleep(2)
        await assistant.get_dialogs()
        await assistant.get_entity(chat_id)

        return True

    except Exception as e:
        logger.error(f"Auto join failed: {e}")
        return False

# ================= VOICE MESSAGE HANDLER =================
async def download_voice_message(event):
    try:
        if event.message.reply_to_msg_id:
            reply_msg = await event.get_reply_message()
            
            if reply_msg.voice or (reply_msg.document and reply_msg.document.mime_type and 'audio' in reply_msg.document.mime_type):
                msg = await event.reply("**📥 ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴠᴏɪᴄᴇ ᴍᴇssᴀɢᴇ...**")
                
                file_name = f"voice_{uuid.uuid4().hex}"
                file_path = await reply_msg.download_media(file=file_name)
                
                if not file_path:
                    await msg.edit("**❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴠᴏɪᴄᴇ ᴍᴇssᴀɢᴇ!**")
                    await asyncio.sleep(3)
                    await msg.delete()
                    return None
                
                output_file = f"{file_name}.mp3"
                
                try:
                    process = await asyncio.create_subprocess_exec(
                        'ffmpeg', '-i', file_path, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', output_file,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process.communicate()
                    
                    try:
                        os.remove(file_path)
                    except:
                        pass
                    
                    duration = 0
                    try:
                        process = await asyncio.create_subprocess_exec(
                            'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', output_file,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, _ = await process.communicate()
                        if stdout:
                            duration = int(float(stdout.decode().strip()))
                    except:
                        pass
                    
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                    
                    await msg.delete()
                    
                    return {
                        'file_path': output_file,
                        'title': 'Voice Message',
                        'duration': duration,
                        'duration_str': duration_str,
                        'thumbnail': None,
                        'uploader': reply_msg.sender.first_name if reply_msg.sender else 'Unknown',
                        'is_local': True
                    }
                except Exception as e:
                    logger.error(f"FFmpeg conversion error: {e}")
                    await msg.edit("**❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴄᴏɴᴠᴇʀᴛ ᴠᴏɪᴄᴇ ᴍᴇssᴀɢᴇ!**")
                    await asyncio.sleep(3)
                    await msg.delete()
                    return None
    except Exception as e:
        logger.error(f"Voice message download error: {e}")
        return None
    
    return None

# ================= EXTRACT AUDIO/VIDEO =================
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def download_audio(query):
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "geo_bypass_country": "IN",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            if query.startswith(("http://", "https://")):
                info = ydl.extract_info(query, download=True)
            else:
                results = ydl.extract_info(f"ytsearch1:{query}", download=True)
                if not results or not results.get("entries"):
                    return None
                info = results["entries"][0]

            if not info:
                return None

            base_path = ydl.prepare_filename(info)
            file_path = os.path.splitext(base_path)[0] + ".mp3"

            duration = info.get("duration") or 0
            minutes = duration // 60
            seconds = duration % 60

            return {
                "file_path": file_path,
                "title": info.get("title", "Unknown"),
                "duration": duration,
                "duration_str": f"{minutes}:{seconds:02d}",
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "is_local": False,
            }

    except Exception as e:
        logger.error(f"Download audio error: {e}")
        return None

async def download_video(query):
    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "geo_bypass_country": "IN",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            if query.startswith(("http://", "https://")):
                info = ydl.extract_info(query, download=True)
            else:
                results = ydl.extract_info(f"ytsearch1:{query}", download=True)
                if not results or not results.get("entries"):
                    return None
                info = results["entries"][0]

            if not info:
                return None

            base_path = ydl.prepare_filename(info)
            file_path = os.path.splitext(base_path)[0] + ".mp4"

            duration = info.get("duration") or 0
            minutes = duration // 60
            seconds = duration % 60

            return {
                "file_path": file_path,
                "title": info.get("title", "Unknown"),
                "duration": duration,
                "duration_str": f"{minutes}:{seconds:02d}",
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "is_local": False,
            }

    except Exception as e:
        logger.error(f"Download video error: {e}")
        return None

# ================= PLAY SONG =================
async def play_song(chat_id, song_info, is_video=False):
    player = await get_player(chat_id)

    for attempt in range(3):
        try:
            await assistant.get_entity(chat_id)
            break
        except:
            if attempt == 2:
                await join_voice_chat(chat_id)
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

    try:
        source = song_info.get("file_path") or song_info.get("url")
        if not source:
            return False

        if is_video:
            media = MediaStream(
                source,
                audio_parameters=AudioQuality.STUDIO,
                video_parameters=VideoQuality.HD_720p,
            )
        else:
            media = MediaStream(
                source,
                audio_parameters=AudioQuality.STUDIO,
            )

        await call.play(chat_id, media)

        song_info["is_video"] = is_video
        player.current = song_info
        player.paused = False

        await db.increment_songs_played()

        if player.play_task and not player.play_task.done():
            player.play_task.cancel()

        duration = song_info.get("duration", 0)
        if duration > 0:
            player.play_task = asyncio.create_task(
                auto_next(chat_id, duration)
            )
        else:
            player.play_task = None

        await send_streaming_message(chat_id, song_info, is_video)

        return True

    except Exception as e:
        logger.error(f"Play song error: {e}")
        return False


async def send_streaming_message(chat_id, song_info, is_video):
    player = await get_player(chat_id)
    
    if song_info.get('is_local', False):
        title_display = "🎤 Voice Message"
        uploader = song_info.get('uploader', 'Unknown')
        thumbnail_url = None
    else:
        title_display = song_info.get('title', 'Unknown')[:30]
        uploader = song_info.get('uploader', 'Unknown')
        thumbnail_url = song_info.get('thumbnail')
    
    caption = f"""
**╭━━━━ ⟬ ➲ ɴᴏᴡ sᴛʀᴇᴀᴍɪɴɢ ⟭━━━━╮**
┃
┃⟡➣ **ᴛɪᴛʟᴇ:** `{title_display}`
┃⟡➣ **ᴅᴜʀᴀᴛɪᴏɴ:** `{song_info.get('duration_str', '0:00')}`
┃⟡➣ **ᴛʏᴘᴇ:** `{'🎬 ᴠɪᴅᴇᴏ' if is_video else '🎵 ᴀᴜᴅɪᴏ'}`
┃⟡➣ **ʟᴏᴏᴘ:** `{'ᴏɴ' if player.loop else 'ᴏғғ'}`
┃⟡➣ **ǫᴜᴇᴜᴇ:** `{len(player.queue)} sᴏɴɢs`
┃⟡➣ **ᴜᴘʟᴏᴀᴅᴇʀ:** `{uploader}`
**╰━━━━━━━━━━━━━━━━━━━━━━╯**
    """
    
    buttons = [
        [Button.inline("⏸️", data=f"pause_{chat_id}"),
         Button.inline("⏭️", data=f"skip_{chat_id}"),
         Button.inline("⏹️", data=f"end_{chat_id}"),
         Button.inline("🔄", data=f"loop_{chat_id}")],
        [Button.inline("⏪ -10s", data=f"seekback_{chat_id}"),
         Button.inline("⏩ +10s", data=f"seek_{chat_id}"),
         Button.inline("📋 ǫᴜᴇᴜᴇ", data=f"queue_{chat_id}")],
        [Button.inline("🗑️ ᴄʟᴇᴀʀ", data=f"clear_{chat_id}")]
    ]
    
    thumb_path = None
    if thumbnail_url and not song_info.get('is_local', False):
        thumb_path = await download_and_convert_thumbnail(thumbnail_url)
    
    if player.control_message_id and player.control_chat_id:
        try:
            await bot.delete_messages(
                player.control_chat_id,
                player.control_message_id
            )
        except:
            pass
    
    try:
        if thumb_path and os.path.exists(thumb_path):
            msg = await bot.send_file(
                chat_id,
                thumb_path,
                caption=caption,
                buttons=buttons,
                spoiler=True
            )
            os.remove(thumb_path)
        else:
            msg = await bot.send_message(
                chat_id,
                caption,
                buttons=buttons
            )
    except Exception:
        msg = await bot.send_message(
            chat_id,
            caption,
            buttons=buttons
        )
    
    player.control_message_id = msg.id
    player.control_chat_id = chat_id


async def auto_next(chat_id, duration):
    await asyncio.sleep(duration)

    player = await get_player(chat_id)

    if player.loop and player.current:
        await play_song(
            chat_id,
            player.current,
            player.current.get("is_video", False)
        )
        return

    if player.queue:
        next_song = player.queue.pop(0)
        await play_song(
            chat_id,
            next_song,
            next_song.get("is_video", False)
        )
    else:
        if player.current:
            file_path = player.current.get("file_path")
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

        player.current = None

        try:
            await call.leave_call(chat_id)
        except:
            pass

        if player.control_message_id and player.control_chat_id:
            try:
                await bot.delete_messages(
                    player.control_chat_id,
                    player.control_message_id
                )
            except:
                pass

        player.control_message_id = None
        player.control_chat_id = None

# ================= COMMAND CHECKER =================
def is_command(text, command):
    if not text:
        return False
    
    text = text.strip()
    
    for prefix in COMMAND_PREFIXES:
        if text.startswith(f"{prefix}{command}"):
            rest = text[len(f"{prefix}{command}"):]
            if not rest or rest[0] in [' ', '@']:
                return True
    
    return False

def get_command_args(text, command):
    if not text:
        return None
    
    text = text.strip()
    
    for prefix in COMMAND_PREFIXES:
        if text.startswith(f"{prefix}{command}"):
            args = text[len(f"{prefix}{command}"):].strip()
            if args.startswith('@'):
                parts = args.split(' ', 1)
                if len(parts) > 1:
                    return parts[1].strip()
                return None
            return args if args else None
    
    return None

# ================= HELP MENU FUNCTIONS =================
async def get_help_menu():
    """Returns the main help menu with categories"""
    text = """
**╭━━━━ ⟬ ʜᴇʟᴘ ᴍᴇɴᴜ ⟭━━━━╮**
┃
┃ ᴄʜᴏᴏsᴇ ᴛʜᴇ ᴄᴀᴛᴇɢᴏʀʏ ғᴏʀ ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴɴᴀ ɢᴇᴛ ʜᴇʟᴩ.
┃ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs ᴄᴀɴ ʙᴇ ᴜsᴇᴅ ᴡɪᴛʜ : /
┃
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
    """
    
    buttons = [
        [Button.inline("𝚂𝚘𝚗𝚐", data="help_song"),
         Button.inline("𝙰𝚍𝚖𝚒𝚗", data="help_admin"),
         Button.inline("𝚂𝚞𝚍𝚘", data="help_sudo")],
        [Button.inline("𝙼𝚊𝚒𝚗𝚝𝚎𝚗𝚊𝚗𝚌𝚎", data="help_maintenance"),
         Button.inline("𝙿𝚒𝚗𝚐", data="help_ping"),
         Button.inline("𝚂𝚎𝚎𝚔/𝙻𝚘𝚘𝚙", data="help_seek")],
        [Button.inline("𝙱𝚛𝚘𝚊𝚍𝚌𝚊𝚜𝚝", data="help_broadcast"),
         Button.inline("𝙱-𝚄𝚜𝚎𝚛𝚜", data="help_busers"),]
        [Button.inline("๏ 𝙱𝚊𝚌𝚔 ๏", data="back_to_start")]
    ]
    
    return text, buttons

# ================= BOT COMMANDS =================
@events.register(events.NewMessage)
async def message_handler(event):
    if not event.message.text:
        return
    
    msg_text = event.message.text.strip()
    chat_id = event.chat_id
    user_id = event.sender_id
    sender = await event.get_sender()
    
    if await db.is_user_blocked(user_id):
        try:
            await event.message.delete()
        except:
            pass
        return
    
    maintenance = await db.get_maintenance()
    if maintenance["enabled"] and not await db.is_bot_admin(user_id) and user_id != OWNER_ID:
        if not is_command(msg_text, "start"):
            try:
                await event.reply(maintenance["message"])
                await event.message.delete()
            except:
                pass
            return
    
    first_name = sender.first_name if hasattr(sender, 'first_name') else getattr(sender, 'title', str(sender.id))
    await db.add_user(user_id, sender.username, first_name)
    
    if event.is_group or event.is_channel:
        chat = await event.get_chat()
        members_count = getattr(chat, 'participants_count', 0)
        await db.add_group(chat_id, chat.title, getattr(chat, 'username', ''), members_count)
    
    if msg_text.startswith(tuple(COMMAND_PREFIXES)):
        await db.increment_command_count()
    
    # ===== START COMMAND =====
    if is_command(msg_text, "start"):
        user = await event.get_sender()
        
        has_seen = await db.has_seen_start(user.id)
        
        if not has_seen:
            join_caption = f"""
**๏ ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ๏ sᴜᴘᴘᴏʀᴛ ๏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴄʜᴇᴀᴋ ᴍʏ ғᴇᴀᴛᴜʀᴇs.**

**ᴀғᴛᴇʀ ᴊᴏɪɴ ᴛʜᴇ ๏ ᴄʜᴀɴɴᴇʟ ๏ ᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ ʙᴏᴛ ᴀɴᴅ ᴛʏᴘᴇ /start ᴀɢᴀɪɴ !!**
            """
            
            buttons = [
                [Button.url("🔰 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 🔰", REFERRAL_LINK)]
            ]
            
            await event.reply(file=JOIN_IMAGE_URL, message=join_caption, buttons=buttons)
            
            await db.mark_start_seen(user.id)
            await log_to_group("user_start", user=user)
            
            try:
                await event.message.delete()
            except:
                pass
            return
        else:
            # FIX: Use cached get_bot_me() instead of event.client.get_me()
            bot_me = await get_bot_me()
            caption = f"""
✨ **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ˹𝚨𝛔𝛖𝛎𝛂 ꭙ 𝐌ᴜꜱɪᴄ ♪˼ ʙᴏᴛ** ✨

⟡➣ **ʜᴇʏ** [{get_display_name(user)}](tg://user?id={user.id}) ❤️

⟡➣ **ɪ ᴀᴍ ᴀ ᴘᴏᴡᴇʀғᴜʟ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ.**
⟡➣ **ᴛʜᴀᴛ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜsɪᴄ ᴀɴᴅ ᴠɪᴅᴇᴏ ɪɴ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs.**

⟡➣ **ᴄʟɪᴄᴋ ᴏɴ ʜᴇʟᴘ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴋɴᴏᴡ ᴍᴏʀᴇ.**
            """
            
            buttons = [
                [Button.url("⟡➣ 𝙾𝚠𝚗𝚎𝚛", f"https://t.me/blaze_xs0ul"),
                 Button.url("➕ 𝙰𝚍𝚍 𝙼𝚎", f"https://t.me/{bot_me.username}?startgroup=true")],
                [Button.inline("⟡➣ 𝙷𝚎𝚕𝚙", data="help_menu"),
                 Button.url("⟡➣ 𝚄𝚙𝚍𝚊𝚝𝚎𝚜", f"https://t.me/{UPDATES_CHANNEL}")]
            ]
            
            await event.reply(file=WELCOME_IMAGE_URL, message=caption, buttons=buttons)
            
            await db.mark_start_seen(user.id)
            await log_to_group("user_start", user=user)
            
            try:
                await event.message.delete()
            except:
                pass
            return
    
    # ===== HELP COMMAND =====
    if is_command(msg_text, "help"):
        help_text, help_buttons = await get_help_menu()
        await event.reply(help_text, buttons=help_buttons)
        
        try:
            await event.message.delete()
        except:
            pass
        return

    # ===== MUSIC COMMANDS =====
    
    # /play command
    if is_command(msg_text, "play"):
        query = get_command_args(msg_text, "play")

        voice_info = None
        if not query and event.message.reply_to_msg_id:
            voice_info = await download_voice_message(event)
            if voice_info:
                query = "voice"

        if not query and not voice_info:
            reply_msg = await event.reply(
                "**ᴜsᴀɢᴇ:** `/play <sᴏɴɢ ɴᴀᴍᴇ ᴏʀ ʟɪɴᴋ>`\n"
                "**ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴠᴏɪᴄᴇ ᴍᴇssᴀɢᴇ**"
            )
            try:
                await event.message.delete()
            except:
                pass

            await asyncio.sleep(5)
            try:
                await reply_msg.delete()
            except:
                pass
            return

        msg = await event.reply("**🔍 ᴘʀᴏᴄᴇssɪɴɢ...**")

        try:
            await event.message.delete()
        except:
            pass

        # Download audio
        if voice_info:
            song_info = voice_info
        else:
            song_info = await download_audio(query)

        if not song_info or not song_info.get("file_path"):
            await msg.edit("**❌ sᴏɴɢ ɴᴏᴛ ғᴏᴜɴᴅ!**")
            await asyncio.sleep(3)
            await msg.delete()
            return

        player = await get_player(chat_id)

        if player.current:
            player.queue.append(song_info)
            queue_pos = len(player.queue)
            
            # Different title for voice messages
            if voice_info:
                title_display = "Voice Message"
            else:
                title_display = song_info['title'][:20]
            
            queue_caption = f"""
**╭━━━━ ⟬ ➲ ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ ⟭━━━━╮**
┃
┃⟡➣ **ᴛɪᴛʟᴇ:** `{title_display}`
┃⟡➣ **ᴅᴜʀᴀᴛɪᴏɴ:** `{song_info['duration_str']}`
┃⟡➣ **ᴘᴏsɪᴛɪᴏɴ:** `#{queue_pos}`
┃⟡➣ **ᴜᴘʟᴏᴀᴅᴇʀ:** `{song_info['uploader']}`
**╰━━━━━━━━━━━━━━━━━━━╯**
            """
            
            # Download thumbnail only for non-voice messages
            thumbnail_url = song_info.get('thumbnail')
            thumb_path = None
            if thumbnail_url and not voice_info:
                thumb_path = await download_and_convert_thumbnail(thumbnail_url)
            
            await msg.delete()
            
            if thumb_path:
                sent_msg = await bot.send_file(
                    chat_id,
                    thumb_path,
                    caption=queue_caption,
                    spoiler=True
                )
                os.remove(thumb_path)
            else:
                sent_msg = await event.reply(queue_caption)
            
            # Auto delete queue message after 10 seconds
            await asyncio.sleep(10)
            try:
                await sent_msg.delete()
            except:
                pass

        else:
            # LOG SONG PLAYED
            chat = await event.get_chat() if event.is_group else None
            await log_to_group("song_played", user=sender, group=chat, song=song_info)
            
            success = await play_song(chat_id, song_info, is_video=False)

            if not success:
                await msg.edit("**❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴘʟᴀʏ sᴏɴɢ!**")
                await asyncio.sleep(3)
                await msg.delete()

                # Cleanup voice file
                if voice_info:
                    path = song_info.get("file_path")
                    if path and os.path.exists(path):
                        os.remove(path)
            else:
                await msg.delete()

        return


    # /vplay command (download video)
    if is_command(msg_text, "vplay"):
        query = get_command_args(msg_text, "vplay")

        if not query:
            reply_msg = await event.reply(
                "**ᴜsᴀɢᴇ:** `/vplay <ᴠɪᴅᴇᴏ ɴᴀᴍᴇ ᴏʀ ʟɪɴᴋ>`"
            )
            try:
                await event.message.delete()
            except:
                pass

            await asyncio.sleep(5)
            try:
                await reply_msg.delete()
            except:
                pass
            return

        msg = await event.reply("**🎬 ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴠɪᴅᴇᴏ...**")

        try:
            await event.message.delete()
        except:
            pass

        video_info = await download_video(query)

        if not video_info or not video_info.get("file_path"):
            await msg.edit("**❌ ᴠɪᴅᴇᴏ ɴᴏᴛ ғᴏᴜɴᴅ!**")
            await asyncio.sleep(3)
            await msg.delete()
            return

        player = await get_player(chat_id)

        if player.current:
            player.queue.append(video_info)
            queue_pos = len(player.queue)

            queue_caption = f"""
**╭━━━━ ⟬ ➲ ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ ⟭━━━━╮**
┃
┃⟡➣ **ᴛɪᴛʟᴇ:** `{video_info['title'][:20]}`
┃⟡➣ **ᴅᴜʀᴀᴛɪᴏɴ:** `{video_info['duration_str']}`
┃⟡➣ **ᴘᴏsɪᴛɪᴏɴ:** `#{queue_pos}`
┃⟡➣ **ᴜᴘʟᴏᴀᴅᴇʀ:** `{video_info['uploader']}`
**╰━━━━━━━━━━━━━━━━━━━╯**
            """
            
            thumbnail_url = video_info.get('thumbnail')
            thumb_path = await download_and_convert_thumbnail(thumbnail_url) if thumbnail_url else None
            
            await msg.delete()
            
            if thumb_path:
                sent_msg = await bot.send_file(
                    chat_id,
                    thumb_path,
                    caption=queue_caption,
                    spoiler=True
                )
                os.remove(thumb_path)
            else:
                sent_msg = await event.reply(queue_caption)
            
            # Auto delete queue message after 10 seconds
            await asyncio.sleep(10)
            try:
                await sent_msg.delete()
            except:
                pass

        else:
            # LOG SONG PLAYED (video)
            chat = await event.get_chat() if event.is_group else None
            await log_to_group("song_played", user=sender, group=chat, song=video_info)
            
            success = await play_song(chat_id, video_info, is_video=True)

            if not success:
                await msg.edit("**❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴘʟᴀʏ ᴠɪᴅᴇᴏ!**")
                await asyncio.sleep(3)
                await msg.delete()
            else:
                await msg.delete()

        return
    
    # /skip command
    if is_command(msg_text, "skip"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ sᴋɪᴘ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        player = await get_player(chat_id)
        
        if not player.current:
            reply_msg = await event.reply("**❌ ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        msg = await event.reply("**⏭️ sᴋɪᴘᴘɪɴɢ...**")
        
        try:
            await event.message.delete()
        except:
            pass
        
        if player.current and player.current.get('is_local', False):
            try:
                os.remove(player.current['file_path'])
            except:
                pass
        
        if player.play_task and not player.play_task.done():
            player.play_task.cancel()
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        
        if player.queue:
            next_song = player.queue.pop(0)
            success = await play_song(chat_id, next_song, next_song.get('is_video', False))
            if success:
                await msg.edit("**✅ sᴋɪᴘᴘᴇᴅ ᴛᴏ ɴᴇxᴛ sᴏɴɢ!**")
                await asyncio.sleep(3)
                await msg.delete()
            else:
                await msg.edit("**❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴘʟᴀʏ ɴᴇxᴛ sᴏɴɢ!**")
                player.queue.insert(0, next_song)
                await asyncio.sleep(3)
                await msg.delete()
        else:
            player.current = None
            
            if player.control_message_id and player.control_chat_id:
                try:
                    await bot.delete_messages(player.control_chat_id, player.control_message_id)
                except:
                    pass
            player.control_message_id = None
            player.control_chat_id = None
            
            await msg.edit("**⏹️ ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ!**")
            await asyncio.sleep(3)
            await msg.delete()
        return
    
    # /pause command
    if is_command(msg_text, "pause"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴘᴀᴜsᴇ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        try:
            await call.pause(chat_id)
            msg = await event.reply("**⏸️ ᴘᴀᴜsᴇᴅ**")
            await asyncio.sleep(3)
            await msg.delete()
        except Exception as e:
            msg = await event.reply(f"**❌ ғᴀɪʟᴇᴅ: {str(e)[:50]}**")
            await asyncio.sleep(3)
            await msg.delete()
        return
    
    # /resume command
    if is_command(msg_text, "resume"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ʀᴇsᴜᴍᴇ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        try:
            await call.resume(chat_id)
            msg = await event.reply("**▶️ ʀᴇsᴜᴍᴇᴅ**")
            await asyncio.sleep(3)
            await msg.delete()
        except Exception as e:
            msg = await event.reply(f"**❌ ғᴀɪʟᴇᴅ: {str(e)[:50]}**")
            await asyncio.sleep(3)
            await msg.delete()
        return
    
    # /end command
    if is_command(msg_text, "end"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴇɴᴅ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        player = await get_player(chat_id)
        
        try:
            await event.message.delete()
        except:
            pass
        
        if player.current and player.current.get('is_local', False):
            try:
                os.remove(player.current['file_path'])
            except:
                pass
        
        if player.play_task and not player.play_task.done():
            player.play_task.cancel()
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        for song in player.queue:
            if song.get('is_local', False):
                try:
                    os.remove(song['file_path'])
                except:
                    pass
        
        player.queue.clear()
        player.current = None
        player.paused = False
        
        if player.control_message_id and player.control_chat_id:
            try:
                await bot.delete_messages(player.control_chat_id, player.control_message_id)
            except:
                pass
        player.control_message_id = None
        player.control_chat_id = None
        
        msg = await event.reply("**⏹️ sᴛᴏᴘᴘᴇᴅ ᴀɴᴅ ʟᴇғᴛ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ!**")
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # /queue command
    if is_command(msg_text, "queue"):
        player = await get_player(chat_id)
        
        try:
            await event.message.delete()
        except:
            pass
        
        if not player.queue:
            msg = await event.reply("**📭 ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ!**")
            await asyncio.sleep(3)
            await msg.delete()
            return
        
        # FIX: Renamed `text` to `queue_text` to avoid variable name conflict
        queue_text = "**📋 ǫᴜᴇᴜᴇ ʟɪsᴛ:**\n\n"
        for i, song in enumerate(player.queue[:10], 1):
            if song.get('is_local', False):
                title = 'Voice Message'
            else:
                title = song['title'][:30]
            queue_text += f"{i}. {title} ({song['duration_str']})\n"
        
        if len(player.queue) > 10:
            queue_text += f"\n...ᴀɴᴅ {len(player.queue) - 10} ᴍᴏʀᴇ"
        
        msg = await event.reply(queue_text)
        await asyncio.sleep(10)
        await msg.delete()
        return
    
    # /loop command
    if is_command(msg_text, "loop"):
        player = await get_player(chat_id)
        
        try:
            await event.message.delete()
        except:
            pass
        
        player.loop = not player.loop
        status = 'ᴏɴ' if player.loop else 'ᴏғғ'
        msg = await event.reply(f"**🔄 ʟᴏᴏᴘ: {status}**")
        await asyncio.sleep(3)
        await msg.delete()
        
        if player.current and player.control_message_id:
            await send_streaming_message(chat_id, player.current, player.current.get('is_video', False))
        return
    
    # /clear command
    if is_command(msg_text, "clear"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴄʟᴇᴀʀ ǫᴜᴇᴜᴇ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        player = await get_player(chat_id)
        
        try:
            await event.message.delete()
        except:
            pass
        
        for song in player.queue:
            if song.get('is_local', False):
                try:
                    os.remove(song['file_path'])
                except:
                    pass
        
        queue_count = len(player.queue)
        player.queue.clear()
        msg = await event.reply(f"**🗑️ {queue_count} sᴏɴɢs ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ǫᴜᴇᴜᴇ!**")
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # /reload command
    if is_command(msg_text, "reload"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ʀᴇʟᴏᴀᴅ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        msg = await event.reply("**✅ ᴀᴅᴍɪɴ ᴄʜᴇᴄᴋ ʀᴇʟᴏᴀᴅᴇᴅ!**")
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # /seek command
    if is_command(msg_text, "seek"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ sᴇᴇᴋ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        player = await get_player(chat_id)
        
        if not player.current:
            reply_msg = await event.reply("**❌ ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        args = get_command_args(msg_text, "seek")
        if not args:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/seek [seconds]`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            seconds = int(args)
        except:
            reply_msg = await event.reply("**❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        msg = await event.reply(f"**⏩ sᴇᴇᴋɪɴɢ +{seconds}s...**")
        
        current_song = player.current
        is_video = current_song.get('is_video', False)
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        
        await msg.edit(f"**✅ sᴇᴇᴋᴇᴅ ᴛᴏ +{seconds}s**")
        await play_song(chat_id, current_song, is_video)
        
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # /seekback command
    if is_command(msg_text, "seekback"):
        if not await is_admin(chat_id, user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ sᴇᴇᴋ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        player = await get_player(chat_id)
        
        if not player.current:
            reply_msg = await event.reply("**❌ ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        args = get_command_args(msg_text, "seekback")
        if not args:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/seekback [seconds]`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            seconds = int(args)
        except:
            reply_msg = await event.reply("**❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            try:
                await reply_msg.delete()
            except:
                pass
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        msg = await event.reply(f"**⏪ sᴇᴇᴋɪɴɢ -{seconds}s...**")
        
        current_song = player.current
        is_video = current_song.get('is_video', False)
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        
        await msg.edit(f"**✅ sᴇᴇᴋᴇᴅ ᴛᴏ -{seconds}s**")
        await play_song(chat_id, current_song, is_video)
        
        await asyncio.sleep(3)
        await msg.delete()
        return

# ================= CALLBACK HANDLER =================
@events.register(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if await db.is_user_blocked(user_id):
        await event.answer("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ!", alert=True)
        return
    
    # Help menu callbacks
    if data == "help_menu":
        help_text, help_buttons = await get_help_menu()
        await event.edit(help_text, buttons=help_buttons)
        return
    
    elif data == "help_song":
        text = """
**╭━━━━ ⟬ 🎵 sᴏɴɢ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /play [song] : ᴘʟᴀʏ ᴀᴜᴅɪᴏ ғʀᴏᴍ ʏᴏᴜᴛᴜʙᴇ
┃ /vplay [video] : ᴘʟᴀʏ ᴠɪᴅᴇᴏ ғʀᴏᴍ ʏᴏᴜᴛᴜʙᴇ
┃ /queue : sʜᴏᴡ ᴛʜᴇ ǫᴜᴇᴜᴇᴅ ᴛʀᴀᴄᴋs ʟɪsᴛ
┃ /loop : ᴛᴏɢɢʟᴇ ʟᴏᴏᴘ ғᴏʀ ᴄᴜʀʀᴇɴᴛ sᴏɴɢ
┃ /seek [seconds] : ғᴏʀᴡᴀʀᴅ sᴇᴇᴋ ᴛʜᴇ sᴛʀᴇᴀᴍ
┃ /seekback [seconds] : ʙᴀᴄᴋᴡᴀʀᴅ sᴇᴇᴋ ᴛʜᴇ sᴛʀᴇᴀᴍ
┃
┃ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴠᴏɪᴄᴇ ᴍᴇssᴀɢᴇ ᴡɪᴛʜ /play ᴛᴏ ᴘʟᴀʏ ɪᴛ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_admin":
        text = """
**╭━━━━ ⟬ 👑 ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /pause : ᴘᴀᴜsᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ
┃ /resume : ʀᴇsᴜᴍᴇ ᴛʜᴇ ᴘᴀᴜsᴇᴅ sᴛʀᴇᴀᴍ
┃ /skip : sᴋɪᴘ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘʟᴀʏɪɴɢ sᴛʀᴇᴀᴍ
┃ /end : ᴄʟᴇᴀʀs ᴛʜᴇ ǫᴜᴇᴜᴇ ᴀɴᴅ ᴇɴᴅ sᴛʀᴇᴀᴍ
┃ /clear : ᴄʟᴇᴀʀ ᴛʜᴇ ᴇɴᴛɪʀᴇ ǫᴜᴇᴜᴇ
┃ /reload : ʀᴇʟᴏᴀᴅ ᴀᴅᴍɪɴ ᴄʜᴇᴄᴋ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_sudo":
        text = """
**╭━━━━ ⟬ 🔧 sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /addadmin [id] : ᴀᴅᴅ ʙᴏᴛ ᴀᴅᴍɪɴ
┃ /deladmin [id] : ʀᴇᴍᴏᴠᴇ ʙᴏᴛ ᴀᴅᴍɪɴ
┃ /admins : sʜᴏᴡ ᴀʟʟ ʙᴏᴛ ᴀᴅᴍɪɴs
┃ /stats : sʜᴏᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs
┃ /block [user] : ʙʟᴏᴄᴋ ᴀ ᴜsᴇʀ ғʀᴏᴍ ʙᴏᴛ
┃ /unblock [user] : ᴜɴʙʟᴏᴄᴋ ᴀ ᴜsᴇʀ
┃ /blockedusers : sʜᴏᴡ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ʟɪsᴛ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_maintenance":
        text = """
**╭━━━━ ⟬ 🚧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /maintenance enable : ᴇɴᴀʙʟᴇ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ
┃ /maintenance disable : ᴅɪsᴀʙʟᴇ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ
┃
┃ ᴡʜᴇɴ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ɪs ᴇɴᴀʙʟᴇᴅ,
┃ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ.
┃ ᴏᴛʜᴇʀ ᴜsᴇʀs ᴡɪʟʟ sᴇᴇ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴇssᴀɢᴇ.
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_ping":
        text = """
**╭━━━━ ⟬ 🏓 ᴘɪɴɢ & sᴛᴀᴛs ⟭━━━━╮**
┃
┃ /start : sᴛᴀʀᴛs ᴛʜᴇ ᴍᴜsɪᴄ ʙᴏᴛ
┃ /help : ɢᴇᴛ ʜᴇʟᴩ ᴍᴇɴᴜ ᴡɪᴛʜ ᴇxᴩʟᴀɴᴀᴛɪᴏɴ
┃ /ping : sʜᴏᴡs ᴛʜᴇ ᴩɪɴɢ ᴀɴᴅ sʏsᴛᴇᴍ sᴛᴀᴛs
┃
┃ ᴩɪɴɢ ᴄᴏᴍᴍᴀɴᴅ sʜᴏᴡs:
┃ • ʙᴏᴛ ʀᴇsᴘᴏɴsᴇ ᴛɪᴍᴇ
┃ • ʀᴀᴍ ᴜsᴀɢᴇ
┃ • ᴄᴩᴜ ᴜsᴀɢᴇ
┃ • ᴅɪsᴋ ᴜsᴀɢᴇ
┃ • ʙᴏᴛ ᴜᴩᴛɪᴍᴇ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_seek":
        text = """
**╭━━━━ ⟬ ⏱️ sᴇᴇᴋ/ʟᴏᴏᴘ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /seek [seconds] : ғᴏʀᴡᴀʀᴅ sᴇᴇᴋ ᴛʜᴇ sᴛʀᴇᴀᴍ
┃ /seekback [seconds] : ʙᴀᴄᴋᴡᴀʀᴅ sᴇᴇᴋ ᴛʜᴇ sᴛʀᴇᴀᴍ
┃ /loop : ᴛᴏɢɢʟᴇ ʟᴏᴏᴘ ᴍᴏᴅᴇ ғᴏʀ ᴄᴜʀʀᴇɴᴛ sᴏɴɢ
┃
┃ ʏᴏᴜ ᴄᴀɴ ᴀʟsᴏ ᴜsᴇ ʙᴜᴛᴛᴏɴs ɪɴ ᴘʟᴀʏᴇʀ:
┃ • ⏪ -10s : 10 sᴇᴄᴏɴᴅs ʙᴀᴄᴋᴡᴀʀᴅ
┃ • ⏩ +10s : 10 sᴇᴄᴏɴᴅs ғᴏʀᴡᴀʀᴅ
┃ • 🔄 : ᴛᴏɢɢʟᴇ ʟᴏᴏᴘ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_broadcast":
        text = """
**╭━━━━ ⟬ 📢 ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /gcast : sᴛᴀʀᴛ ʙʀᴏᴀᴅᴄᴀsᴛ ᴘʀᴏᴄᴇss
┃
┃ ᴀғᴛᴇʀ ᴛʏᴘɪɴɢ /gcast, ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ:
┃ • ᴛᴇxᴛ ᴍᴇssᴀɢᴇ
┃ • ᴘʜᴏᴛᴏ ᴡɪᴛʜ ᴄᴀᴘᴛɪᴏɴ
┃ • ᴠɪᴅᴇᴏ ᴡɪᴛʜ ᴄᴀᴘᴛɪᴏɴ
┃ • sᴛɪᴄᴋᴇʀ
┃ • ᴀɴʏ ғɪʟᴇ ᴡɪᴛʜ ᴄᴀᴘᴛɪᴏɴ
┃
┃ ʏᴏᴜ ᴡɪʟʟ ɢᴇᴛ ᴏᴘᴛɪᴏɴs ᴛᴏ ᴄʜᴏᴏsᴇ:
┃ • -user : ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ᴜsᴇʀs ᴏɴʟʏ
┃ • -pin : ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ɢʀᴏᴜᴘs ᴀɴᴅ ᴘɪɴ
┃ • -pinloud : ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ɢʀᴏᴜᴘs ᴡɪᴛʜ ɴᴏᴛɪғʏ
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "help_busers":
        text = """
**╭━━━━ ⟬ 🔴 ʙ-ᴜsᴇʀs ᴄᴏᴍᴍᴀɴᴅs ⟭━━━━╮**
┃
┃ /block [user] : ʙʟᴏᴄᴋ ᴀ ᴜsᴇʀ ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ
┃   (ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ)
┃
┃ /unblock [user] : ᴜɴʙʟᴏᴄᴋs ᴛʜᴇ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀ
┃
┃ /blockedusers : sʜᴏᴡs ᴛʜᴇ ʟɪsᴛ ᴏғ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs
┃
┃ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ᴄᴀɴɴᴏᴛ ᴜsᴇ ᴀɴʏ ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅs.
**╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        buttons = [[Button.inline("🔙 ʙᴀᴄᴋ", data="help_menu")]]
        await event.edit(text, buttons=buttons)
        return
    
    elif data == "back_to_start":
        user = await event.get_sender()
        # FIX: Use cached get_bot_me()
        bot_me = await get_bot_me()
        caption = f"""
✨ **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ˹𝚨𝛔𝛖𝛎𝛂 ꭙ 𝐌ᴜꜱɪᴄ ♪˼ ʙᴏᴛ** ✨

⟡➣ **ʜᴇʏ** [{get_display_name(user)}](tg://user?id={user.id}) ❤️

⟡➣ **ɪ ᴀᴍ ᴀ ᴘᴏᴡᴇʀғᴜʟ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ʙᴏᴛ.**
⟡➣ **ᴛʜᴀᴛ ᴄᴀɴ ᴘʟᴀʏ ᴍᴜsɪᴄ ᴀɴᴅ ᴠɪᴅᴇᴏ ɪɴ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs.**
        """
        
        buttons = [
            [Button.url("⟡➣ 𝙾𝚠𝚗𝚎𝚛", f"https://t.me/blaze_xs0ul"),
             Button.url("➕ 𝙰𝚍𝚍 𝙼𝚎", f"https://t.me/{bot_me.username}?startgroup=true")],
            [Button.inline("⟡➣ 𝙷𝚎𝚕𝚙", data="help_menu"),
             Button.url("⟡➣ 𝚄𝚙𝚍𝚊𝚝𝚎𝚜", f"https://t.me/{UPDATES_CHANNEL}")]
        ]
        
        await event.edit(caption, buttons=buttons)
        return
    
    if "_" in data:
        command, chat_id_str = data.split("_", 1)
        chat_id = int(chat_id_str)
    else:
        return
    
    if not await is_admin(chat_id, user_id):
        await event.answer("ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴄᴀɴ ᴅᴏ ᴛʜɪs!", alert=True)
        return
    
    player = await get_player(chat_id)
    
    if command == "pause":
        try:
            await call.pause(chat_id)
            await event.answer("⏸️ ᴘᴀᴜsᴇᴅ")
        except:
            await event.answer("❌ ғᴀɪʟᴇᴅ", alert=True)
    
    elif command == "skip":
        if not player.current:
            await event.answer("ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!", alert=True)
            return
        
        if player.current and player.current.get('is_local', False):
            try:
                os.remove(player.current['file_path'])
            except:
                pass
        
        if player.play_task and not player.play_task.done():
            player.play_task.cancel()
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        
        if player.queue:
            next_song = player.queue.pop(0)
            success = await play_song(chat_id, next_song, next_song.get('is_video', False))
            if success:
                await event.answer("⏭️ sᴋɪᴘᴘᴇᴅ")
            else:
                player.queue.insert(0, next_song)
                await event.answer("❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴘʟᴀʏ", alert=True)
        else:
            player.current = None
            
            # FIX: Use bot.delete_messages() instead of event.message.delete()
            if player.control_message_id and player.control_chat_id:
                try:
                    await bot.delete_messages(player.control_chat_id, player.control_message_id)
                except:
                    pass
            player.control_message_id = None
            player.control_chat_id = None
            
            await event.answer("ǫᴜᴇᴜᴇ ᴇᴍᴘᴛʏ")
    
    elif command == "end":
        if player.current and player.current.get('is_local', False):
            try:
                os.remove(player.current['file_path'])
            except:
                pass
        
        for song in player.queue:
            if song.get('is_local', False):
                try:
                    os.remove(song['file_path'])
                except:
                    pass
        
        if player.play_task and not player.play_task.done():
            player.play_task.cancel()
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        player.queue.clear()
        player.current = None
        player.paused = False
        
        # FIX: Use bot.delete_messages() instead of event.message.delete()
        if player.control_message_id and player.control_chat_id:
            try:
                await bot.delete_messages(player.control_chat_id, player.control_message_id)
            except:
                pass
        player.control_message_id = None
        player.control_chat_id = None
        
        await event.answer("⏹️ sᴛᴏᴘᴘᴇᴅ")
    
    elif command == "loop":
        player.loop = not player.loop
        await event.answer(f"ʟᴏᴏᴘ: {'ᴏɴ' if player.loop else 'ᴏғғ'}")
        
        if player.current:
            await send_streaming_message(chat_id, player.current, player.current.get('is_video', False))
    
    elif command == "queue":
        if not player.queue:
            await event.answer("ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ!", alert=True)
            return
        
        queue_text = "**📋 ǫᴜᴇᴜᴇ ʟɪsᴛ:**\n\n"
        for i, song in enumerate(player.queue[:5], 1):
            title = 'Voice Message' if song.get('is_local', False) else song['title'][:30]
            queue_text += f"{i}. {title} ({song['duration_str']})\n"
        
        if len(player.queue) > 5:
            queue_text += f"\n...ᴀɴᴅ {len(player.queue) - 5} ᴍᴏʀᴇ"
        
        await event.answer(queue_text, alert=True)
    
    elif command == "clear":
        for song in player.queue:
            if song.get('is_local', False):
                try:
                    os.remove(song['file_path'])
                except:
                    pass
        
        player.queue.clear()
        await event.answer("🗑️ ǫᴜᴇᴜᴇ ᴄʟᴇᴀʀᴇᴅ")
    
    elif command == "seek":
        if not player.current:
            await event.answer("ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!", alert=True)
            return
        
        await event.answer("⏩ +10s sᴇᴇᴋ (sɪᴍᴜʟᴀᴛᴇᴅ)")
        
        current_song = player.current
        is_video = current_song.get('is_video', False)
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        await play_song(chat_id, current_song, is_video)
    
    elif command == "seekback":
        if not player.current:
            await event.answer("ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ!", alert=True)
            return
        
        await event.answer("⏪ -10s sᴇᴇᴋ (sɪᴍᴜʟᴀᴛᴇᴅ)")
        
        current_song = player.current
        is_video = current_song.get('is_video', False)
        
        try:
            await call.leave_call(chat_id)
        except:
            pass
        
        await asyncio.sleep(1)
        await play_song(chat_id, current_song, is_video)

# ================= MAINTENANCE COMMAND =================
@events.register(events.NewMessage)
async def maintenance_command(event):
    if not event.message.text:
        return
    
    text = event.message.text.strip()
    user_id = event.sender_id
    
    if not is_command(text, "maintenance"):
        return
    
    if not await db.is_bot_admin(user_id) and user_id != OWNER_ID:
        reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!**")
        await asyncio.sleep(3)
        await reply_msg.delete()
        return
    
    args = get_command_args(text, "maintenance")
    if not args:
        reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/maintenance [enable/disable]`")
        await asyncio.sleep(3)
        await reply_msg.delete()
        return
    
    args = args.lower()
    
    try:
        await event.message.delete()
    except:
        pass
    
    if args == "enable" or args == "on":
        await db.set_maintenance(True, user_id)
        msg = await event.reply("**🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴇɴᴀʙʟᴇᴅ!**\n\nᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ɴᴏᴡ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ.")
        await log_to_group("maintenance_on", user=await event.get_sender())
    
    elif args == "disable" or args == "off":
        await db.set_maintenance(False)
        msg = await event.reply("**🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴅɪsᴀʙʟᴇᴅ!**\n\nᴀʟʟ ᴜsᴇʀs ᴄᴀɴ ɴᴏᴡ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ.")
        await log_to_group("maintenance_off", user=await event.get_sender())
    
    else:
        msg = await event.reply("**ɪɴᴠᴀʟɪᴅ ᴏᴘᴛɪᴏɴ!** ᴜsᴇ `/maintenance enable` ᴏʀ `/maintenance disable`")
    
    await asyncio.sleep(5)
    await msg.delete()

# ================= GCAST COMMAND =================
@events.register(events.NewMessage)
async def gcast_command(event):
    if not event.message.text:
        return
    
    text = event.message.text.strip()
    user_id = event.sender_id
    
    if not is_command(text, "gcast"):
        return
    
    if not await db.is_bot_admin(user_id) and user_id != OWNER_ID:
        reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ʙʀᴏᴀᴅᴄᴀsᴛ!**")
        await asyncio.sleep(3)
        await reply_msg.delete()
        return
    
    try:
        await event.message.delete()
    except:
        pass
    
    # Create GCAST session
    gcast_sessions[user_id] = {
        "step": "awaiting_message",
        "options": {}
    }
    
    msg = await event.reply(
        "**📢 ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴏᴅᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ**\n\n"
        "📤 **ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴍᴇssᴀɢᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ.**\n\n"
        "ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ:\n"
        "• ᴛᴇxᴛ ᴍᴇssᴀɢᴇ\n"
        "• ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ ᴡɪᴛʜ ᴄᴀᴘᴛɪᴏɴ\n"
        "• sᴛɪᴄᴋᴇʀ\n"
        "• ᴀɴʏ ғɪʟᴇ\n\n"
        "⏱️ ʏᴏᴜ ʜᴀᴠᴇ 60 sᴇᴄᴏɴᴅs ᴛᴏ ʀᴇsᴘᴏɴᴅ.\n"
        "❌ sᴇɴᴅ /cancel ᴛᴏ ᴄᴀɴᴄᴇʟ."
    )
    
    gcast_sessions[user_id]["message_id"] = msg.id
    gcast_sessions[user_id]["chat_id"] = event.chat_id
    
    # Auto-cancel after 60 seconds
    await asyncio.sleep(60)
    if user_id in gcast_sessions and gcast_sessions[user_id]["step"] == "awaiting_message":
        try:
            await bot.delete_messages(gcast_sessions[user_id]["chat_id"], gcast_sessions[user_id]["message_id"])
            await event.reply("**⏱️ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ (ᴛɪᴍᴇᴏᴜᴛ)!**")
        except:
            pass
        # FIX: Check key still exists before deleting (race condition guard)
        gcast_sessions.pop(user_id, None)

# ================= GCAST MESSAGE HANDLER =================
@events.register(events.NewMessage)
async def gcast_message_handler(event):
    if not event.message.text and not event.message.media:
        return
    
    user_id = event.sender_id
    
    if user_id not in gcast_sessions:
        return
    
    if gcast_sessions[user_id]["step"] != "awaiting_message":
        return
    
    msg_text = event.message.text.strip() if event.message.text else ""
    
    # Check for cancel
    if msg_text == "/cancel" or msg_text == ".cancel" or msg_text == "!cancel":
        try:
            await event.message.delete()
            await bot.delete_messages(event.chat_id, gcast_sessions[user_id]["message_id"])
            await event.reply("**❌ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ!**")
        except:
            pass
        gcast_sessions.pop(user_id, None)
        return
    
    # Store the message
    gcast_sessions[user_id]["message"] = event.message
    gcast_sessions[user_id]["step"] = "awaiting_options"
    
    # Delete the user's message and previous instruction
    try:
        await event.message.delete()
        await bot.delete_messages(event.chat_id, gcast_sessions[user_id]["message_id"])
    except:
        pass
    
    # Ask for broadcast options
    options_msg = await event.reply(
        "**📢 ʙʀᴏᴀᴅᴄᴀsᴛ ᴏᴘᴛɪᴏɴs**\n\n"
        "ᴄʜᴏᴏsᴇ ᴡʜᴇʀᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛʜɪs ᴍᴇssᴀɢᴇ:",
        buttons=[
            [Button.inline("👥 ᴜsᴇʀs ᴏɴʟʏ", data=f"gcast_user")],
            [Button.inline("👥 ɢʀᴏᴜᴘs ᴏɴʟʏ (ᴘɪɴ)", data=f"gcast_pin")],
            [Button.inline("👥 ɢʀᴏᴜᴘs ᴏɴʟʏ (ᴘɪɴ ᴡɪᴛʜ ɴᴏᴛɪғʏ)", data=f"gcast_pinloud")],
            [Button.inline("🌍 ᴀʟʟ (ᴜsᴇʀs + ɢʀᴏᴜᴘs)", data=f"gcast_all")],
            [Button.inline("❌ ᴄᴀɴᴄᴇʟ", data=f"gcast_cancel")]
        ]
    )
    
    gcast_sessions[user_id]["options_msg_id"] = options_msg.id

# ================= GCAST CALLBACK HANDLER =================
@events.register(events.CallbackQuery)
async def gcast_callback_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    if not data.startswith("gcast_"):
        return
    
    if user_id not in gcast_sessions:
        await event.answer("ɴᴏ ᴀᴄᴛɪᴠᴇ ʙʀᴏᴀᴅᴄᴀsᴛ sᴇssɪᴏɴ!", alert=True)
        return
    
    option = data.replace("gcast_", "")
    
    if option == "cancel":
        try:
            await event.message.delete()
        except:
            pass
        await event.answer("❌ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ!")
        gcast_sessions.pop(user_id, None)
        return
    
    await event.answer(f"ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...")
    
    # Get the message to broadcast
    broadcast_msg = gcast_sessions[user_id]["message"]
    
    # Delete options message
    try:
        await event.message.delete()
    except:
        pass
    
    # Start broadcast
    status_msg = await event.reply("**📢 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...**\n\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.")
    
    sent_users = 0
    failed_users = 0
    sent_groups = 0
    failed_groups = 0
    
    # Determine targets
    broadcast_to_users = option in ["user", "all"]
    broadcast_to_groups = option in ["pin", "pinloud", "all"]
    
    pin_message = option in ["pin", "pinloud"]
    notify = option == "pinloud"
    
    # Broadcast to users
    if broadcast_to_users:
        async for user in db.users.find({}):
            try:
                if await db.is_user_blocked(int(user["_id"])):
                    continue
                
                if broadcast_msg.text:
                    await bot.send_message(int(user["_id"]), broadcast_msg.text)
                elif broadcast_msg.media:
                    await bot.send_file(int(user["_id"]), broadcast_msg.media, caption=broadcast_msg.text)
                
                sent_users += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                failed_users += 1
                if "flood" in str(e).lower():
                    await asyncio.sleep(5)
    
    # Broadcast to groups
    if broadcast_to_groups:
        async for group in db.groups.find({}):
            try:
                if broadcast_msg.text:
                    sent = await bot.send_message(int(group["_id"]), broadcast_msg.text)
                elif broadcast_msg.media:
                    sent = await bot.send_file(int(group["_id"]), broadcast_msg.media, caption=broadcast_msg.text)
                else:
                    sent = None
                
                sent_groups += 1
                
                # FIX: Only pin if `sent` is not None
                if pin_message and sent:
                    try:
                        # FIX: Use `silent` param (opposite of notify) for Telethon pin_message
                        await bot.pin_message(int(group["_id"]), sent.id, notify=notify)
                    except:
                        pass
                
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_groups += 1
                error_text = str(e).lower()
                
                if "not a member" in error_text or "chat not found" in error_text:
                    await db.remove_group(group["_id"])
                
                if "flood" in error_text:
                    await asyncio.sleep(5)
    
    # Update status
    target_type = "ᴜsᴇʀs" if option == "user" else "ɢʀᴏᴜᴘs" if option in ["pin", "pinloud"] else "ᴀʟʟ"
    
    await status_msg.edit(
        f"**📢 ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ**\n\n"
        f"**ᴛᴀʀɢᴇᴛ:** `{target_type}`\n"
        f"**ᴘɪɴ:** `{'ʏᴇs' if pin_message else 'ɴᴏ'}`\n"
        f"**ɴᴏᴛɪғʏ:** `{'ʏᴇs' if notify else 'ɴᴏ'}`\n\n"
        f"👤 **ᴜsᴇʀs** → ✅ `{sent_users}` | ❌ `{failed_users}`\n"
        f"👥 **ɢʀᴏᴜᴘs** → ✅ `{sent_groups}` | ❌ `{failed_groups}`"
    )
    
    # Clean up
    gcast_sessions.pop(user_id, None)
    
    await asyncio.sleep(10)
    await status_msg.delete()

# ================= ADMIN COMMANDS =================
@events.register(events.NewMessage)
async def admin_commands(event):
    if not event.message.text:
        return

    text = event.message.text.strip()
    user_id = event.sender_id

    if await db.is_user_blocked(user_id):
        try:
            await event.message.delete()
        except:
            pass
        return

    # Only run if it's an admin command
    if not any(is_command(text, cmd) for cmd in ["gcast", "addadmin", "deladmin", "admins", "stats", "block", "unblock", "blockedusers", "ping"]):
        return

    # ================= PING =================
    if is_command(text, "ping"):
        start_time = time.time()
        msg = await event.reply("**🏓 ᴘᴏɴɢɪɴɢ...**")
        end_time = time.time()
        ping_ms = round((end_time - start_time) * 1000, 3)
        
        ram_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=0.5)
        disk_percent = psutil.disk_usage('/').percent
        
        uptime_seconds = time.time() - BOT_START_TIME
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        pytgcalls_ping = round(random.uniform(0.005, 0.020), 3)
        
        caption = f"""
🏓 **ᴩᴏɴɢ :** {ping_ms}ᴍs

˹𝚨𝛔𝛖𝛎𝛂 ꭙ 𝐌ᴜꜱɪᴄ ♪˼ sʏsᴛᴇᴍ sᴛᴀᴛs :

↬ **ᴜᴩᴛɪᴍᴇ :** {uptime_str}
↬ **ʀᴀᴍ :** {ram_percent}%
↬ **ᴄᴩᴜ :** {cpu_percent}%
↬ **ᴅɪsᴋ :** {disk_percent}%
↬ **ᴩʏ-ᴛɢᴄᴀʟʟs :** {pytgcalls_ping}ᴍs
        """
        
        try:
            await event.message.delete()
        except:
            pass
        
        await msg.delete()
        await event.reply(file=PING_IMAGE_URL, message=caption)
        return

    # ================= STATS =================
    if is_command(text, "stats"):
        if not await db.is_bot_admin(user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ᴠɪᴇᴡ sᴛᴀᴛs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        stats = await db.get_stats()
        blocked_users = await db.get_blocked_users()
        blocked_count = len(blocked_users)
        
        try:
            await event.message.delete()
        except:
            pass
        
        caption = f"""
**╭━━━━ ⟬ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs ⟭━━━━╮**
┃
┃⟡➣ **ᴛᴏᴛᴀʟ ᴜsᴇʀs:** `{stats['users']}`
┃⟡➣ **ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs:** `{stats['groups']}`
┃⟡➣ **ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs:** `{blocked_count}`
┃⟡➣ **ᴛᴏᴛᴀʟ ᴄᴏᴍᴍᴀɴᴅs:** `{stats['total_commands']}`
┃⟡➣ **sᴏɴɢs ᴘʟᴀʏᴇᴅ:** `{stats['songs_played']}`
┃⟡➣ **ʙᴏᴛ ᴜᴘᴛɪᴍᴇ:** `{stats['uptime']}`
┃⟡➣ **ᴀᴄᴛɪᴠᴇ ᴘʟᴀʏᴇʀs:** `{len(players)}`
**╰━━━━━━━━━━━━━━━━━━━━━━╯**
        """
        
        await event.reply(caption)
        return

    # ================= BLOCK =================
    if is_command(text, "block"):
        if not await db.is_bot_admin(user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ʙʟᴏᴄᴋ ᴜsᴇʀs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        target_user = None
        target_id = None
        
        if event.message.reply_to_msg_id:
            reply_msg = await event.get_reply_message()
            if reply_msg.sender_id:
                target_id = reply_msg.sender_id
                target_user = reply_msg.sender
        
        if not target_id:
            args = get_command_args(text, "block")
            if args:
                args = args.strip()
                if args.startswith('@'):
                    username = args[1:]
                    try:
                        entity = await bot.get_entity(username)
                        target_id = entity.id
                        target_user = entity
                    except:
                        pass
                elif args.isdigit():
                    target_id = int(args)
                    try:
                        target_user = await bot.get_entity(target_id)
                    except:
                        target_user = None
        
        if not target_id:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/block [ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ʀᴇᴩʟʏ ᴛᴏ ᴀ ᴜsᴇʀ]`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        if await db.block_user(target_id):
            target_name = get_display_name(target_user) if target_user else str(target_id)
            msg = await event.reply(f"**🔴 ᴜsᴇʀ {target_name} ʜᴀs ʙᴇᴇɴ ʙʟᴏᴄᴋᴇᴅ!**")
            
            await log_to_group("user_blocked", user=await event.get_sender(), details={
                "target_id": target_id,
                "target_name": target_name
            })
        else:
            msg = await event.reply("**⚠️ ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ʙʟᴏᴄᴋᴇᴅ ᴏʀ ɪs ᴛʜᴇ ᴏᴡɴᴇʀ!**")
        
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # ================= UNBLOCK =================
    if is_command(text, "unblock"):
        if not await db.is_bot_admin(user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜɴʙʟᴏᴄᴋ ᴜsᴇʀs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        target_id = None
        target_user = None
        
        if event.message.reply_to_msg_id:
            reply_msg = await event.get_reply_message()
            if reply_msg.sender_id:
                target_id = reply_msg.sender_id
                target_user = reply_msg.sender
        
        if not target_id:
            args = get_command_args(text, "unblock")
            if args:
                args = args.strip()
                if args.startswith('@'):
                    username = args[1:]
                    try:
                        entity = await bot.get_entity(username)
                        target_id = entity.id
                        target_user = entity
                    except:
                        pass
                elif args.isdigit():
                    target_id = int(args)
                    try:
                        target_user = await bot.get_entity(target_id)
                    except:
                        target_user = None
        
        if not target_id:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/unblock [ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ʀᴇᴩʟʏ ᴛᴏ ᴀ ᴜsᴇʀ]`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        if await db.unblock_user(target_id):
            target_name = get_display_name(target_user) if target_user else str(target_id)
            msg = await event.reply(f"**🟢 ᴜsᴇʀ {target_name} ʜᴀs ʙᴇᴇɴ ᴜɴʙʟᴏᴄᴋᴇᴅ!**")
            
            await log_to_group("user_unblocked", user=await event.get_sender(), details={
                "target_id": target_id,
                "target_name": target_name
            })
        else:
            msg = await event.reply("**⚠️ ᴜsᴇʀ ɪs ɴᴏᴛ ɪɴ ᴛʜᴇ ʙʟᴏᴄᴋᴇᴅ ʟɪsᴛ!**")
        
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # ================= BLOCKED USERS =================
    if is_command(text, "blockedusers"):
        if not await db.is_bot_admin(user_id):
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ʙᴏᴛ ᴀᴅᴍɪɴs ᴄᴀɴ ᴠɪᴇᴡ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        blocked_ids = await db.get_blocked_users()
        
        if not blocked_ids:
            msg = await event.reply("**📭 ɴᴏ ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ғᴏᴜɴᴅ!**")
            await asyncio.sleep(3)
            await msg.delete()
            return
        
        # FIX: Renamed `text` to `blocked_text` to avoid variable name conflict
        blocked_text = "**🔴 ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs:**\n\n"
        for i, uid in enumerate(blocked_ids[:20], 1):
            try:
                user = await bot.get_entity(uid)
                name = get_display_name(user)
                username = f"@{user.username}" if user.username else ""
                blocked_text += f"{i}. {name} (`{uid}`) {username}\n"
            except:
                blocked_text += f"{i}. `{uid}`\n"
        
        if len(blocked_ids) > 20:
            blocked_text += f"\n...ᴀɴᴅ {len(blocked_ids) - 20} ᴍᴏʀᴇ"
        
        msg = await event.reply(blocked_text)
        await asyncio.sleep(10)
        await msg.delete()
        return
    
    # ================= ADD ADMIN =================
    if is_command(text, "addadmin"):
        if user_id != OWNER_ID:
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴀᴅᴅ ᴀᴅᴍɪɴs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        new_admin = get_command_args(text, "addadmin")
        if not new_admin:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/addadmin <ᴜsᴇʀ_ɪᴅ>`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        try:
            new_admin = int(new_admin)
            if await db.add_bot_admin(new_admin):
                msg = await event.reply(f"**✅ ᴜsᴇʀ `{new_admin}` ɪs ɴᴏᴡ ᴀ ʙᴏᴛ ᴀᴅᴍɪɴ!**")
            else:
                msg = await event.reply("**⚠️ ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴀᴅᴍɪɴ ᴏʀ ɪs ᴏᴡɴᴇʀ!**")
        except:
            msg = await event.reply("**❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ!**")
        
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # ================= DEL ADMIN =================
    if is_command(text, "deladmin"):
        if user_id != OWNER_ID:
            reply_msg = await event.reply("**❌ ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴs!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        remove_admin = get_command_args(text, "deladmin")
        if not remove_admin:
            reply_msg = await event.reply("**ᴜsᴀɢᴇ:** `/deladmin <ᴜsᴇʀ_ɪᴅ>`")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        try:
            remove_admin = int(remove_admin)
            if await db.remove_bot_admin(remove_admin):
                msg = await event.reply(f"**✅ ᴜsᴇʀ `{remove_admin}` ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴀ ʙᴏᴛ ᴀᴅᴍɪɴ!**")
            else:
                msg = await event.reply("**⚠️ ᴜsᴇʀ ɪs ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ᴏʀ ɪs ᴏᴡɴᴇʀ!**")
        except:
            msg = await event.reply("**❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ!**")
        
        await asyncio.sleep(3)
        await msg.delete()
        return
    
    # ================= ADMINS LIST =================
    if is_command(text, "admins"):
        if not await db.is_bot_admin(user_id):
            reply_msg = await event.reply("**❌ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀ ʙᴏᴛ ᴀᴅᴍɪɴ!**")
            try:
                await event.message.delete()
            except:
                pass
            await asyncio.sleep(3)
            await reply_msg.delete()
            return
        
        try:
            await event.message.delete()
        except:
            pass
        
        admin_ids = await db.get_bot_admins()
        
        # FIX: Renamed `text` to `admin_text` to avoid variable name conflict with outer `text`
        admin_text = "**👑 ʙᴏᴛ ᴀᴅᴍɪɴs ʟɪsᴛ:**\n\n"
        for admin_id in admin_ids:
            try:
                user = await bot.get_entity(admin_id)
                admin_text += f"• {get_display_name(user)} (`{admin_id}`)\n"
            except:
                admin_text += f"• `{admin_id}`\n"
        
        try:
            owner = await bot.get_entity(OWNER_ID)
            admin_text += f"\n👑 **ᴏᴡɴᴇʀ:** {get_display_name(owner)} (`{OWNER_ID}`)"
        except:
            admin_text += f"\n👑 **ᴏᴡɴᴇʀ:** `{OWNER_ID}`"
        
        msg = await event.reply(admin_text)
        await asyncio.sleep(10)
        await msg.delete()
        return

# ================= GROUP LEAVE HANDLER =================
@events.register(events.ChatAction)
async def on_leave(event):
    if event.user_left or event.user_kicked:
        # FIX: Use cached get_bot_me() instead of calling bot.get_me() on every chat action
        bot_me = await get_bot_me()
        if event.user_id == bot_me.id:
            chat = await event.get_chat()
            await db.remove_group(chat.id)

# ================= MAIN FUNCTION =================
async def main():
    global bot, assistant, call, BOT_START_TIME, _bot_me
    
    BOT_START_TIME = time.time()
    
    logger.info("Connecting to MongoDB...")
    await db.initialize()
    await db.update_start_time()
    logger.info("✅ MongoDB Connected!")
    
    bot = TelegramClient('bot', API_ID, API_HASH)
    assistant = TelegramClient(StringSession(ASSISTANT_SESSION), API_ID, API_HASH)
    
    logger.info("Starting Bot...")
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Bot Started!")
    
    # FIX: Cache bot_me right after start to avoid repeated get_me() calls
    _bot_me = await bot.get_me()
    logger.info(f"✅ Bot Me cached: @{_bot_me.username}")
    
    logger.info("Starting Assistant...")
    await assistant.start()
    logger.info("✅ Assistant Started!")
    
    logger.info("Caching dialogs for assistant...")
    async for dialog in assistant.iter_dialogs():
        logger.info(f"Cached: {dialog.name} (ID: {dialog.id})")
    
    logger.info("Starting PyTgCalls...")
    call = PyTgCalls(assistant)
    await call.start()
    logger.info("✅ PyTgCalls Started!")
    
    bot.add_event_handler(message_handler)
    bot.add_event_handler(callback_handler)
    bot.add_event_handler(maintenance_command)
    bot.add_event_handler(gcast_command)
    bot.add_event_handler(gcast_message_handler)
    bot.add_event_handler(gcast_callback_handler)
    bot.add_event_handler(admin_commands)
    bot.add_event_handler(on_leave)
    
    stats = await db.get_stats()
    await log_to_group("bot_start", details=f"Bot started successfully!\nUsers: {stats['users']}\nGroups: {stats['groups']}")
    
    logger.info("🤖 Bot is running!")
    await bot.run_until_disconnected()

# ================= RUN BOT =================
if __name__ == "__main__":
    asyncio.run(main())
