"""
Kuku Chat — terminal messaging app
Deps: pymongo bcrypt python-dotenv termcolor
  pip install pymongo bcrypt python-dotenv termcolor
"""

import hashlib
import getpass
import os
import re
import sys
from datetime import datetime

import bcrypt
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from termcolor import colored

load_dotenv()

# ── Config from .env ───────────────────────────────────────────────────────────
MONGO_URI   = os.getenv("MONGO_URI", "")
DB_NAME     = os.getenv("DB_NAME", "")
MSG_COL     = os.getenv("MSG_COLLECTION", "messages")
PAGE_SIZE   = int(os.getenv("PAGE_SIZE", 50))

if not MONGO_URI or not DB_NAME:
    print(colored("Error: MONGO_URI and DB_NAME must be set in your .env file.", 'red'))
    sys.exit(1)

try:
    cluster     = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    cluster.server_info()   # fail fast if unreachable
    db_messages = cluster[DB_NAME][MSG_COL]
    db_users    = cluster[DB_NAME]["users"]
    db_groups   = cluster[DB_NAME]["groups"]
except Exception as e:
    print(colored(f"Could not connect to MongoDB: {e}", 'red'))
    sys.exit(1)

current_user = None

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M:%S"


# ── Auth helpers ───────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def validate_username(username: str) -> tuple[bool, str]:
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(username) > 20:
        return False, "Username must be 20 characters or fewer."
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if len(password) > 50:
        return False, "Password must be 50 characters or fewer."
    return True, ""


# ── Display helpers ────────────────────────────────────────────────────────────
def fmt_time(date_str: str, time_str: str) -> str:
    today = datetime.now().strftime(DATE_FMT)
    if date_str == today:
        return f"Today {time_str}"
    return f"{date_str} {time_str}"


def print_message(message: dict, own_username: str):
    sender    = message.get("id", "?")
    date_disp = fmt_time(message.get("date", ""), message.get("time", ""))
    msg_type  = message.get("message_type", "")

    print(colored(date_disp, 'red'))

    if msg_type == "dm":
        recipient = message.get("recipient", "?")
        direction = f"{sender} -> {recipient}"
        print(colored("DM: ", 'magenta'), colored(direction, 'magenta', attrs=['bold']))
    elif msg_type == "group":
        print(colored("Group: ", 'magenta'),
              colored(message.get("group_name", "?"), 'magenta', attrs=['bold']))
    elif msg_type == "public":
        print(colored("[ Public Chat ]", 'white', attrs=['bold']))

    if sender == own_username:
        print(colored("From: ", 'green'), colored(f"{sender} (You)", 'cyan', attrs=['bold']))
    else:
        print(colored("From: ", 'green'), colored(sender, 'cyan'))

    print(colored("Message: ", 'green'), message["message"])
    print(colored(f"  [ID: {message['_id']}]", 'dark_grey') if '_id' in message else "")
    print("-" * 63)


# ── Registration ───────────────────────────────────────────────────────────────
def register_user():
    print(colored("\n=== USER REGISTRATION ===", 'blue', attrs=['bold']))

    while True:
        username = input(colored("Username: ", 'green')).strip()
        if not username:
            print(colored("Username cannot be empty.", 'red'))
            continue
        valid, msg = validate_username(username)
        if not valid:
            print(colored(msg, 'red'))
            continue
        if db_users.find_one({"username": username}):
            print(colored("Username already taken.", 'red'))
            continue
        break

    while True:
        password = getpass.getpass(colored("Password: ", 'green'))
        if not password:
            print(colored("Password cannot be empty.", 'red'))
            continue
        valid, msg = validate_password(password)
        if not valid:
            print(colored(msg, 'red'))
            continue
        confirm = getpass.getpass(colored("Confirm password: ", 'green'))
        if password != confirm:
            print(colored("Passwords do not match.", 'red'))
            continue
        break

    full_name = input(colored("Full name (optional): ", 'green')).strip()

    try:
        result = db_users.insert_one({
            "username":   username,
            "password":   hash_password(password),
            "full_name":  full_name or username,
            "created_at": datetime.now(),
            "last_login": None,
        })
        if result.inserted_id:
            print(colored("Registration successful. You can now log in.", 'green'))
            return True
        print(colored("Registration failed.", 'red'))
        return False
    except Exception as e:
        print(colored(f"Error: {e}", 'red'))
        return False


