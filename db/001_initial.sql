BEGIN;

    CREATE TABLE public.tracked_projects (
        id serial NOT NULL,
        youtrack_id varchar NULL,
        search_query varchar NOT NULL DEFAULT 'updated: today'::character varying,
        last_checked timestamp NOT NULL DEFAULT to_timestamp(0),
        tg_chat varchar NOT NULL,
        name varchar NOT NULL,
        CONSTRAINT tracked_projects_pk PRIMARY KEY (id),
        CONSTRAINT tracked_projects_unique_youtrack_id UNIQUE (youtrack_id)
    )
    WITH (
        OIDS=FALSE
    );

    CREATE TABLE public.users (
        id serial NOT NULL,
        tg_id varchar,
        youtrack_id varchar NOT NULL,
        full_name varchar NOT NULL,
        CONSTRAINT users_pk PRIMARY KEY (id),
        CONSTRAINT users_unique_youtrack_id UNIQUE (youtrack_id)
    )
    WITH (
        OIDS=FALSE
    );

    CREATE TABLE public.posted_comments (
        id serial NOT NULL,
        youtrack_id varchar NOT NULL,
        project_id int4 NOT NULL,
        author_id int4 NOT NULL,
        posted_at timestamp NOT NULL DEFAULT current_timestamp,
        CONSTRAINT posted_comments_pk PRIMARY KEY (id),
        CONSTRAINT posted_comments_unique_youtrack_id UNIQUE (youtrack_id),
        CONSTRAINT posted_comments_tracked_projects_fk FOREIGN KEY (project_id) REFERENCES public.tracked_projects(id),
        CONSTRAINT posted_comments_users_fk FOREIGN KEY (author_id) REFERENCES public.users(id)
    )
    WITH (
        OIDS=FALSE
    );

COMMIT;
