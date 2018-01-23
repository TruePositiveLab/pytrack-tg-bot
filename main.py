"""
Bot entry point
"""
import datetime
import asyncio
import ssl
import logging

import aiotools
import youtrack
import dotenv

from youtrack_aio import Connection
import db

from aiotg import Bot
from aiotg.bot import BotApiError


MESSAGE_TEMPLATE = \
    """%s написал комментарий к задаче %s:

%s"""

dotenv.load()

YOUTRACK_BASE_URL = dotenv.get("YOUTRACK_BASE_URL")
YOUTRACK_LOGIN = dotenv.get("YOUTRACK_LOGIN")
YOUTRACK_PASSWORD = dotenv.get("YOUTRACK_PASSWORD")
TELEGRAM_API_KEY = dotenv.get("TELEGRAM_API_KEY")
POSTGRESQL_DSN = dotenv.get("POSTGRESQL_DSN")


class PytrackTelegramBot(object):

    def __init__(self):
        self.connection = Connection(YOUTRACK_BASE_URL,
                                     login=YOUTRACK_LOGIN,
                                     password=YOUTRACK_PASSWORD)
        self.bot = Bot(TELEGRAM_API_KEY)
        self.db_pool = None
        self.update_timer = None
        self.logger = logging.getLogger('TG-bot')

    async def init(self):
        """
        Initializes app
        """
        self.logger.info("Initializing")
        self.db_pool = await db.create_pool(POSTGRESQL_DSN)
        projects = await self.connection.get_projects()
        _users = await self.connection.get_users()
        users = []
        for _user in _users:
            user = await self.connection.get_user(_user['login'])
            users.append((user['login'], user['fullName']))

        async with self.db_pool.acquire() as conn:
            await db.ensure_projects_are_present(conn, projects)
            await db.ensure_users_are_present(conn, users)

    async def run(self):
        self.logger.info("Starting timer")
        self.update_timer = aiotools.create_timer(
            self.check_for_updates, 300.0)

    async def shutdown(self):
        self.logger.info("Shutting down")
        self.update_timer.cancel()
        await self.update_timer

    def create_mention(self, user):
        if user['tg_id']:
            return "[%s](tg://user?id=%s)" % (user['full_name'], user['tg_id'])
        else:
            return "@%s" % user['youtrack_id']

    def render_message(self, mention, comment):
        issue_link = "[{0}]({1}/issue/{0})".format(
            comment['issueId'], YOUTRACK_BASE_URL)
        return MESSAGE_TEMPLATE % (mention, issue_link, comment['text'])

    async def post_comment(self, comment):
        async with self.db_pool.acquire() as conn:
            project_id = comment['issueId'].split('-')[0]
            chat_id = await db.get_project_chat_id(conn, project_id)
            user = await db.get_user(conn, comment['author'])
            mention = self.create_mention(user)
            message = self.render_message(mention, comment)
            self.logger.info("Posting comment %s to chat %s",
                             comment['id'], chat_id)
            chat = self.bot.channel(chat_id)
            try:
                await chat.send_text(message, parse_mode='Markdown')
            except BotApiError:
                self.logger.warning(
                    "Cannot send message '%s' as markdown", message)
                await chat.send_text(message)
            await db.set_comment_posted(conn, comment)

    async def check_issue(self, issue):
        self.logger.info("Checking issue %s", issue['id'])
        async with self.db_pool.acquire() as conn:
            comments = await self.connection.get_comments(issue['id'])
            last_checked = 0
            for comment in comments:
                posted = await db.check_comment(conn, comment)
                if posted:
                    continue
                updated = comment.get('updated', comment.get('created', '0'))
                updated = int(updated)
                last_checked = max(last_checked, updated)
                project_id = comment['issueId'].split('-')[0]
                await self.post_comment(comment)
            if last_checked > 0:
                last_checked = datetime.datetime.fromtimestamp(
                    last_checked / 1000)
                await db.set_last_updated(conn, project_id, last_checked)

    async def check_project(self, project, limit=50):
        self.logger.info("Checking project %s", project['youtrack_id'])
        try:
            timestamp = project['last_checked'].timestamp()
            current = 0
            while True:
                issues = await self.connection.get_issues(
                    project['youtrack_id'],
                    project['search_query'],
                    current, limit,
                    updated_after=int(
                        timestamp * 1000) if timestamp > 0 else None
                )
                current += limit
                issues_tasks = list(
                    self.check_issue(issue)
                    for issue in issues if int(issue['commentsCount']))
                if issues_tasks:
                    await asyncio.wait(issues_tasks)
                if len(issues) < limit:
                    break
        except ssl.SSLError:
            self.logger.exception('SSLError')
            return
        except youtrack.YouTrackException as ex:
            self.logger.exception('Youtrack exception')
            return

    async def check_for_updates(self, interval):
        """
        Iterates over projects looking for updated issues
        """
        self.logger.info("Checking projects for updates")
        try:
            async with self.db_pool.acquire() as conn:
                tasks = []
                for project in await db.get_projects(conn):
                    tasks.append(self.check_project(project))
                await asyncio.wait(tasks)
        except asyncio.CancelledError:
            self.logger.info("cancelled")
        self.logger.info("Done")


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s\t%(levelname)s\t%(message)s')
    loop = asyncio.get_event_loop()
    bot = PytrackTelegramBot()
    loop.run_until_complete(bot.init())
    loop.run_until_complete(bot.run())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(bot.shutdown())
    loop.close()


if __name__ == '__main__':
    main()