# ── Login / Logout ─────────────────────────────────────────────────────────────
def login_user():
    global current_user
    print(colored("\n=== LOGIN ===", 'blue', attrs=['bold']))

    for attempt in range(1, 4):
        username = input(colored("Username: ", 'green')).strip()
        if not username:
            print(colored("Username cannot be empty.", 'red'))
            continue

        password = getpass.getpass(colored("Password: ", 'green'))
        if not password:
            print(colored("Password cannot be empty.", 'red'))
            continue

        try:
            user = db_users.find_one({"username": username})
            if user and check_password(password, user["password"]):
                db_users.update_one({"username": username},
                                    {"$set": {"last_login": datetime.now()}})
                current_user = {
                    "username":  username,
                    "full_name": user.get("full_name", username),
                }
                print(colored(f"Welcome back, {current_user['full_name']}!", 'green'))
                return True

            remaining = 3 - attempt
            if remaining:
                print(colored(f"Invalid credentials. {remaining} attempt(s) remaining.", 'red'))
            else:
                print(colored("Too many failed attempts.", 'red'))
        except Exception as e:
            print(colored(f"Login error: {e}", 'red'))

    return False


def logout_user():
    global current_user
    if current_user:
        print(colored(f"Goodbye, {current_user['full_name']}!", 'yellow'))
        current_user = None
    else:
        print(colored("No user is currently logged in.", 'yellow'))


# ── Private DMs ────────────────────────────────────────────────────────────────
def send_dm():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    recipient_name = input(colored("Send DM to (username): ", 'green')).strip()
    if not recipient_name:
        return
    if recipient_name == current_user["username"]:
        print(colored("You cannot DM yourself.", 'red'))
        return
    if not db_users.find_one({"username": recipient_name}):
        print(colored(f"User '{recipient_name}' not found.", 'red'))
        return

    message = input(colored("Message: ", 'green')).strip()
    if not message:
        print(colored("Message cannot be empty.", 'red'))
        return

    now = datetime.now()
    result = db_messages.insert_one({
        "id":           current_user["username"],
        "sender_name":  current_user["full_name"],
        "recipient":    recipient_name,
        "message":      message,
        "message_type": "dm",
        "date":         now.strftime(DATE_FMT),
        "time":         now.strftime(TIME_FMT),
        "timestamp":    now,
    })
    if result.inserted_id:
        print(colored(f"DM sent to {recipient_name}.", 'green'))
    else:
        print(colored("Failed to send DM.", 'red'))


