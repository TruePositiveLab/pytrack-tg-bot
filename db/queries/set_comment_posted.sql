WITH
    _tmp as (
    	select
    		$1::varchar as youtrack_id,
    		(SELECT id FROM tracked_projects WHERE youtrack_id = $2) as project_id,
    		(SELECT id FROM users WHERE youtrack_id = $3) as author_id
        )
INSERT INTO posted_comments (youtrack_id, project_id, author_id)
select * from _tmp;
