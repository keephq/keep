import json

from google.cloud import storage

from keep.storagemanager.storagemanager import BaseStorageManager


class GcpStorageManager(BaseStorageManager):
    def __init__(self, **kwargs):
        super().__init__()
        # Initialize the Google Cloud Storage client
        self.storage_client = storage.Client()

    def create_bucket_if_not_exists(self, bucket_name):
        """Create the GCP bucket if it doesn't exist."""
        try:
            bucket = self.storage_client.get_bucket(bucket_name)
        except Exception:
            self.logger.info("Creating bucket %s", bucket_name)
            bucket = self.storage_client.create_bucket(bucket_name)
            self.logger.info("Bucket %s created successfully", bucket_name)
        return bucket

    def get_file(self, tenant_id, filename, create_if_not_exist=False) -> str:
        """
        Get a file from Google Cloud Storage.
        Args:
            filename (str): The name of the file to get.
        Returns:
            str: The content of the file.
        """
        bucket = self.create_bucket_if_not_exists(tenant_id)
        try:
            blob = bucket.blob(filename)
        except Exception as exc:
            self.logger.warning("Failed to get file %s", filename)
            if create_if_not_exist:
                self.logger.warning("Creating file %s", filename)
                blob = bucket.blob(filename)
                blob.upload_from_string(json.dumps({}))
                self.logger.warning("File %s created successfully", filename)
            else:
                self.logger.warning(f"Reason: {exc}")
                raise exc
        f = blob.download_as_string()
        return f

    def get_files(self, tenant_id) -> list[str]:
        """
        List all files from Google Cloud Storage.
        Returns:
            list[str]: A list of file names.
        """
        files = []
        bucket_name = tenant_id
        bucket = self.create_bucket_if_not_exists(bucket_name)
        # List all blobs (files) in the bucket
        blobs = list(bucket.list_blobs())
        # Append the filenames to the list
        for blob in blobs:
            blob_content = blob.download_as_bytes()
            files.append(blob_content)

        return files

    def store_file(self, tenant_id, file_name, file_content: dict | str):
        """
        Store a file in Google Cloud Storage.
        Args:
            file_name (str): The name of the file to store.
            file_content (bytes): The content of the file to store.
        """
        self.logger.info("Storing file %s in bucket %s", file_name, tenant_id)
        bucket = self.create_bucket_if_not_exists(tenant_id)
        blob = bucket.blob(file_name)

        if isinstance(file_content, dict):
            file_content = json.dumps(file_content, default=str)

        file_content = file_content.encode("utf-8")
        blob.upload_from_string(file_content)
        self.logger.info("File %s stored in bucket %s", file_name, tenant_id)
