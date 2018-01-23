INSERT INTO
    users
    (youtrack_id, full_name)
VALUES
    ($1, $2)
ON CONFLICT (youtrack_id) DO UPDATE SET full_name = excluded.full_name;
