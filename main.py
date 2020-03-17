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

%s

"""

MESSAGE_CHANGE_TEMPLATE = \
    """%s обновил задачу %s:

%s

"""

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

    def create_issue_link(self, issue_id):
        return "[{0}]({1}/issue/{0})".format(issue_id, YOUTRACK_BASE_URL)

    def render_message(self, mention, comment):
        return MESSAGE_TEMPLATE % (mention,
                                   self.create_issue_link(comment['issueId']),
                                   comment['text'])

    def render_change_message(self, mention, issue, change):
        updated_tmpl = "- {0}: {1} -> {2}"
        updates = (updated_tmpl.format(field.name,
                                       field.old_value[
                                           0] if field.old_value else "n/a",
                                       field.new_value[0] if field.new_value else "n/a")
                   for field in change.fields)
        updates = "\n".join(updates)
        return MESSAGE_CHANGE_TEMPLATE % (mention,
                                          self.create_issue_link(issue['id']),
                                          updates)

    async def try_post_markdown(self, chat, message):
        try:
            await chat.send_text(message, parse_mode='Markdown')
        except BotApiError:
            self.logger.warning(
                "Cannot send message '%s' as markdown, resending as text",
                message)
            await chat.send_text(message)

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
            await self.try_post_markdown(chat, message)
            await db.set_comment_posted(conn, comment)

    async def post_change(self, issue, change):
        async with self.db_pool.acquire() as conn:
            project_id = issue['id'].split('-')[0]
            chat_id = await db.get_project_chat_id(conn, project_id)
            user = await db.get_user(conn, change.updater_name)
            mention = self.create_mention(user)
            message = self.render_change_message(mention, issue, change)
            self.logger.info("Posting issue %s change to chat %s",
                             issue['id'], chat_id)
            chat = self.bot.channel(chat_id)
            await self.try_post_markdown(chat, message)

    async def post_new_issue(self, issue):
        async with self.db_pool.acquire() as conn:
            project_id = issue['id'].split('-')[0]
            user = await db.get_user(conn, issue['reporterName'])
            chat_id = await db.get_project_chat_id(conn, project_id)
            mention = self.create_mention(user)
            issue_link = self.create_issue_link(issue['id'])
            summary = issue['summary']
            issue_type = issue['Type']
            assignee = issue.get('Assignee', None)
            assignee_mention = None
            if assignee:
                try:
                    assignee_mention = self.create_mention(
                        await db.get_user(conn, assignee))
                except:
                    self.logger.warning("Could not create assignee mention")

            if assignee_mention:
                message = f"{mention} создал задачу {issue_link}: {summary} с типом {issue_type}. Задача назначена на {assignee_mention}."
            else:
                message = f"{mention} создал задачу {issue_link}: {summary} с типом {issue_type}."
            chat = self.bot.channel(chat_id)
            await self.try_post_markdown(chat, message)

    async def check_issue(self, issue, last_updated):
        self.logger.info("Checking issue %s", issue['id'])
        last_checked = 0
        project_id = issue['id'].split('-')[0]
        async with self.db_pool.acquire() as conn:
            created = int(issue['created'])
            if created > last_updated:
                # new issue
                last_checked = max(last_checked, created)
                await self.post_new_issue(issue)
            if issue['commentsCount']:
                comments = await self.connection.get_comments(issue['id'])
                for comment in comments:
                    posted = await db.check_comment(conn, comment)
                    if posted:
                        continue
                    updated = comment.get(
                        'updated', comment.get('created', '0'))
                    updated = int(updated)
                    if updated <= last_updated:
                        self.logger.info(
                            'Skipping old comment %s', comment['id'])
                        continue
                    last_checked = max(last_checked, updated)
                    await self.post_comment(comment)
            changes = await self.connection.get_changes_for_issue(issue['id'])
            for change in changes:
                print(change)
                updated = int(change.updated)
                if updated <= last_updated:
                    self.logger.info(
                        'Skipping old change for issue %s', issue['id'])
                    continue
                last_checked = max(last_checked, updated)
                await self.post_change(issue, change)
            if last_checked > 0:
                last_checked = datetime.datetime.fromtimestamp(
                    last_checked / 1000)
                await db.set_last_updated(conn,
                                          project_id,
                                          last_checked)

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
                self.logger.info("Got %s issues in project %s",
                                 len(issues), project['youtrack_id'])
                current += limit
                issues_tasks = list(
                    self.check_issue(issue, timestamp * 1000)
                    for issue in issues)
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
