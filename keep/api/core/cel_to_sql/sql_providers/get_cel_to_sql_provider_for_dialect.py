from keep.api.core.cel_to_sql.sql_providers.sqlite import CelToSqliteProvider
from keep.api.core.cel_to_sql.sql_providers.mysql import CelToMySqlProvider

def get_cel_to_sql_provider_for_dialect(dialect: str, known_fields_mapping: dict):
    if dialect == "sqlite":
        return CelToSqliteProvider(known_fields_mapping)
    elif dialect == "mysql":
        return CelToMySqlProvider(known_fields_mapping)
    
    else:
        raise ValueError(f"Unsupported dialect: {dialect}")