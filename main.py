from pymongo import MongoClient
from datetime import datetime
from termcolor import colored
import hashlib
import getpass
import re
from bson import ObjectId

# Connection to MongoDB
cluster = MongoClient("")
db_messages = cluster["socialmedia"]["bandar"]
db_users = cluster["socialmedia"]["users"]
db_groups = cluster["socialmedia"]["groups"]

# Global variable to store current user
current_user = None

def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_username(username):
    """Validate username format"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 20:
        return False, "Username must be no more than 20 characters long"
    if not re.match("^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"
    return True, ""

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if len(password) > 50:
        return False, "Password must be no more than 50 characters long"
    return True, ""

def register_user():
    """Register a new user"""
    print(colored("\n=== USER REGISTRATION ===", 'blue', attrs=['bold']))
    
    while True:
        username = input(colored("Enter username: ", 'green')).strip()
        if not username:
            print(colored("Username cannot be empty!", 'red'))
            continue
            
        valid, message = validate_username(username)
        if not valid:
            print(colored(message, 'red'))
            continue
            
        # Check if username already exists
        if db_users.find_one({"username": username}):
            print(colored("Username already exists! Please choose another.", 'red'))
            continue
            
        break
    
    while True:
        password = getpass.getpass(colored("Enter password: ", 'green'))
        if not password:
            print(colored("Password cannot be empty!", 'red'))
            continue
            
        valid, message = validate_password(password)
        if not valid:
            print(colored(message, 'red'))
            continue
            
        confirm_password = getpass.getpass(colored("Confirm password: ", 'green'))
        if password != confirm_password:
            print(colored("Passwords do not match!", 'red'))
            continue
            
        break
    
    # Get additional user info
    full_name = input(colored("Enter full name (optional): ", 'green')).strip()
    
    try:
        # Create user document
        user_doc = {
            "username": username,
            "password": hash_password(password),
            "full_name": full_name if full_name else username,
            "created_at": datetime.now(),
            "last_login": None
        }
        
        result = db_users.insert_one(user_doc)
        if result.inserted_id:
            print(colored("Registration successful! You can now log in.", 'green'))
            return True
        else:
            print(colored("Registration failed! Please try again.", 'red'))
            return False
            
    except Exception as e:
        print(colored(f"Error during registration: {e}", 'red'))
        return False

def login_user():
    """Login an existing user"""
    global current_user
    
    print(colored("\n=== USER LOGIN ===", 'blue', attrs=['bold']))
    
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        username = input(colored("Username: ", 'green')).strip()
        if not username:
            print(colored("Username cannot be empty!", 'red'))
            continue
            
        password = getpass.getpass(colored("Password: ", 'green'))
        if not password:
            print(colored("Password cannot be empty!", 'red'))
            continue
        
        try:
            # Find user in database
            user = db_users.find_one({"username": username})
            
            if user and user["password"] == hash_password(password):
                # Update last login
                db_users.update_one(
                    {"username": username},
                    {"$set": {"last_login": datetime.now()}}
                )
                
                current_user = {
                    "username": username,
                    "full_name": user.get("full_name", username)
                }
                
                print(colored(f"Welcome back, {current_user['full_name']}!", 'green'))
                return True
            else:
                attempts += 1
                remaining = max_attempts - attempts
                if remaining > 0:
                    print(colored(f"Invalid credentials! {remaining} attempts remaining.", 'red'))
                else:
                    print(colored("Too many failed attempts! Please try again later.", 'red'))
                    
        except Exception as e:
            print(colored(f"Login error: {e}", 'red'))
            attempts += 1
    
    return False

def logout_user():
    """Logout current user"""
    global current_user
    if current_user:
        print(colored(f"Goodbye, {current_user['full_name']}!", 'yellow'))
        current_user = None
    else:
        print(colored("No user is currently logged in.", 'yellow'))

# GROUP CHAT FUNCTIONS

def create_group():
    """Create a new group chat"""
    if not current_user:
        print(colored("Please log in to create groups.", 'red'))
        return
    
    print(colored("\n=== CREATE GROUP CHAT ===", 'blue', attrs=['bold']))
    
    # Get group name
    while True:
        group_name = input(colored("Enter group name: ", 'green')).strip()
        if not group_name:
            print(colored("Group name cannot be empty!", 'red'))
            continue
        if len(group_name) > 50:
            print(colored("Group name must be 50 characters or less!", 'red'))
            continue
        
        # Check if group name already exists
        if db_groups.find_one({"name": group_name}):
            print(colored("Group name already exists! Please choose another.", 'red'))
            continue
        break
    
    # Get group description
    description = input(colored("Enter group description (optional): ", 'green')).strip()
    
    # Get group type
    print(colored("\nGroup Types:", 'yellow'))
    print("1. Public (anyone can join)")
    print("2. Private (invite only)")
    
    while True:
        group_type = input(colored("Select group type (1-2): ", 'cyan'))
        if group_type == "1":
            is_private = False
            break
        elif group_type == "2":
            is_private = True
            break
        else:
            print(colored("Invalid option! Please select 1 or 2.", 'red'))
    
    try:
        # Create group document
        group_doc = {
            "name": group_name,
            "description": description,
            "created_by": current_user["username"],
            "admins": [current_user["username"]],
            "members": [current_user["username"]],
            "is_private": is_private,
            "created_at": datetime.now(),
            "message_count": 0
        }
        
        result = db_groups.insert_one(group_doc)
        if result.inserted_id:
            print(colored(f"Group '{group_name}' created successfully!", 'green'))
            print(colored(f"Group ID: {result.inserted_id}", 'blue'))
        else:
            print(colored("Failed to create group!", 'red'))
            
    except Exception as e:
        print(colored(f"Error creating group: {e}", 'red'))

def list_groups():
    """List all available groups"""
    if not current_user:
        print(colored("Please log in to view groups.", 'red'))
        return
    
    try:
        # Get all groups user is member of
        my_groups = list(db_groups.find({"members": current_user["username"]}))
        
        # Get public groups user is not member of
        public_groups = list(db_groups.find({
            "is_private": False,
            "members": {"$ne": current_user["username"]}
        }))
        
        print(colored("\n=== MY GROUPS ===", 'blue', attrs=['bold']))
        if my_groups:
            for group in my_groups:
                status = "Admin" if current_user["username"] in group.get("admins", []) else "Member"
                member_count = len(group.get("members", []))
                print(colored(f"• {group['name']}", 'green', attrs=['bold']))
                print(f"  Status: {colored(status, 'cyan')}")
                print(f"  Members: {member_count}")
                print(f"  Messages: {group.get('message_count', 0)}")
                if group.get("description"):
                    print(f"  Description: {group['description']}")
                print(f"  ID: {colored(str(group['_id']), 'blue')}")
                print()
        else:
            print(colored("You are not a member of any groups.", 'yellow'))
        
        print(colored("=== PUBLIC GROUPS (Available to Join) ===", 'blue', attrs=['bold']))
        if public_groups:
            for group in public_groups:
                member_count = len(group.get("members", []))
                print(colored(f"• {group['name']}", 'magenta', attrs=['bold']))
                print(f"  Members: {member_count}")
                print(f"  Messages: {group.get('message_count', 0)}")
                if group.get("description"):
                    print(f"  Description: {group['description']}")
                print(f"  ID: {colored(str(group['_id']), 'blue')}")
                print()
        else:
            print(colored("No public groups available to join.", 'yellow'))
            
    except Exception as e:
        print(colored(f"Error listing groups: {e}", 'red'))

def join_group():
    """Join a group chat"""
    if not current_user:
        print(colored("Please log in to join groups.", 'red'))
        return
    
    print(colored("\n=== JOIN GROUP ===", 'blue', attrs=['bold']))
    
    # Show available public groups
    try:
        public_groups = list(db_groups.find({
            "is_private": False,
            "members": {"$ne": current_user["username"]}
        }))
        
        if not public_groups:
            print(colored("No public groups available to join.", 'yellow'))
            return
        
        print(colored("Available Groups:", 'green'))
        for i, group in enumerate(public_groups, 1):
            member_count = len(group.get("members", []))
            print(f"{i}. {colored(group['name'], 'cyan')} ({member_count} members)")
            if group.get("description"):
                print(f"   {group['description']}")
        
        while True:
            try:
                choice = input(colored("\nSelect group number (or 'cancel' to exit): ", 'yellow'))
                if choice.lower() == 'cancel':
                    return
                
                choice = int(choice) - 1
                if 0 <= choice < len(public_groups):
                    selected_group = public_groups[choice]
                    break
                else:
                    print(colored("Invalid selection!", 'red'))
            except ValueError:
                print(colored("Please enter a valid number!", 'red'))
        
        # Add user to group
        result = db_groups.update_one(
            {"_id": selected_group["_id"]},
            {"$push": {"members": current_user["username"]}}
        )
        
        if result.modified_count > 0:
            print(colored(f"Successfully joined group '{selected_group['name']}'!", 'green'))
        else:
            print(colored("Failed to join group!", 'red'))
            
    except Exception as e:
        print(colored(f"Error joining group: {e}", 'red'))

def leave_group():
    """Leave a group chat"""
    if not current_user:
        print(colored("Please log in to leave groups.", 'red'))
        return
    
    print(colored("\n=== LEAVE GROUP ===", 'blue', attrs=['bold']))
    
    try:
        # Get user's groups
        my_groups = list(db_groups.find({"members": current_user["username"]}))
        
        if not my_groups:
            print(colored("You are not a member of any groups.", 'yellow'))
            return
        
        print(colored("Your Groups:", 'green'))
        for i, group in enumerate(my_groups, 1):
            status = "Admin" if current_user["username"] in group.get("admins", []) else "Member"
            print(f"{i}. {colored(group['name'], 'cyan')} ({status})")
        
        while True:
            try:
                choice = input(colored("\nSelect group number to leave (or 'cancel' to exit): ", 'yellow'))
                if choice.lower() == 'cancel':
                    return
                
                choice = int(choice) - 1
                if 0 <= choice < len(my_groups):
                    selected_group = my_groups[choice]
                    break
                else:
                    print(colored("Invalid selection!", 'red'))
            except ValueError:
                print(colored("Please enter a valid number!", 'red'))
        
        # Check if user is the only admin
        admins = selected_group.get("admins", [])
        if (current_user["username"] in admins and len(admins) == 1 and 
            len(selected_group.get("members", [])) > 1):
            print(colored("You are the only admin. Please promote another member to admin before leaving.", 'red'))
            return
        
        # Confirm leaving
        confirm = input(colored(f"Are you sure you want to leave '{selected_group['name']}'? (yes/no): ", 'yellow'))
        if confirm.lower() != 'yes':
            return
        
        # Remove user from group
        update_query = {
            "$pull": {
                "members": current_user["username"],
                "admins": current_user["username"]
            }
        }
        
        result = db_groups.update_one({"_id": selected_group["_id"]}, update_query)
        
        if result.modified_count > 0:
            print(colored(f"Successfully left group '{selected_group['name']}'.", 'green'))
            
            # If no members left, delete the group
            updated_group = db_groups.find_one({"_id": selected_group["_id"]})
            if not updated_group.get("members"):
                db_groups.delete_one({"_id": selected_group["_id"]})
                print(colored("Group was empty and has been deleted.", 'yellow'))
        else:
            print(colored("Failed to leave group!", 'red'))
            
    except Exception as e:
        print(colored(f"Error leaving group: {e}", 'red'))

def send_group_message():
    """Send a message to a group"""
    if not current_user:
        print(colored("Please log in to send group messages.", 'red'))
        return
    
    try:
        # Get user's groups
        my_groups = list(db_groups.find({"members": current_user["username"]}))
        
        if not my_groups:
            print(colored("You are not a member of any groups.", 'yellow'))
            return
        
        print(colored("\n=== SEND GROUP MESSAGE ===", 'blue', attrs=['bold']))
        print(colored("Your Groups:", 'green'))
        
        for i, group in enumerate(my_groups, 1):
            member_count = len(group.get("members", []))
            print(f"{i}. {colored(group['name'], 'cyan')} ({member_count} members)")
        
        while True:
            try:
                choice = input(colored("\nSelect group number (or 'cancel' to exit): ", 'yellow'))
                if choice.lower() == 'cancel':
                    return
                
                choice = int(choice) - 1
                if 0 <= choice < len(my_groups):
                    selected_group = my_groups[choice]
                    break
                else:
                    print(colored("Invalid selection!", 'red'))
            except ValueError:
                print(colored("Please enter a valid number!", 'red'))
        
        # Get message
        message = input(colored(f"Message for '{selected_group['name']}': ", 'green'))
        if not message.strip():
            print(colored("Message cannot be empty!", 'red'))
            return
        
        # Create message document
        current_time = datetime.now()
        msg = {
            "id": current_user["username"],
            "sender_name": current_user["full_name"],
            "message": message.strip(),
            "group_id": selected_group["_id"],
            "group_name": selected_group["name"],
            "message_type": "group",
            "date": current_time.strftime("%x"),
            "time": current_time.strftime("%X"),
            "timestamp": current_time
        }
        
        # Insert message
        result = db_messages.insert_one(msg)
        if result.inserted_id:
            # Update group message count
            db_groups.update_one(
                {"_id": selected_group["_id"]},
                {"$inc": {"message_count": 1}}
            )
            print(colored("Group message sent successfully!", 'green'))
        else:
            print(colored("Failed to send message!", 'red'))
            
    except Exception as e:
        print(colored(f"Error sending group message: {e}", 'red'))

def view_group_messages():
    """View messages from a specific group"""
    if not current_user:
        print(colored("Please log in to view group messages.", 'red'))
        return
    
    try:
        # Get user's groups
        my_groups = list(db_groups.find({"members": current_user["username"]}))
        
        if not my_groups:
            print(colored("You are not a member of any groups.", 'yellow'))
            return
        
        print(colored("\n=== VIEW GROUP MESSAGES ===", 'blue', attrs=['bold']))
        print(colored("Your Groups:", 'green'))
        
        for i, group in enumerate(my_groups, 1):
            member_count = len(group.get("members", []))
            message_count = group.get("message_count", 0)
            print(f"{i}. {colored(group['name'], 'cyan')} ({member_count} members, {message_count} messages)")
        
        while True:
            try:
                choice = input(colored("\nSelect group number (or 'cancel' to exit): ", 'yellow'))
                if choice.lower() == 'cancel':
                    return
                
                choice = int(choice) - 1
                if 0 <= choice < len(my_groups):
                    selected_group = my_groups[choice]
                    break
                else:
                    print(colored("Invalid selection!", 'red'))
            except ValueError:
                print(colored("Please enter a valid number!", 'red'))
        
        # Get group messages
        group_messages = db_messages.find({
            "group_id": selected_group["_id"]
        }).sort([("timestamp", 1)])
        
        print(colored(f"\n=== {selected_group['name'].upper()} MESSAGES ===", 'blue', attrs=['bold']))
        
        message_count = 0
        today = datetime.now().strftime("%x")
        
        for message in group_messages:
            try:
                msg_date = message["date"]
                msg_time = message["time"]
                sender = message["id"]
                
                if today == msg_date:
                    date_display = f"Today - {msg_time}"
                else:
                    date_display = f"{msg_date} - {msg_time}"
                
                print(colored(date_display, 'red'))
                
                # Highlight current user's messages
                if sender == current_user["username"]:
                    print(colored("From: ", 'green'), colored(f"{sender} (You)", 'cyan', attrs=['bold']))
                else:
                    print(colored("From: ", 'green'), colored(sender, 'cyan'))
                    
                print(colored("Message: ", 'green'), message["message"])
                print("---------------------------------------------------------------")
                message_count += 1
                
            except KeyError:
                continue
        
        if message_count == 0:
            print(colored(f"No messages in '{selected_group['name']}' yet. Be the first to send one!", 'yellow'))
            
    except Exception as e:
        print(colored(f"Error viewing group messages: {e}", 'red'))

def display_messages():
    """Display all messages (both private and group)"""
    if not current_user:
        print(colored("Please log in to view messages.", 'red'))
        return
        
    try:
        # Get all messages (private and group messages user has access to)
        user_groups = list(db_groups.find({"members": current_user["username"]}))
        group_ids = [group["_id"] for group in user_groups]
        
        # Find messages: either no group_id (private) or in user's groups
        query = {
            "$or": [
                {"group_id": {"$exists": False}},  # Private messages
                {"group_id": {"$in": group_ids}}   # Group messages
            ]
        }
        
        all_messages = db_messages.find(query).sort([("timestamp", 1)])
        today = datetime.now().strftime("%x")
        
        print(colored("=== ALL MESSAGES ===", 'blue', attrs=['bold']))
        print()
        
        message_count = 0
        for message in all_messages:
            try:
                if not all(key in message for key in ["date", "time", "id", "message"]):
                    continue
                
                msg_date = message["date"]
                msg_time = message["time"]
                sender = message["id"]
                
                if today == msg_date:
                    date_display = f"Today - {msg_time}"
                else:
                    date_display = f"{msg_date} - {msg_time}"
                
                print(colored(date_display, 'red'))
                
                # Show message type and sender
                if "group_id" in message:
                    group_name = message.get("group_name", "Unknown Group")
                    print(colored("Group: ", 'magenta'), colored(group_name, 'magenta', attrs=['bold']))
                
                if sender == current_user["username"]:
                    print(colored("From: ", 'green'), colored(f"{sender} (You)", 'cyan', attrs=['bold']))
                else:
                    print(colored("From: ", 'green'), colored(sender, 'cyan'))
                    
                print(colored("Message: ", 'green'), message["message"])
                print("---------------------------------------------------------------")
                message_count += 1
                
            except KeyError as e:
                continue
        
        if message_count == 0:
            print(colored("No messages found. Start a conversation!", 'yellow'))
                
    except Exception as e:
        print(colored(f"Error retrieving messages: {e}", 'red'))

def add_message():
    """Add a new private message to the database"""
    if not current_user:
        print(colored("Please log in to send messages.", 'red'))
        return
        
    try:
        message = input(colored("Private Message: ", 'green'))
        if not message.strip():
            print(colored("Message cannot be empty!", 'red'))
            return
        
        # Create message document (private message - no group_id)
        current_time = datetime.now()
        msg = {
            "id": current_user["username"],
            "sender_name": current_user["full_name"],
            "message": message.strip(),
            "message_type": "private",
            "date": current_time.strftime("%x"),
            "time": current_time.strftime("%X"),
            "timestamp": current_time
        }
        
        # Insert message
        result = db_messages.insert_one(msg)
        if result.inserted_id:
            print(colored("Private message sent successfully!", 'green'))
        else:
            print(colored("Failed to send message!", 'red'))
            
    except Exception as e:
        print(colored(f"Error adding message: {e}", 'red'))

def view_my_messages():
    """View only current user's messages"""
    if not current_user:
        print(colored("Please log in to view your messages.", 'red'))
        return
        
    try:
        my_messages = db_messages.find({"id": current_user["username"]}).sort([("timestamp", 1)])
        today = datetime.now().strftime("%x")
        
        print(colored(f"=== YOUR MESSAGES ===", 'blue', attrs=['bold']))
        print()
        
        message_count = 0
        for message in my_messages:
            try:
                msg_date = message["date"]
                msg_time = message["time"]
                
                if today == msg_date:
                    date_display = f"Today - {msg_time}"
                else:
                    date_display = f"{msg_date} - {msg_time}"
                
                print(colored(date_display, 'red'))
                
                # Show if it's a group message
                if "group_id" in message:
                    group_name = message.get("group_name", "Unknown Group")
                    print(colored("Group: ", 'magenta'), colored(group_name, 'magenta', attrs=['bold']))
                else:
                    print(colored("Type: ", 'blue'), colored("Private", 'blue'))
                
                print(colored("Message: ", 'green'), message["message"])
                print("---------------------------------------------------------------")
                message_count += 1
                
            except KeyError:
                continue
        
        if message_count == 0:
            print(colored("You haven't sent any messages yet.", 'yellow'))
            
    except Exception as e:
        print(colored(f"Error retrieving your messages: {e}", 'red'))

