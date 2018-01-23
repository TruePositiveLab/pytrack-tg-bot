SELECT
    id, youtrack_id, name, search_query, last_checked, tg_chat
FROM tracked_projects
WHERE tg_chat is not NULL
