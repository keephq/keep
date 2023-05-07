import hashlib

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, SQLModel, create_engine, select

# This import is required to create the tables
from keep.api.models.db.tenant import *

# Todo: this should be from the configuration
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    """
    Creates the database and tables.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Creates a database session.

    Yields:
        Session: A database session
    """
    with Session(engine) as session:
        yield session


auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key")


def verify_customer(
    api_key: str = Security(auth_header), session: Session = Depends(get_session)
) -> TenantApiKey:
    """
    Verifies that a customer is allowed to access the API.

    Args:
        api_key (str, optional): The API key extracted from X-API-KEY header. Defaults to Security(auth_header).
        session (Session, optional): A databse session. Defaults to Depends(get_session).

    Raises:
        HTTPException: 401 if the user is unauthorized.

    Returns:
        TenantApiKey: The tenant API key resource including the Tenant resource.
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")

    api_key_hashed = hashlib.sha256(api_key.encode()).hexdigest()

    statement = select(TenantApiKey).where(TenantApiKey.key_hash == api_key_hashed)
    tenant_api_key = session.exec(statement).first()
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return tenant_api_key