def group_menu():
    """Group management menu"""
    while True:
        print(colored("\n=== GROUP MANAGEMENT ===", 'blue', attrs=['bold']))
        print(colored("Options:", 'yellow'))
        print("1. Create new group")
        print("2. List groups")
        print("3. Join group")
        print("4. Leave group")
        print("5. Send group message")
        print("6. View group messages")
        print("7. Back to main menu")
        
        choice = input(colored("\nSelect option (1-7): ", 'cyan'))
        
        if choice == "1":
            create_group()
        elif choice == "2":
            list_groups()
        elif choice == "3":
            join_group()
        elif choice == "4":
            leave_group()
        elif choice == "5":
            send_group_message()
        elif choice == "6":
            view_group_messages()
        elif choice == "7":
            break
        else:
            print(colored("Invalid option! Please select 1-7.", 'red'))

def auth_menu():
    """Authentication menu for login/register"""
    print(colored("🔐 Authentication Required", 'blue', attrs=['bold']))
    print()
    
    while True:
        print(colored("Options:", 'yellow'))
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        
        choice = input(colored("\nSelect option (1-3): ", 'cyan'))
        
        if choice == "1":
            if login_user():
                return True
        elif choice == "2":
            register_user()
        elif choice == "3":
            return False
        else:
            print(colored("Invalid option! Please select 1, 2, or 3.", 'red'))

