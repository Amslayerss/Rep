import json
import asyncio
import logging
import os
import glob
from telethon import TelegramClient, events, functions, types
from telethon.errors import SessionPasswordNeededError, ChatAdminRequiredError, ChannelPrivateError, UserAlreadyParticipantError, FloodWaitError, InviteRequestSentError
import logging.handlers

# Add these functions at the top of your file, before setting up logging
def check_log_size(log_file, max_size_mb=1):
    """Check if log file exceeds the maximum size and delete it if needed"""
    try:
        if os.path.exists(log_file):
            size_mb = os.path.getsize(log_file) / (1024 * 1024)  # Convert bytes to MB
            if size_mb >= max_size_mb:
                os.remove(log_file)
                return True
    except Exception as e:
        print(f"Error checking log file size: {str(e)}")
    return False

# Add this right before your logging.basicConfig() call
log_file = "bot_debug.log"
check_log_size(log_file)  # Clean up log file if it's too large

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=1024*1024,  # 1MB
            backupCount=0  # Don't keep backup files, just overwrite when full
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ReportBot")

# Configuration
API_ID = "22384067"
API_HASH = "a6e4f48ba9a20a319af00fb04378134b"
BOT_TOKEN = "7555896380:AAEeaNfLuFeTujfRjrTk1o0hFq5PVXuwihY"

NOREPORT_CHATS = [
    "@Mod_By_Kamal",
    "https://t.me/KamalxKiller",
    "https://t.me/kamalxkiller_gc",
    "@CodeWraith_Here",
    "@https://t.me/+pRysSFARlMwxNDRl",
    "@https://t.me/+JNJoNqA3yLo4YzBl",
    "@https://t.me/+wyXo7kIMRlhhMDQ8",
    "@https://t.me/+xiNdn4d2OBZlYjhl",
]

# File to store user data and sessions
USERS_FILE = 'users.json'  # Path to your users file
SESSIONS_DIR = '.'  # Directory containing session files (current directory by default)
REPORT_CATEGORIES = ['spam', 'violence', 'pornography', 'illegal_drugs', 'personal_details', 'other']

# Initialize the global users dictionary properly
users = {"users": {}, "sessions": {}}

# Load existing users and sessions with better error handling
try:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            content = f.read().strip()
            if content:  # Only try to load JSON if file has content
                try:
                    loaded_users = json.loads(content)
                    # Ensure the loaded data has the expected structure
                    if isinstance(loaded_users, dict):
                        # Make sure both required keys exist
                        if "users" in loaded_users:
                            users["users"] = loaded_users["users"]
                        if "sessions" in loaded_users:
                            users["sessions"] = loaded_users["sessions"]
                        
                        logger.info(f"Loaded users data: {len(users.get('users', {}))} users, {len(users.get('sessions', {}))} sessions")
                        logger.debug(f"Registered users: {list(users.get('users', {}).keys())}")
                    else:
                        logger.error("Invalid users data format in file, using empty data")
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON parsing error: {str(json_err)}, using empty data")
            else:
                # File exists but is empty
                logger.info("Users file exists but is empty. Using empty users data.")
                
                # Create the file with default structure
                with open(USERS_FILE, 'w') as f:
                    json.dump(users, f, indent=4)
    else:
        # File doesn't exist
        logger.info("Users file doesn't exist. Creating new file with empty users data.")
        
        # Create the file with default structure
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        logger.info(f"Created new users file at {USERS_FILE}")
except Exception as e:
    logger.error(f"Error loading users data: {str(e)}", exc_info=True)
    logger.info("Using empty users data due to error")
    
    # Try to create the file with default structure
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        logger.info(f"Created new users file at {USERS_FILE}")
    except Exception as write_err:
        logger.error(f"Could not create users file: {str(write_err)}", exc_info=True)

