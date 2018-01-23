"""
Database utilites
"""
import glob

import asyncpg


async def _discover_migrations():
    pattern = __file__.replace("__init__.py", "*.sql")
    files = glob.glob(pattern)
    return sorted(files)


GET_CURRENT_VERSION_QUERY = "select max(last_version) from _service.dbversion"


INIT_VERSIONING_QUERIES = """
create schema _service;

create table _service.dbversion (
        last_version integer primary key,
        applied timestamp default current_timestamp);

commit;
"""


async def _init_versioning(conn):
    await conn.execute(INIT_VERSIONING_QUERIES)


async def _get_current_version(conn, try_init=True):
    try:
        ver = await conn.fetchrow(GET_CURRENT_VERSION_QUERY)
        return ver['max']
    except asyncpg.exceptions.PostgresError as ex:
        print(ex)
        if try_init:
            await _init_versioning(conn)
            return await _get_current_version(conn, False)
        else:
            raise


def _load_migration(migration):
    with open(migration, 'r') as migration_file:
        return migration_file.read()


def _load_query(query_name):
    return _load_migration(
        __file__.replace(
            '__init__.py', 'queries/%s.sql' % query_name))


async def _apply(conn, migration):
    query = _load_migration(migration)
    async with conn.transaction():
        await conn.execute(query)


WRITE_LAST_VERSION_QUERY = \
    "insert into _service.dbversion (last_version) values ($1)"


async def _write_last_version(conn, last_version):
    await conn.execute(WRITE_LAST_VERSION_QUERY, last_version)


async def _run_migrations(conn):
    migrations = await _discover_migrations()
    last_version = len(migrations)
    current_version = await _get_current_version(conn)
    migrations = migrations[current_version:]
    if migrations:
        for migration in migrations:
            await _apply(conn, migration)
        await _write_last_version(conn, last_version)


ENSURE_PROJECTS_ARE_PRESENT_QUERY = _load_query('upsert_project')


async def ensure_projects_are_present(conn, projects):
    """
    Upserts projects entries
    """
    async with conn.transaction():
        await conn.executemany(ENSURE_PROJECTS_ARE_PRESENT_QUERY,
                               projects.items())

ENSURE_USERS_ARE_PRESENT_QUERY = _load_query('upsert_users')


async def ensure_users_are_present(conn, users):
    """
    Upserts youtrack users
    """
    async with conn.transaction():
        await conn.executemany(ENSURE_USERS_ARE_PRESENT_QUERY,
                               users)

GET_PROJECTS_QUERY = _load_query('get_projects')


async def get_projects(conn):
    return await conn.fetch(GET_PROJECTS_QUERY)


SET_LAST_UPDATED_QUERY = _load_query('set_last_updated')


async def set_last_updated(conn, project_id, last_checked):
    async with conn.transaction():
        await conn.execute(SET_LAST_UPDATED_QUERY,
                           project_id, last_checked)


CHECK_COMMENT_QUERY = _load_query('check_comment')


async def check_comment(conn, comment):
    async with conn.transaction():
        return await conn.fetchval(CHECK_COMMENT_QUERY,
                                   comment['id'])


GET_PROJECT_CHAT_ID_QUERY = _load_query('get_project_chat_id')

async def get_project_chat_id(conn, project_id):
    async with conn.transaction():
        return await conn.fetchval(GET_PROJECT_CHAT_ID_QUERY,
                                   project_id)


SET_COMMENT_POSTED_QUERY = _load_query('set_comment_posted')

async def set_comment_posted(conn, comment):
    async with conn.transaction():
        project_id = comment['issueId'].split('-')[0]
        await conn.execute(SET_COMMENT_POSTED_QUERY,
                           comment['id'],
                           project_id,
                           comment['author'])


async def get_user(conn, youtrack_id):
    return await conn.fetchrow(
        "SELECT * FROM users WHERE youtrack_id = $1",
        youtrack_id)

async def create_pool(dsn):
    """
    Creates connection pool from dsn
    """
    pool = await asyncpg.create_pool(dsn)
    async with pool.acquire() as conn:
        await _run_migrations(conn)
    return pool