def main_menu():
    """Main menu for authenticated users"""
    print(colored(f"\n📱 Welcome to Simple Messaging System", 'blue', attrs=['bold']))
    print(colored(f"Logged in as: {current_user['full_name']}", 'green'))
    
    while True:
        print(colored("\nOptions:", 'yellow'))
        print("1. View all messages")
        print("2. View my messages")
        print("3. Send private message")
        print("4. Group chats")
        print("5. Logout")
        print("6. Exit")
        
        choice = input(colored("\nSelect option (1-6): ", 'cyan'))
        
        if choice == "1":
            display_messages()
        elif choice == "2":
            view_my_messages()
        elif choice == "3":
            add_message()
        elif choice == "4":
            group_menu()
        elif choice == "5":
            logout_user()
            return True  # Return to auth menu
        elif choice == "6":
            logout_user()
            return False  # Exit application
        else:
            print(colored("Invalid option! Please select 1-6.", 'red'))

def main():
    """Main function to run the messaging system"""
    print(colored("📱 Simple Messaging System with Group Chats", 'blue', attrs=['bold']))
    print(colored("Private messages and group conversations for authenticated users", 'cyan'))
    
    try:
        while True:
            if not current_user:
                # Show authentication menu
                if not auth_menu():
                    break
            else:
                # Show main menu
                if not main_menu():
                    break
                    
        print(colored("\nThank you for using Simple Messaging System! 👋", 'green'))
        
    except KeyboardInterrupt:
        print(colored("\n\nGoodbye! 👋", 'yellow'))
    except Exception as e:
        print(colored(f"\nUnexpected error: {e}", 'red'))

if __name__ == "__main__":
    main()