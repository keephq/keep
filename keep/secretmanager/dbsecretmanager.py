from datetime import datetime
import json
from sqlmodel import Session, select

from keep.api.models.db.secret import Secret
from keep.secretmanager.secretmanager import BaseSecretManager

from keep.api.core.db import engine


class DbSecretManager(BaseSecretManager):
    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        self.logger.info("Using DB Secret Manager")

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        self.logger.info("Getting secret", extra={"secret_name": secret_name})
        with Session(engine) as session:
            try:
                secret_model = session.exec(
                    select(Secret).where(
                        Secret.key == secret_name
                    )
                ).one_or_none()
                if secret_model:
                    if is_json:
                        return json.loads(secret_model.value)
                    return secret_model.value
                else:
                    raise KeyError(f"Secret {secret_name} not found")
            except Exception as e:    
                self.logger.error(
                    "Failed to read secret",
                    extra={"error": str(e)},
                )
                raise


    def write_secret(self, secret_name: str, secret_value: str) -> None:
        self.logger.info("Writing secret", extra={"secret_name": secret_name})        
        with Session(engine) as session:
            secret_model = session.exec(
                select(Secret).where(
                    Secret.key == secret_name
                )
            ).one_or_none()

            try:
                if secret_model:
                    secret_model.value = secret_value
                    secret_model.last_updated = datetime.utcnow()
                    session.commit()
                    return
                
                secret_model = Secret(
                    key=secret_name,
                    value=secret_value,
                )
                    
                session.add(secret_model)
                session.commit()
            except Exception as e:
                self.logger.error(
                    "Failed to write secret",
                    extra={"error": str(e)},
                )
                raise

    def delete_secret(self, secret_name: str) -> None:
        self.logger.info("Deleting secret", extra={"secret_name": secret_name})        
        with Session(engine) as session:
            secret_model = session.exec(
                select(Secret).where(
                    Secret.key == secret_name
                )
            ).one_or_none()
            try:
                if secret_model:
                    session.delete(secret_model)
                    session.commit()
            except Exception as e:
                self.logger.error(
                    "Failed to delete secret",
                    extra={"error": str(e)},
                )
                raise        
