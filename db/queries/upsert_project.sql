INSERT INTO
    tracked_projects
    (youtrack_id, name)
VALUES
    ($1, $2)
ON CONFLICT (youtrack_id) DO UPDATE SET name = excluded.name;
