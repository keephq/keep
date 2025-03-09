import logging
from datetime import datetime

from sqlalchemy.dialects.mssql import DATETIME2 as MSSQL_DATETIME2
from sqlalchemy.dialects.mysql import DATETIME as MySQL_DATETIME
from sqlalchemy.engine.url import make_url
from sqlmodel import DateTime

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.config import config

logger = logging.getLogger(__name__)

# We want to include the deleted_at field in the primary key,
# but we also want to allow it to be nullable. MySQL doesn't allow nullable fields in primary keys, so:
NULL_FOR_DELETED_AT = datetime(1000, 1, 1, 0, 0)


DB_CONNECTION_STRING = config("DATABASE_CONNECTION_STRING", default=None)
# managed (mysql)
if RUNNING_IN_CLOUD_RUN or DB_CONNECTION_STRING == "impersonate":
    # Millisecond precision
    DATETIME_COLUMN_TYPE = MySQL_DATETIME(fsp=3)
# self hosted (mysql, sql server, sqlite / postgres)
else:
    try:
        url = make_url(DB_CONNECTION_STRING)
        dialect = url.get_dialect().name
        if dialect == "mssql":
            # Millisecond precision
            DATETIME_COLUMN_TYPE = MSSQL_DATETIME2(precision=3)
        elif dialect == "mysql":
            # Millisecond precision
            DATETIME_COLUMN_TYPE = MySQL_DATETIME(fsp=3)
        else:
            DATETIME_COLUMN_TYPE = DateTime
    except Exception:
        logger.warning(
            "Could not determine the database dialect, falling back to default datetime column type"
        )
        # give it a default
        DATETIME_COLUMN_TYPE = DateTime
