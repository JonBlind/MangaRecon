"""maintain internal manga rating average

Revision ID: b7c2d4e6f8a1
Revises: e08ce70978e1
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7c2d4e6f8a1"
down_revision: Union[str, Sequence[str], None] = "e08ce70978e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep manga.average_rating synchronized with personal rating rows."""
    op.execute(
        """
        CREATE FUNCTION public.refresh_manga_average_rating()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            target_manga_id integer;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_manga_id := OLD.manga_id;
            ELSE
                target_manga_id := NEW.manga_id;
            END IF;

            PERFORM 1
            FROM public.manga
            WHERE manga.manga_id = target_manga_id
            FOR UPDATE;

            UPDATE public.manga
            SET average_rating = (
                SELECT ROUND(AVG(r.personal_rating), 1)
                FROM public.rating AS r
                WHERE r.manga_id = target_manga_id
            )
            WHERE manga.manga_id = target_manga_id;

            RETURN NULL;
        END;
        $function$
        """
    )
    op.execute(
        """
        REVOKE ALL
        ON FUNCTION public.refresh_manga_average_rating()
        FROM PUBLIC
        """
    )
    op.execute(
        """
        GRANT EXECUTE
        ON FUNCTION public.refresh_manga_average_rating()
        TO "UserManager", "MangaManager"
        """
    )
    op.execute(
        """
        CREATE TRIGGER refresh_manga_average_rating_after_rating_change
        AFTER INSERT OR UPDATE OF personal_rating OR DELETE
        ON public.rating
        FOR EACH ROW
        EXECUTE FUNCTION public.refresh_manga_average_rating()
        """
    )
    op.execute(
        """
        UPDATE public.manga AS m
        SET average_rating = (
            SELECT ROUND(AVG(r.personal_rating), 1)
            FROM public.rating AS r
            WHERE r.manga_id = m.manga_id
        )
        """
    )


def downgrade() -> None:
    """Remove automatic aggregate maintenance without erasing stored averages."""
    op.execute(
        """
        DROP TRIGGER IF EXISTS refresh_manga_average_rating_after_rating_change
        ON public.rating
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.refresh_manga_average_rating()
        """
    )
