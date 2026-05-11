from __future__ import annotations

from sqlalchemy import or_

from app.models.upload import TrapUpload


# Exclude dataset split artifacts from user-facing analytics.
# These usually come from offline train/valid/test datasets and should not appear in production dashboards.
_DATASET_PATH_PATTERNS = (
    "%/train/%",
    "%\\train\\%",
    "%/training/%",
    "%\\training\\%",
    "%/valid/%",
    "%\\valid\\%",
    "%/validation/%",
    "%\\validation\\%",
    "%/test/%",
    "%\\test\\%",
)


def apply_production_upload_filter(query):
    if query is None:
        return query
    blocked = [TrapUpload.image_path.ilike(pattern) for pattern in _DATASET_PATH_PATTERNS]
    return query.filter(~or_(*blocked))
