# Kuku Chat

A terminal-based messaging application with user authentication, public chat, direct messages, and group chats. Built with Python and MongoDB.

---

## Features

- User registration and login with bcrypt password hashing
- Public chat visible to all logged-in users
- Direct messages between specific users
- Group chats with public and private modes
- Group admin roles, member management, and admin promotion
- Message search across your DMs and group chats
- Delete your own messages
- Color-coded terminal output
- Config loaded from a `.env` file — no hardcoded credentials
- Connection validated at startup

---

## Requirements

- Python 3.10+
- MongoDB (local or Atlas)

### Python dependencies

```
pymongo
bcrypt
python-dotenv
termcolor
```

Install with:

```bash
pip install pymongo bcrypt python-dotenv termcolor
```

---

## Setup

**1. Clone or download the project.**

**2. Create your `.env` file.**

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net
DB_NAME=your_database_name
MSG_COLLECTION=messages
PAGE_SIZE=50
```

For a local MongoDB instance use `mongodb://localhost:27017` as your URI.

**3. Run the application.**

```bash
python main.py
```

The app will verify the MongoDB connection before starting and exit immediately if it cannot connect or if the `.env` values are missing.

---
## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_URI` | Yes | — | MongoDB connection string |
| `DB_NAME` | Yes | — | Database name |
| `MSG_COLLECTION` | No | `messages` | Collection name for messages |
| `PAGE_SIZE` | No | `50` | Max messages shown per view |

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `users` | Registered user accounts |
| `messages` (or your `MSG_COLLECTION`) | All messages — public, DMs, and group |
| `groups` | Group metadata and membership |

All three collections are created automatically on first use.

---

## Message types

Each message stored in MongoDB has a `message_type` field:

| Type | Who can see it |
|---|---|
| `public` | All logged-in users |
| `dm` | Sender and recipient only |
| `group` | Members of that group only |

---

## Usage

On launch you are prompted to log in or register. After authenticating, the main menu gives you the following options.

### Main menu

| Option | Description |
|---|---|
| All messages | Combined feed of public messages, your DMs, and your group messages |
| My sent messages | Only messages you have sent, across all types |
| Public chat | Read the global public chat (last 50 messages) |
| Post to public chat | Post a message visible to all logged-in users |
| Direct messages | Read DMs sent to or from you |
| Send DM | Send a private message to a specific user by username |
| Group chats | Open the group management submenu |
| Search messages | Search by keyword across public, DM, and group messages |
| Delete a message | Delete one of your own messages by its ID |
| Logout | Return to the authentication screen |
| Exit | Close the application |

### Group management

| Option | Description |
|---|---|
| Create group | Create a public or private group |
| List groups | View your groups and available public groups |
| Join group | Join any public group |
| Leave group | Leave a group you are a member of |
| Promote member to admin | Give admin rights to another member of your group |
| Send group message | Post a message to a specific group |
| View group messages | Read all messages in a specific group (last 50) |

---

## Validation rules

**Username**
- 3 to 20 characters
- Letters, numbers, and underscores only
- Must be unique

**Password**
- 6 to 50 characters
- Stored as a bcrypt hash, never in plain text

**Login**
- 3 attempts allowed before lockout for that session

---

## Notes

- Passwords are hashed with bcrypt. If you have existing users registered with an older version of this app that used SHA-256, those users will need to re-register as the hashes are not compatible.
- Group admins cannot leave a group if they are the sole admin and other members remain. Use the "Promote member to admin" option first.
- Message IDs shown at the bottom of each message are MongoDB ObjectIds. Copy the ID to use the delete feature.
- Keep your `.env` file out of version control. Add it to `.gitignore` before pushing to GitHub.
