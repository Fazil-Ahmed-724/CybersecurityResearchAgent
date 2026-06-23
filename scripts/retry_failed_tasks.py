import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database.db import SessionLocal
from app.models.failed_task import FailedTask
from app.tasks.article_tasks import process_article_task


def main():
    db = SessionLocal()
    try:
        rows = (
            db.query(FailedTask)
            .filter(FailedTask.is_resolved == False)
            .order_by(FailedTask.created_at.asc())
            .all()
        )

        print("\n========== FAILED TASK RETRY START ==========")
        print(f"[Retry Failed Tasks] Unresolved rows found: {len(rows)}")

        queued = 0

        for row in rows:
            if not row.article_id:
                print(f"[Retry Failed Tasks] Skipping failed_task #{row.id} (no article_id)")
                continue

            process_article_task.delay(row.article_id)
            queued += 1
            print(
                f"[Retry Failed Tasks] Requeued failed_task #{row.id} "
                f"for article #{row.article_id} | stage={row.stage}"
            )

        print("\n========== FAILED TASK RETRY COMPLETE ==========")
        print(f"[Retry Failed Tasks] Tasks queued: {queued}")
        print("===============================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()