UPDATE tracked_projects
SET last_checked = $2
WHERE youtrack_id = $1 AND last_checked < $2;