def view_dms():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    me = current_user["username"]
    messages = list(
        db_messages.find({
            "message_type": "dm",
            "$or": [{"id": me}, {"recipient": me}],
        })
        .sort("timestamp", 1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== YOUR DIRECT MESSAGES (last {PAGE_SIZE}) ===", 'blue', attrs=['bold']))
    if not messages:
        print(colored("No direct messages yet.", 'yellow'))
        return
    for msg in messages:
        print_message(msg, me)


# ── Delete message ─────────────────────────────────────────────────────────────
def delete_message():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    msg_id = input(colored("Message ID to delete: ", 'green')).strip()
    try:
        oid = ObjectId(msg_id)
    except Exception:
        print(colored("Invalid message ID.", 'red'))
        return

    msg = db_messages.find_one({"_id": oid})
    if not msg:
        print(colored("Message not found.", 'red'))
        return
    if msg.get("id") != current_user["username"]:
        print(colored("You can only delete your own messages.", 'red'))
        return

    confirm = input(colored("Delete this message? (yes/no): ", 'yellow'))
    if confirm.lower() != "yes":
        return

    db_messages.delete_one({"_id": oid})

    # Decrement group counter if applicable
    if msg.get("group_id"):
        db_groups.update_one({"_id": msg["group_id"]}, {"$inc": {"message_count": -1}})

    print(colored("Message deleted.", 'green'))


# ── Search messages ────────────────────────────────────────────────────────────
def search_messages():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    term = input(colored("Search term: ", 'green')).strip()
    if not term:
        return

    me         = current_user["username"]
    my_groups  = list(db_groups.find({"members": me}))
    group_ids  = [g["_id"] for g in my_groups]

    results = list(
        db_messages.find({
            "message": {"$regex": term, "$options": "i"},
            "$or": [
                {"id": me},
                {"recipient": me},
                {"group_id": {"$in": group_ids}},
            ],
        })
        .sort("timestamp", -1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== SEARCH RESULTS for '{term}' ===", 'blue', attrs=['bold']))
    if not results:
        print(colored("No messages found.", 'yellow'))
        return
    for msg in reversed(results):
        print_message(msg, me)


# ── Group functions ────────────────────────────────────────────────────────────
def create_group():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    print(colored("\n=== CREATE GROUP ===", 'blue', attrs=['bold']))

    while True:
        name = input(colored("Group name: ", 'green')).strip()
        if not name:
            print(colored("Name cannot be empty.", 'red'))
            continue
        if len(name) > 50:
            print(colored("Name must be 50 characters or fewer.", 'red'))
            continue
        if db_groups.find_one({"name": name}):
            print(colored("That name is already taken.", 'red'))
            continue
        break

    description = input(colored("Description (optional): ", 'green')).strip()

    print(colored("\n1. Public  2. Private", 'yellow'))
    while True:
        t = input(colored("Type (1/2): ", 'cyan'))
        if t == "1":
            is_private = False
            break
        if t == "2":
            is_private = True
            break
        print(colored("Enter 1 or 2.", 'red'))

    result = db_groups.insert_one({
        "name":          name,
        "description":   description,
        "created_by":    current_user["username"],
        "admins":        [current_user["username"]],
        "members":       [current_user["username"]],
        "is_private":    is_private,
        "created_at":    datetime.now(),
        "message_count": 0,
    })
    if result.inserted_id:
        print(colored(f"Group '{name}' created. ID: {result.inserted_id}", 'green'))
    else:
        print(colored("Failed to create group.", 'red'))


def list_groups():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    me          = current_user["username"]
    my_groups   = list(db_groups.find({"members": me}))
    avail       = list(db_groups.find({"is_private": False, "members": {"$ne": me}}))

    print(colored("\n=== MY GROUPS ===", 'blue', attrs=['bold']))
    if my_groups:
        for g in my_groups:
            role = "Admin" if me in g.get("admins", []) else "Member"
            print(colored(f"  {g['name']}", 'green', attrs=['bold']),
                  colored(f"[{role}]", 'cyan'),
                  f"{len(g.get('members', []))} members  |  {g.get('message_count', 0)} msgs")
            if g.get("description"):
                print(f"    {g['description']}")
            print(f"    ID: {colored(str(g['_id']), 'blue')}")
    else:
        print(colored("You are not in any groups.", 'yellow'))

    print(colored("\n=== AVAILABLE PUBLIC GROUPS ===", 'blue', attrs=['bold']))
    if avail:
        for g in avail:
            print(colored(f"  {g['name']}", 'magenta', attrs=['bold']),
                  f"{len(g.get('members', []))} members  |  {g.get('message_count', 0)} msgs")
            if g.get("description"):
                print(f"    {g['description']}")
            print(f"    ID: {colored(str(g['_id']), 'blue')}")
    else:
        print(colored("No public groups available.", 'yellow'))


def _pick_my_group(prompt="Select group: ") -> dict | None:
    """Helper — show numbered list of user's groups, return chosen one."""
    me     = current_user["username"]
    groups = list(db_groups.find({"members": me}))
    if not groups:
        print(colored("You are not in any groups.", 'yellow'))
        return None
    for i, g in enumerate(groups, 1):
        print(f"{i}. {colored(g['name'], 'cyan')} ({len(g.get('members', []))} members)")
    while True:
        choice = input(colored(prompt, 'yellow'))
        if choice.lower() == "cancel":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(groups):
                return groups[idx]
            print(colored("Invalid selection.", 'red'))
        except ValueError:
            print(colored("Enter a number or 'cancel'.", 'red'))


def join_group():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    me     = current_user["username"]
    avail  = list(db_groups.find({"is_private": False, "members": {"$ne": me}}))
    if not avail:
        print(colored("No public groups to join.", 'yellow'))
        return

    print(colored("\n=== JOIN GROUP ===", 'blue', attrs=['bold']))
    for i, g in enumerate(avail, 1):
        print(f"{i}. {colored(g['name'], 'cyan')} ({len(g.get('members', []))} members)")
        if g.get("description"):
            print(f"   {g['description']}")

    while True:
        choice = input(colored("Select number (or 'cancel'): ", 'yellow'))
        if choice.lower() == "cancel":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(avail):
                g = avail[idx]
                break
            print(colored("Invalid selection.", 'red'))
        except ValueError:
            print(colored("Enter a number.", 'red'))

    result = db_groups.update_one({"_id": g["_id"]}, {"$push": {"members": me}})
    if result.modified_count:
        print(colored(f"Joined '{g['name']}'.", 'green'))
    else:
        print(colored("Failed to join.", 'red'))


def leave_group():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    print(colored("\n=== LEAVE GROUP ===", 'blue', attrs=['bold']))
    g = _pick_my_group("Select group to leave (or 'cancel'): ")
    if not g:
        return

    me     = current_user["username"]
    admins = g.get("admins", [])

    if me in admins and len(admins) == 1 and len(g.get("members", [])) > 1:
        print(colored("You are the only admin. Promote someone else before leaving.", 'red'))
        return

    confirm = input(colored(f"Leave '{g['name']}'? (yes/no): ", 'yellow'))
    if confirm.lower() != "yes":
        return

    db_groups.update_one({"_id": g["_id"]},
                          {"$pull": {"members": me, "admins": me}})
    print(colored(f"Left '{g['name']}'.", 'green'))

    updated = db_groups.find_one({"_id": g["_id"]})
    if updated and not updated.get("members"):
        db_groups.delete_one({"_id": g["_id"]})
        print(colored("Group had no members left and was deleted.", 'yellow'))


def promote_to_admin():
    """Promote a group member to admin."""
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    print(colored("\n=== PROMOTE TO ADMIN ===", 'blue', attrs=['bold']))
    me = current_user["username"]

    # Only show groups where current user is admin
    admin_groups = list(db_groups.find({"admins": me}))
    if not admin_groups:
        print(colored("You are not an admin of any group.", 'yellow'))
        return

    for i, g in enumerate(admin_groups, 1):
        print(f"{i}. {colored(g['name'], 'cyan')}")

    while True:
        choice = input(colored("Select group (or 'cancel'): ", 'yellow'))
        if choice.lower() == "cancel":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(admin_groups):
                g = admin_groups[idx]
                break
            print(colored("Invalid selection.", 'red'))
        except ValueError:
            print(colored("Enter a number.", 'red'))

    members     = g.get("members", [])
    non_admins  = [m for m in members if m not in g.get("admins", [])]
    if not non_admins:
        print(colored("All members are already admins.", 'yellow'))
        return

    print(colored("Members eligible for promotion:", 'green'))
    for i, m in enumerate(non_admins, 1):
        print(f"{i}. {m}")

    while True:
        choice = input(colored("Select member to promote (or 'cancel'): ", 'yellow'))
        if choice.lower() == "cancel":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(non_admins):
                target = non_admins[idx]
                break
            print(colored("Invalid selection.", 'red'))
        except ValueError:
            print(colored("Enter a number.", 'red'))

    db_groups.update_one({"_id": g["_id"]}, {"$push": {"admins": target}})
    print(colored(f"'{target}' is now an admin of '{g['name']}'.", 'green'))


def send_group_message():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    print(colored("\n=== SEND GROUP MESSAGE ===", 'blue', attrs=['bold']))
    g = _pick_my_group("Select group (or 'cancel'): ")
    if not g:
        return

    message = input(colored(f"Message for '{g['name']}': ", 'green')).strip()
    if not message:
        print(colored("Message cannot be empty.", 'red'))
        return

    now    = datetime.now()
    result = db_messages.insert_one({
        "id":           current_user["username"],
        "sender_name":  current_user["full_name"],
        "message":      message,
        "group_id":     g["_id"],
        "group_name":   g["name"],
        "message_type": "group",
        "date":         now.strftime(DATE_FMT),
        "time":         now.strftime(TIME_FMT),
        "timestamp":    now,
    })
    if result.inserted_id:
        db_groups.update_one({"_id": g["_id"]}, {"$inc": {"message_count": 1}})
        print(colored("Message sent.", 'green'))
    else:
        print(colored("Failed to send message.", 'red'))


def view_group_messages():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    print(colored("\n=== VIEW GROUP MESSAGES ===", 'blue', attrs=['bold']))
    g = _pick_my_group("Select group (or 'cancel'): ")
    if not g:
        return

    messages = list(
        db_messages.find({"group_id": g["_id"]})
        .sort("timestamp", 1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== {g['name'].upper()} (last {PAGE_SIZE}) ===", 'blue', attrs=['bold']))
    if not messages:
        print(colored("No messages yet.", 'yellow'))
        return
    for msg in messages:
        print_message(msg, current_user["username"])


# ── Public chat ────────────────────────────────────────────────────────────────
def view_public_chat():
    """Read the global public chat — visible to all logged-in users."""
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    messages = list(
        db_messages.find({"message_type": "public"})
        .sort("timestamp", -1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== PUBLIC CHAT (last {PAGE_SIZE}) ===", 'blue', attrs=['bold']))
    if not messages:
        print(colored("No public messages yet. Be the first to post.", 'yellow'))
        return
    for msg in reversed(messages):
        print_message(msg, current_user["username"])


def send_public_message():
    """Post a message to the global public chat."""
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    message = input(colored("Public message: ", 'green')).strip()
    if not message:
        print(colored("Message cannot be empty.", 'red'))
        return

    now = datetime.now()
    result = db_messages.insert_one({
        "id":           current_user["username"],
        "sender_name":  current_user["full_name"],
        "message":      message,
        "message_type": "public",
        "date":         now.strftime(DATE_FMT),
        "time":         now.strftime(TIME_FMT),
        "timestamp":    now,
    })
    if result.inserted_id:
        print(colored("Message posted to public chat.", 'green'))
    else:
        print(colored("Failed to post message.", 'red'))


# ── All messages / my messages ─────────────────────────────────────────────────
def display_all_messages():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    me        = current_user["username"]
    group_ids = [g["_id"] for g in db_groups.find({"members": me})]

    messages = list(
        db_messages.find({
            "$or": [
                {"id": me, "message_type": "dm"},
                {"recipient": me, "message_type": "dm"},
                {"group_id": {"$in": group_ids}},
                {"message_type": "public"},
            ]
        })
        .sort("timestamp", 1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== ALL YOUR MESSAGES (last {PAGE_SIZE}) ===", 'blue', attrs=['bold']))
    if not messages:
        print(colored("No messages.", 'yellow'))
        return
    for msg in messages:
        print_message(msg, me)


def view_my_messages():
    if not current_user:
        print(colored("Please log in first.", 'red'))
        return

    me       = current_user["username"]
    messages = list(
        db_messages.find({"id": me})
        .sort("timestamp", 1)
        .limit(PAGE_SIZE)
    )

    print(colored(f"\n=== YOUR SENT MESSAGES (last {PAGE_SIZE}) ===", 'blue', attrs=['bold']))
    if not messages:
        print(colored("You have not sent any messages.", 'yellow'))
        return
    for msg in messages:
        print_message(msg, me)


# ── Menus ──────────────────────────────────────────────────────────────────────
def group_menu():
    while True:
        print(colored("\n=== GROUP MANAGEMENT ===", 'blue', attrs=['bold']))
        print("1. Create group")
        print("2. List groups")
        print("3. Join group")
        print("4. Leave group")
        print("5. Promote member to admin")
        print("6. Send group message")
        print("7. View group messages")
        print("8. Back")

        choice = input(colored("Select (1-8): ", 'cyan'))
        actions = {
            "1": create_group,
            "2": list_groups,
            "3": join_group,
            "4": leave_group,
            "5": promote_to_admin,
            "6": send_group_message,
            "7": view_group_messages,
        }
        if choice == "8":
            break
        elif choice in actions:
            actions[choice]()
        else:
            print(colored("Invalid option.", 'red'))


def auth_menu():
    print(colored("\nAuthentication Required", 'blue', attrs=['bold']))
    while True:
        print(colored("\n1. Login  2. Register  3. Exit", 'yellow'))
        choice = input(colored("Select (1-3): ", 'cyan'))
        if choice == "1":
            if login_user():
                return True
        elif choice == "2":
            register_user()
        elif choice == "3":
            return False
        else:
            print(colored("Invalid option.", 'red'))


def main_menu():
    print(colored(f"\nKuku Chat  |  {current_user['full_name']}", 'blue', attrs=['bold']))
    while True:
        print(colored("\n1.  All messages", 'yellow'))
        print("2.  My sent messages")
        print("3.  Public chat")
        print("4.  Post to public chat")
        print("5.  Direct messages")
        print("6.  Send DM")
        print("7.  Group chats")
        print("8.  Search messages")
        print("9.  Delete a message")
        print("10. Logout")
        print("11. Exit")

        choice = input(colored("Select (1-11): ", 'cyan'))
        actions = {
            "1":  display_all_messages,
            "2":  view_my_messages,
            "3":  view_public_chat,
            "4":  send_public_message,
            "5":  view_dms,
            "6":  send_dm,
            "7":  group_menu,
            "8":  search_messages,
            "9":  delete_message,
        }
        if choice == "10":
            logout_user()
            return True
        elif choice == "11":
            logout_user()
            return False
        elif choice in actions:
            actions[choice]()
        else:
            print(colored("Invalid option.", 'red'))


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    print(colored("Kuku Chat", 'blue', attrs=['bold']))
    print(colored("Terminal messaging with group chats and direct messages", 'cyan'))
    try:
        while True:
            if not current_user:
                if not auth_menu():
                    break
            else:
                if not main_menu():
                    break
        print(colored("\nGoodbye.", 'green'))
    except KeyboardInterrupt:
        print(colored("\nInterrupted.", 'yellow'))
    except Exception as e:
        print(colored(f"Unexpected error: {e}", 'red'))


if __name__ == "__main__":
    main()
