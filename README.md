# pytrack-tg-bot

This bot will get updates from your YouTrack instance and publish them to given
Telegram Chats. It uses Python 3, Asyncio and PostgreSQL to work.

## Feature set

At the moment, bot supports reporting about:
* New issues
* Issue updates
* Issue comments

## Configuration

All basic parameters are read from environment variables:

* YOUTRACK_BASE_URL - URL of your YouTrack instance
* YOUTRACK_LOGIN - your YouTrack login
* YOUTRACK_PASSWORD - your YouTrack password
* TELEGRAM_API_KEY - your Telegram API key from @BotFather bot
* POSTGRESQL_DSN - connection string to your database

Currently, bot requires admin privileges to import list of users into own
database.

When all basic parameters are set, you need to run bot for it to retrieve
information about projects and users. After that, fill in "tg_chat" field
of the "tracked_projects" table with corresponding Telegram Chat IDs.
You may also fill in "tg_id" field in "users" table, if you want the bot to
mention correct users.
