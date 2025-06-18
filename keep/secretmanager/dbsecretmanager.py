import json
import logging
import time
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.models.db.secret import Secret
from keep.secretmanager.secretmanager import BaseSecretManager

from keep.api.core.db import engine

logger = logging.getLogger(__name__)

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
            except Exception as e:    
                self.logger.error(f"Fail to read secret {secret_name}: {e}")
                raise


    def write_secret(self, secret_name: str, secret_value: str) -> None:
        self.logger.info("Getting secret", extra={"secret_name": secret_name})        
        with Session(engine) as session:
            secret_model = session.exec(
                select(Secret).where(
                    Secret.key == secret_name
                )
            ).one_or_none()

            try:
                if secret_model:
                    secret_model.value = secret_value
                    secret_model.lastmodification_time = time.time()
                    session.commit()
                    return
    
                if not secret_model:
                    secret_model = Secret(
                        key=secret_name,
                        value=secret_value,
                    )
                    
                session.add(secret_model)
                session.commit()
            except Exception as e:
                self.logger.error(f"Exception")
                raise

    def delete_secret(self, secret_name: str) -> None:
        self.logger.info("Deleting secret", extra={"secret_name": secret_name})        
        with Session(engine) as session:
            secret_model = session.exec(
                select(Secret).where(
                    Secret.key == secret_name
                )
            ).one_or_none()

            if secret_model:
                session.delete(secret_model)
                session.commit()