def save_users():
    """Save user data to the users.json file with additional error handling"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        
        # Verify the file was written correctly by reading it back
        with open(USERS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                logger.error(f"Error saving users: file is empty after save")
                return False
            
            test_users = json.loads(content)
            logger.info(f"Users data saved and verified. Users: {len(test_users.get('users', {}))} Sessions: {len(test_users.get('sessions', {}))}")
            return True
    except Exception as e:
        logger.error(f"Error saving users data: {str(e)}", exc_info=True)
        return False

def is_in_noreport_chats(link):
    """
    Check if a given link/username is in the NOREPORT_CHATS list,
    checking all possible formats (with/without @, with/without https://t.me/, etc.)
    """
    logger.debug(f"Checking if {link} is in NOREPORT_CHATS")
    
    # Normalize the input link/username
    normalized_input = link.lower()
    
    # Extract username without any prefixes
    username = None
    
    # Handle t.me links
    if normalized_input.startswith('http://t.me/') or normalized_input.startswith('https://t.me/'):
        parts = normalized_input.split('/')
        if len(parts) >= 4:
            username = parts[3].lower()
    
    # Handle username with @ prefix
    elif normalized_input.startswith('@'):
        username = normalized_input[1:].lower()
    
    # Handle raw username
    else:
        username = normalized_input.lower()
    
    # Now check against all possible formats in NOREPORT_CHATS
    for no_report in NOREPORT_CHATS:
        normalized_no_report = no_report.lower()
        
        # Extract the username from the no_report entry
        no_report_username = None
        
        # Handle t.me links in NOREPORT_CHATS
        if normalized_no_report.startswith('http://t.me/') or normalized_no_report.startswith('https://t.me/'):
            parts = normalized_no_report.split('/')
            if len(parts) >= 4:
                no_report_username = parts[3].lower()
        
        # Handle username with @ prefix in NOREPORT_CHATS
        elif normalized_no_report.startswith('@'):
            no_report_username = normalized_no_report[1:].lower()
        
        # Handle raw username in NOREPORT_CHATS
        else:
            no_report_username = normalized_no_report.lower()
        
        # Compare the normalized usernames
        if username == no_report_username:
            logger.info(f"Found {link} in NOREPORT_CHATS as {no_report}")
            return True
            
        # Also check direct match with the original formats
        if normalized_input == normalized_no_report:
            logger.info(f"Found direct match for {link} in NOREPORT_CHATS")
            return True
    
    logger.debug(f"{link} is not in NOREPORT_CHATS")
    return False

def load_session_files(sessions_dir=SESSIONS_DIR):
    """Find and load available session files from specified directory"""
    if "sessions" not in users:
        users["sessions"] = {}
    
    session_count = 0
    # Get all session files in specified directory
    session_pattern = os.path.join(sessions_dir, '*.session')
    session_files = glob.glob(session_pattern)
    
    logger.info(f"Searching for session files in: {sessions_dir}")
    logger.info(f"Found {len(session_files)} session files: {session_files}")
    
    for session_path in session_files:
        # Extract phone number from filename (removing extension and path)
        session_name = os.path.basename(session_path)
        phone = session_name.replace('.session', '')
        
        # Skip if it doesn't look like a phone number
        if not (phone.startswith('+') and phone[1:].replace(' ', '').isdigit()):
            logger.debug(f"Skipping non-phone session: {phone}")
            continue
            
        # Add to sessions if not already there
        if phone not in users["sessions"]:
            users["sessions"][phone] = {
                "api_id": API_ID,
                "api_hash": API_HASH,
                "session_path": session_path  # Store the full path
            }
            session_count += 1
            logger.info(f"Added session for phone: {phone}")
    
    logger.info(f"Auto-detected {session_count} additional session files")
    if session_count > 0:
        save_users()
    return session_count

async def send_report(client, peer, category, attempts=10):
    """Send a report using the provided client session with multiple attempts"""
    logger.debug(f"Sending report for peer: {peer}, category: {category}")
    
    # Create appropriate reason object based on category
    if category == 'spam':
        reason = types.InputReportReasonSpam()
    elif category == 'violence':
        reason = types.InputReportReasonViolence()
    elif category == 'pornography':
        reason = types.InputReportReasonPornography()
    elif category == 'illegal_drugs':
        reason = types.InputReportReasonIllegalDrugs()
    elif category == 'personal_details':
        reason = types.InputReportReasonPersonalDetails()
    else:  # other
        reason = types.InputReportReasonOther()
    
    success_count = 0
    for attempt in range(attempts):
        try:
            logger.debug(f"Report attempt {attempt+1}/{attempts} for category: {category}")
            
            # For broadcast channels (not megagroups)
            if hasattr(peer, 'broadcast') and peer.broadcast:
                try:
                    # Get recent messages from the channel to report
                    messages = await client.get_messages(peer, limit=5)
                    if messages and len(messages) > 0:
                        msg_id = messages[0].id
                        logger.debug(f"Found message ID {msg_id} to report")
                        
                        # Try to report message with correct parameters
                        try:
                            # Simple direct approach using report API
                            result = await client(functions.account.ReportPeerRequest(
                                peer=peer,
                                reason=reason,
                                message=f'Reporting {category}'
                            ))
                            logger.info(f"Successfully reported channel using account.ReportPeerRequest, attempt {attempt+1}")
                            success_count += 1
                        except Exception as report_err:
                            logger.error(f"Error with ReportPeerRequest: {str(report_err)}")
                            
                            # Try to report specific message
                            try:
                                result = await client(functions.messages.ReportRequest(
                                    peer=peer,
                                    id=[msg_id],
                                    reason=reason,
                                    message=f'Reporting {category}'
                                ))
                                logger.info(f"Successfully reported channel message, attempt {attempt+1}")
                                success_count += 1
                            except Exception as msg_err:
                                logger.error(f"Error reporting message: {str(msg_err)}")
                    else:
                        # No messages found, try account.reportPeer instead
                        result = await client(functions.account.ReportPeerRequest(
                            peer=peer,
                            reason=reason,
                            message=f'Reporting {category}'
                        ))
                        logger.info(f"Successfully reported channel using account.ReportPeerRequest (no messages), attempt {attempt+1}")
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error reporting channel on attempt {attempt+1}: {str(e)}", exc_info=True)
            
            # For regular chats, groups and users
            else:
                try:
                    result = await client(functions.account.ReportPeerRequest(
                        peer=peer,
                        reason=reason,
                        message=f'Reporting {category}'
                    ))
                    logger.info(f"Successfully reported peer using ReportPeerRequest, attempt {attempt+1}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error with ReportPeerRequest on attempt {attempt+1}: {str(e)}", exc_info=True)
                    
                    try:
                        # Try to get recent messages to report
                        messages = await client.get_messages(peer, limit=5)
                        if messages and len(messages) > 0:
                            msg_id = messages[0].id
                            logger.debug(f"Found message ID {msg_id} to report")
                            
                            # Try with correct parameters
                            result = await client(functions.messages.ReportRequest(
                                peer=peer,
                                id=[msg_id],
                                reason=reason,
                                message=f'Reporting {category}'
                            ))
                            logger.info(f"Successfully reported using messages.ReportRequest, attempt {attempt+1}")
                            success_count += 1
                        else:
                            logger.warning(f"No messages found to report on attempt {attempt+1}")
                    except Exception as inner_e:
                        logger.error(f"Error with message reporting fallback on attempt {attempt+1}: {str(inner_e)}", exc_info=True)
            
            # Add a small delay between report attempts to avoid rate limiting
            await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Report error on attempt {attempt+1}: {str(e)}", exc_info=True)
    
    return success_count

def extract_entity_id(link):
    """Extract entity ID from various link formats"""
    logger.debug(f"Extracting entity ID from link: {link}")
    try:
        # Handle both http:// and https:// links
        if link.startswith('http://t.me/') or link.startswith('https://t.me/'):
            if '+' in link:
                # This is a private link with an invite hash
                parts = link.split('/')
                if len(parts) >= 4:
                    invite_link = parts[3]
                    logger.debug(f"Extracted private invite link: {invite_link}")
                    return invite_link
            else:
                # Handle public channel link - add @ prefix for usernames
                parts = link.split('/')
                if len(parts) >= 4:
                    username = parts[3]
                    logger.debug(f"Extracted username: {username}")
                    # Add @ prefix if it doesn't have one and isn't a private link
                    if not username.startswith('@') and not username.startswith('+'):
                        username = '@' + username
                    return username
        
        # Handle other formats
        if '@' in link:
            username = link.strip('@')
            logger.debug(f"Extracted username from @format: {username}")
            return '@' + username  # Make sure it has @ prefix
            
        # If link itself looks like a username without any protocol
        if not link.startswith('http') and not link.startswith('@') and not link.startswith('+'):
            logger.debug(f"Using as username: {link}")
            return '@' + link  # Add @ prefix
            
        logger.debug(f"Using link as is: {link}")
        return link
    except Exception as e:
        logger.error(f"Error extracting entity ID: {str(e)}", exc_info=True)
        return link

class ReportBot:
    def __init__(self, api_id, api_hash, bot_token):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot = TelegramClient('report_bot', api_id, api_hash)
        self.bot_token = bot_token
        self.active_sessions = {}
        self.pending_actions = {}
        logger.info(f"ReportBot initialized with API ID: {api_id}")

    async def start(self):
        logger.info("Starting bot")
        await self.bot.start(bot_token=self.bot_token)
        
        # Register event handlers
        self.bot.add_event_handler(self.on_start, events.NewMessage(pattern='/start'))
        self.bot.add_event_handler(self.on_register, events.NewMessage(pattern='/register'))
        self.bot.add_event_handler(self.on_report, events.NewMessage(pattern='/report'))
        self.bot.add_event_handler(self.on_addacc, events.NewMessage(pattern='/addacc'))
        self.bot.add_event_handler(self.on_loadsessions, events.NewMessage(pattern='/loadsessions'))
        self.bot.add_event_handler(self.on_message, events.NewMessage)
        
        logger.info("Bot started and event handlers registered!")
        await self.bot.run_until_disconnected()

    async def on_start(self, event):
        """Handle /start command"""
        user_id = str(event.sender_id)
        logger.info(f"User {user_id} sent /start command")
        
        # Ensure the users dictionary has the expected structure
        if "users" not in users:
            users["users"] = {}
        
        if user_id in users["users"]:
            logger.debug(f"User {user_id} is already registered")
            await event.respond('Welcome back! Use /report to report illegal content.\n\nCommands:\n/report <channel/group link> <category>\n/addacc <phone number>')
        else:
            logger.debug(f"User {user_id} is not registered")
            await event.respond('Please register first. Use /register')

    async def on_register(self, event):
        """Handle user registration"""
        user_id = str(event.sender_id)
        logger.info(f"User {user_id} sent register command")
        
        try:
            # Check if user is already registered
            if user_id in users.get("users", {}):
                logger.info(f"User {user_id} is already registered")
                username = users["users"][user_id]["name"]
                await event.respond(f"You are already registered as @{username}. You can use these commands:\n\n"
                                   f"/report <channel/group link> <category> - Report illegal content\n"
                                   f"/addacc <phone number> - Add a reporting account\n\n"
                                   f"Available report categories: {', '.join(REPORT_CATEGORIES)}")
                return
            
            # Get user information from the event
            sender = await event.get_sender()
            
            # Get username (if available) or first name
            if hasattr(sender, 'username') and sender.username:
                username = sender.username
            else:
                # Fallback to first name if no username
                username = sender.first_name if hasattr(sender, 'first_name') else f"User{user_id}"
            
            # Initialize users structure if it doesn't exist
            if "users" not in users:
                users["users"] = {}
            
            # Save user info including Telegram ID and automatically retrieved username
            users["users"][user_id] = {
                "name": username,
                "telegram_id": user_id,
                "reports": []
            }
            
            # Save to file and verify
            saved = save_users()
            
            if saved:
                logger.info(f"User {user_id} registered successfully as {username}")
                
                # Print debug info about the users dictionary
                logger.debug(f"Current users after registration: {list(users.get('users', {}).keys())}")
                
                response = f"Successfully registered as @{username}. You can now use these commands:\n\n"
                response += "/report <channel/group link> <category> - Report illegal content\n"
                response += "/addacc <phone number> - Add a reporting account\n\n"
                response += f"Available report categories: {', '.join(REPORT_CATEGORIES)}"
                
                await event.respond(response)
            else:
                logger.error(f"Failed to save user data for {user_id}")
                await event.respond("Registration failed. Please try again later.")
        except Exception as e:
            logger.error(f"Error in register handling: {str(e)}", exc_info=True)
            await event.respond(f"Registration error: {str(e)}")

    async def on_loadsessions(self, event):
        """Handle loading sessions from a directory"""
        user_id = str(event.sender_id)
        text = event.raw_text.strip()
        logger.info(f"User {user_id} sent loadsessions command: {text}")
        
        if user_id not in users["users"]:
            logger.warning(f"Unregistered user {user_id} tried to use loadsessions command")
            await event.respond('Please register first. Use /register <your_name>')
            return
            
        parts = event.raw_text.strip().split(' ', 1)
        sessions_dir = parts[1] if len(parts) > 1 else SESSIONS_DIR
        
        await event.respond(f"Looking for session files in: {sessions_dir}")
        
        try:
            session_count = load_session_files(sessions_dir)
            await event.respond(f"Found and loaded {session_count} new session files. Total sessions: {len(users['sessions'])}")
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}", exc_info=True)
            await event.respond(f"Error loading sessions: {str(e)}")

    async def on_report(self, event):
        """Handle reporting requests"""
        user_id = str(event.sender_id)
        text = event.raw_text.strip()
        logger.info(f"User {user_id} sent report command: {text}")
        
        # Ensure the users dictionary has the expected structure
        if "users" not in users:
            users["users"] = {}
        
        if user_id not in users["users"]:
            logger.warning(f"Unregistered user {user_id} tried to use report command")
            await event.respond('Please register first. Use /register')
            return

        try:
            parts = event.raw_text.strip().split(' ', 2)
            if len(parts) < 3:
                logger.warning(f"User {user_id} sent invalid report format")
                await event.respond(f"Please use the format: /report <channel/group link> <category>\nAvailable categories: {', '.join(REPORT_CATEGORIES)}")
                return
                
            _, link, category = parts
            logger.debug(f"Parsed link: {link}, category: {category}")
            
            # Check if the link is in NOREPORT_CHATS
            if is_in_noreport_chats(link):
                logger.info(f"User {user_id} tried to report a protected chat: {link}")
                await event.respond("You are not able to report your father")
                return
            
            if category.lower() not in REPORT_CATEGORIES:
                logger.warning(f"User {user_id} used invalid category: {category}")
                await event.respond(f"Invalid category. Please use one of these: {', '.join(REPORT_CATEGORIES)}")
                return
            
            # Extract the entity ID from the link
            entity_id = extract_entity_id(link)
            logger.info(f"Extracted entity ID: {entity_id} from link: {link}")
            
            # Check if there are any sessions to use
            if not users["sessions"]:
                logger.warning("No reporting accounts available")
                await event.respond("No reporting accounts added. Use /loadsessions or /addacc command.")
                return
            
            await event.respond(f"Starting to report {entity_id} for {category} using {len(users['sessions'])} accounts...")
            
            # Report using all available sessions
            total_channel_success = 0
            total_message_success = 0
            total_fail_count = 0
            working_sessions = 0
            pending_joins = 0
            
            logger.info(f"Found {len(users['sessions'])} reporting accounts to use")
            for phone, session_data in users["sessions"].items():
                logger.debug(f"Using session for phone: {phone}")
                client = None
                try:
                    # Get session path - use phone number as fallback
                    session_path = session_data.get('session_path', phone)
                    
                    # Create client with session data
                    client = TelegramClient(session_path, API_ID, API_HASH)
                    await client.connect()
                    logger.debug(f"Connected client for phone: {phone}")
                    
                    # Check if session is authorized
                    if await client.is_user_authorized():
                        logger.debug(f"Session {phone} is authorized")
                        
                        # For invite links, need to join first
                        if entity_id.startswith('+'):
                            peer, join_status = await join_private_chat(client, entity_id)
                            
                            if join_status == 'joined' or join_status == 'already_joined':
                                # Successfully joined or already a member, can report
                                logger.info(f"Successfully joined or already in chat, proceeding with reports")
                                channel_success, message_success = await report_channel_and_messages(client, peer, category, attempts=10)
                                
                                if channel_success > 0 or message_success > 0:
                                    total_channel_success += channel_success
                                    total_message_success += message_success
                                    working_sessions += 1
                                    await event.respond(f"Session {phone}: reported channel {channel_success} times and messages {message_success} times")
                                else:
                                    logger.warning(f"Failed to report private chat using session {phone}")
                                    total_fail_count += 20  # Both channel and message reports failed
                                    
                            elif join_status == 'pending':
                                # Join request is pending admin approval
                                pending_joins += 1
                                logger.info(f"Join request is pending for session {phone}")
                                await event.respond(f"Session {phone}: Join request is pending admin approval")
                                
                            else:
                                # Error joining
                                logger.error(f"Error joining private chat with session {phone}")
                                total_fail_count += 20
                                await event.respond(f"Session {phone}: Error joining private chat")
                                
                        elif entity_id.startswith('@'):
                            # Regular channel or user, try to report directly
                            try:
                                entity = await client.get_entity(entity_id)
                                logger.debug(f"Entity resolved: {entity}")
                                
                                # Report both channel and messages
                                channel_success, message_success = await report_channel_and_messages(client, entity, category, attempts=10)
                                
                                if channel_success > 0 or message_success > 0:
                                    total_channel_success += channel_success
                                    total_message_success += message_success
                                    working_sessions += 1
                                    await event.respond(f"Session {phone}: reported channel {channel_success} times and messages {message_success} times")
                                else:
                                    logger.warning(f"Failed to report using resolved entity for session {phone}")
                                    total_fail_count += 20
                                
                            except Exception as inner_e:
                                logger.error(f"Error resolving entity: {str(inner_e)}", exc_info=True)
                                # Try direct string reporting as fallback
                                try:
                                    channel_success = await send_report(client, entity_id, category, attempts=10)
                                    if channel_success > 0:
                                        total_channel_success += channel_success
                                        working_sessions += 1
                                        await event.respond(f"Session {phone}: reported using string entity {channel_success} times")
                                    else:
                                        logger.warning(f"Failed to report using string entity for session {phone}")
                                        total_fail_count += 20
                                except Exception as e:
                                    logger.error(f"Error reporting with string entity: {str(e)}", exc_info=True)
                                    total_fail_count += 20
                    else:
                        logger.warning(f"Session {phone} is not authorized - skipping")
                        await event.respond(f"Session {phone} is not authorized - skipping")
                except Exception as e:
                    logger.error(f"Error with session {phone}: {str(e)}", exc_info=True)
                    await event.respond(f"Error with session {phone}: {str(e)}")
                    total_fail_count += 20
                finally:
                    if client:
                        await client.disconnect()
            
            summary = f"Report complete:\n"
            summary += f"• {total_channel_success} successful channel reports\n"
            summary += f"• {total_message_success} successful message reports\n"
            summary += f"• {working_sessions} working accounts used\n"
            
            if pending_joins > 0:
                summary += f"• {pending_joins} accounts with pending join requests\n"
                summary += "Note: For accounts with pending join requests, please wait for admin approval and run the report command again later.\n"
                
            summary += f"• {total_fail_count} failed attempts"
            
            logger.info(summary.replace('\n', ' '))
            await event.respond(summary)
            
        except Exception as e:
            logger.error(f"Error in report handling: {str(e)}", exc_info=True)
            await event.respond(f"Error: {str(e)}\nPlease use the format: /report <channel/group link> <category>")

    async def on_addacc(self, event):
        """Handle adding a new account"""
        user_id = str(event.sender_id)
        text = event.raw_text.strip()
        logger.info(f"User {user_id} sent addacc command: {text}")
        
        if user_id not in users["users"]:
            logger.warning(f"Unregistered user {user_id} tried to use addacc command")
            await event.respond('Please register first. Use /register <your_name>')
            return
            
        try:
            parts = event.raw_text.strip().split(' ', 1)
            if len(parts) < 2:
                logger.warning(f"User {user_id} sent invalid addacc format")
                await event.respond("Please use the format: /addacc <phone number>")
                return
                
            _, phone = parts
            logger.debug(f"Phone number to add: {phone}")
            
            # Start the authentication process
            self.pending_actions[user_id] = {"action": "waiting_api_id", "phone": phone}
            logger.info(f"Started authentication process for user {user_id}, phone {phone}")
            await event.respond("Please enter your API ID (get from https://my.telegram.org):")
            
        except Exception as e:
            logger.error(f"Error in addacc handling: {str(e)}", exc_info=True)
            await event.respond(f"Error: {str(e)}")

    async def on_message(self, event):
        """Handle regular messages for multi-step processes"""
        if event.is_private:
            user_id = str(event.sender_id)
            text = event.raw_text.strip()
            
            if user_id in self.pending_actions:
                action = self.pending_actions[user_id]["action"]
                phone = self.pending_actions[user_id]["phone"]
                logger.debug(f"Processing message from user {user_id} with pending action {action}")
                
                if action == "waiting_api_id":
                    logger.debug(f"User {user_id} provided API ID: {text}")
                    api_id = text
                    if not api_id.isdigit():
                        logger.warning(f"User {user_id} provided invalid API ID: {api_id}")
                        await event.respond("API ID should be a number. Please try again:")
                        return
                        
                    self.pending_actions[user_id]["api_id"] = api_id
                    self.pending_actions[user_id]["action"] = "waiting_api_hash"
                    logger.info(f"User {user_id} provided valid API ID, now waiting for API hash")
                    await event.respond("Please enter your API Hash:")
                    
                elif action == "waiting_api_hash":
                    logger.debug(f"User {user_id} provided API hash")
                    api_hash = text
                    api_id = self.pending_actions[user_id]["api_id"]
                    
                    # Store the API hash in the pending actions
                    self.pending_actions[user_id]["api_hash"] = api_hash
                    logger.debug(f"Stored API hash for user {user_id}")
                    
                    # Start the client and send code
                    try:
                        logger.debug(f"Creating client for phone {phone}")
                        client = TelegramClient(f"{phone}", api_id, api_hash)
                        await client.connect()
                        logger.debug(f"Connected client for phone {phone}")
                        
                        if not await client.is_user_authorized():
                            logger.debug(f"Client for phone {phone} is not authorized, sending code request")
                            await client.send_code_request(phone)
                            self.pending_actions[user_id]["action"] = "waiting_code"
                            self.pending_actions[user_id]["client"] = client
                            logger.info(f"Sent verification code to phone {phone}")
                            await event.respond("Verification code sent. Please enter the code you received:")
                        else:
                            logger.info(f"Client for phone {phone} is already authorized")
                            users["sessions"][phone] = {
                                "api_id": api_id,
                                "api_hash": api_hash
                            }
                            save_users()
                            logger.info(f"Account {phone} added successfully")
                            await event.respond(f"Account {phone} added successfully.")
                            del self.pending_actions[user_id]
                            await client.disconnect()
                            logger.debug(f"Disconnected client for phone {phone}")
                    
                    except Exception as e:
                        logger.error(f"Error in client creation for phone {phone}: {str(e)}", exc_info=True)
                        await event.respond(f"Error: {str(e)}")
                        del self.pending_actions[user_id]
                        
                elif action == "waiting_code":
                    logger.debug(f"User {user_id} provided verification code")
                    code = text
                    client = self.pending_actions[user_id]["client"]
                    
                    # Make sure we have both api_id and api_hash in pending_actions
                    if "api_id" not in self.pending_actions[user_id] or "api_hash" not in self.pending_actions[user_id]:
                        logger.error(f"Missing API credentials for user {user_id}")
                        await event.respond("Error: API credentials missing. Please try again with /addacc.")
                        del self.pending_actions[user_id]
                        await client.disconnect()
                        return
                    
                    api_id = self.pending_actions[user_id]["api_id"]
                    api_hash = self.pending_actions[user_id]["api_hash"]
                    
                    try:
                        logger.debug(f"Signing in with code for phone {phone}")
                        await client.sign_in(phone, code)
                        users["sessions"][phone] = {
                            "api_id": api_id,
                            "api_hash": api_hash
                        }
                        save_users()
                        logger.info(f"Account {phone} added successfully")
                        await event.respond(f"Account {phone} added successfully.")
                        del self.pending_actions[user_id]
                        await client.disconnect()
                        logger.debug(f"Disconnected client for phone {phone}")
                        
                    except SessionPasswordNeededError:
                        logger.info(f"Two-step verification required for phone {phone}")
                        self.pending_actions[user_id]["action"] = "waiting_2fa"
                        await event.respond("Two-step verification is enabled. Please enter your password:")
                        
                    except Exception as e:
                        logger.error(f"Error signing in with code for phone {phone}: {str(e)}", exc_info=True)
                        await event.respond(f"Error: {str(e)}")
                        del self.pending_actions[user_id]
                        await client.disconnect()
                        
                elif action == "waiting_2fa":
                    logger.debug(f"User {user_id} provided 2FA password")
                    password = text
                    client = self.pending_actions[user_id]["client"]
                    
                    # Make sure we have both api_id and api_hash in pending_actions
                    if "api_id" not in self.pending_actions[user_id] or "api_hash" not in self.pending_actions[user_id]:
                        logger.error(f"Missing API credentials for user {user_id}")
                        await event.respond("Error: API credentials missing. Please try again with /addacc.")
                        del self.pending_actions[user_id]
                        await client.disconnect()
                        return
                    
                    api_id = self.pending_actions[user_id]["api_id"]
                    api_hash = self.pending_actions[user_id]["api_hash"]
                    
                    try:
                        logger.debug(f"Signing in with 2FA password for phone {phone}")
                        await client.sign_in(password=password)
                        users["sessions"][phone] = {
                            "api_id": api_id,
                            "api_hash": api_hash
                        }
                        save_users()
                        logger.info(f"Account {phone} added successfully with 2FA")
                        await event.respond(f"Account {phone} added successfully.")
                        del self.pending_actions[user_id]
                        await client.disconnect()
                        logger.debug(f"Disconnected client for phone {phone}")
                        
                    except Exception as e:
                        logger.error(f"Error signing in with 2FA password for phone {phone}: {str(e)}", exc_info=True)
                        await event.respond(f"Error: {str(e)}")
                        del self.pending_actions[user_id]
                        await client.disconnect()

async def report_channel_and_messages(client, peer, category, attempts=10):
    """
    Send reports for both the channel itself and its messages
    Returns tuple of (channel_reports_success, message_reports_success)
    """
    logger.debug(f"Reporting both channel and messages for peer: {peer}, category: {category}")
    
    # First report the channel/group itself
    channel_success = await send_report(client, peer, category, attempts)
    logger.info(f"Channel report success count: {channel_success}")
    
    # Then report recent messages in the channel/group
    message_success = 0
    try:
        # Get recent messages to report
        messages = await client.get_messages(peer, limit=10)
        if messages and len(messages) > 0:
            logger.debug(f"Found {len(messages)} messages to report")
            
            # Create appropriate reason object based on category
            if category == 'spam':
                reason = types.InputReportReasonSpam()
            elif category == 'violence':
                reason = types.InputReportReasonViolence()
            elif category == 'pornography':
                reason = types.InputReportReasonPornography()
            elif category == 'illegal_drugs':
                reason = types.InputReportReasonIllegalDrugs()
            elif category == 'personal_details':
                reason = types.InputReportReasonPersonalDetails()
            else:  # other
                reason = types.InputReportReasonOther()
            
            # Report each message individually
            for message in messages[:10]:  # Limit to 10 messages
                for attempt in range(attempts):
                    try:
                        msg_id = message.id
                        try:
                            result = await client(functions.messages.ReportRequest(
                                peer=peer,
                                id=[msg_id],
                                reason=reason,
                                message=f'Reporting {category}'
                            ))
                            logger.info(f"Successfully reported message {msg_id}, attempt {attempt+1}")
                            message_success += 1
                            break  # Successfully reported this message, move to next
                        except Exception as report_err:
                            logger.error(f"Error reporting message {msg_id}: {str(report_err)}")
                            # Try with account.reportPeer as fallback
                            try:
                                result = await client(functions.account.ReportPeerRequest(
                                    peer=peer,
                                    reason=reason,
                                    message=f'Reporting message {msg_id} for {category}'
                                ))
                                logger.info(f"Successfully reported message {msg_id} using fallback, attempt {attempt+1}")
                                message_success += 1
                                break
                            except Exception as simplified_err:
                                logger.error(f"Error with fallback report for message {msg_id}: {str(simplified_err)}")
                                # Continue to next attempt
                    except Exception as e:
                        logger.error(f"Error in message report loop: {str(e)}")
                    # Small delay between attempts
                    await asyncio.sleep(0.2)
        else:
            logger.warning(f"No messages found to report for peer {peer}")
    except Exception as e:
        logger.error(f"Error getting or reporting messages: {str(e)}", exc_info=True)
    
    logger.info(f"Message report success count: {message_success}")
    return channel_success, message_success

async def join_private_chat(client, entity_id):
    """
    Attempts to join a private chat, handles pending request scenarios
    Returns a tuple of (peer, join_status)
    where join_status can be: 'joined', 'pending', 'already_joined', 'error'
    """
    try:
        logger.debug(f"Attempting to join private chat with invite {entity_id}")
        
        # Try to resolve the invite link first
        invite_info = await client(functions.messages.CheckChatInviteRequest(
            hash=entity_id.lstrip('+')
        ))
        logger.debug(f"Invite info: {invite_info}")
        
        # If we already have chat info, we're already a member
        if hasattr(invite_info, 'chat'):
            logger.debug(f"Already a member of the chat: {invite_info.chat.id}")
            return invite_info.chat, 'already_joined'
        
        # Try to join the chat
        try:
            updates = await client(functions.messages.ImportChatInviteRequest(
                hash=entity_id.lstrip('+')
            ))
            logger.debug(f"Joined chat: {updates}")
            
            # Extract the peer from the updates
            peer = None
            for update in updates.updates:
                if hasattr(update, 'message') and hasattr(update.message, 'peer_id'):
                    peer = update.message.peer_id
                    break
                elif hasattr(update, 'chat_id'):
                    peer = await client.get_entity(update.chat_id)
                    break
            
            # If we found a chat in the updates object directly
            if not peer and hasattr(updates, 'chats') and updates.chats:
                peer = updates.chats[0]
                logger.debug(f"Got peer from updates.chats: {peer.id}")
            
            if peer:
                return peer, 'joined'
            else:
                logger.error("Failed to extract peer information after join")
                return None, 'error'
                
        except InviteRequestSentError:
            # Admin approval is required to join
            logger.info("Join request sent, waiting for admin approval")
            return None, 'pending'
            
        except UserAlreadyParticipantError:
            # Already a member
            try:
                # Try to get the chat entity directly
                chat = await client.get_entity(f"https://t.me/{entity_id}")
                return chat, 'already_joined'
            except Exception as e:
                logger.error(f"Error getting entity after UserAlreadyParticipantError: {str(e)}")
                return None, 'error'
                
        except FloodWaitError as e:
            # Rate limited
            logger.warning(f"FloodWaitError while joining chat: {str(e)}")
            return None, 'error'
            
    except Exception as e:
        logger.error(f"Error joining private chat: {str(e)}", exc_info=True)
        return None, 'error'

# Main entry point
if __name__ == "__main__":
    # Auto-detect sessions at startup
    session_count = load_session_files()
    logger.info(f"Auto-detected {session_count} session files at startup")
    
    logger.info("Starting ReportBot application")
    bot = ReportBot(API_ID, API_HASH, BOT_TOKEN)
    
    # Run the bot
    asyncio.run(bot.start())
