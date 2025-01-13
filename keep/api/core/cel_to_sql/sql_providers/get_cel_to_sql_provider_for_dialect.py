from keep.api.core.cel_to_sql.sql_providers.base import BaseCelToSqlProvider
from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider
from keep.api.core.cel_to_sql.sql_providers.mysql import CelToMySqlProvider

def get_cel_to_sql_provider_for_dialect(dialect: str) -> type[BaseCelToSqlProvider]:
    if dialect == "sqlite":
        return CelToSqliteProvider
    elif dialect == "mysql":
        return CelToMySqlProvider
    
    else:
        raise ValueError(f"Unsupported dialect: {dialect}")