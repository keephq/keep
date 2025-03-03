import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from typing import Optional

import jwt
import requests

from keep.api.core.config import config


class SupersetClient:
    def __init__(
        self, base_url: str = None, username: str = None, password: str = None
    ):
        self.base_url = base_url or config(
            "KEEP_SUPERSET_URL", default="http://localhost:8088"
        )
        self.username = username or config("KEEP_SUPERSET_USER", default="admin")
        self.password = password or config("KEEP_SUPERSET_PASSWORD", default="admin")
        self.dashboards_templates_dir = config(
            "KEEP_KEEP_SUPERSET_URLSUPERSET_DASHBOARDS_TEMPLATES_DIR",
            default="superset/dashboards",
        )
        self._access_token = None
        self.csrf_token = None
        self.session_cookie = None
        self.logger = logging.getLogger(__name__)
        # Template dashboards tag
        self.template_tag = "keep_template_dashboards"
        # for optimization, we keep the dataset ids
        self.dataset_ids = []

    @property
    def access_token(self) -> Optional[str]:
        """
        Property for access_token that checks if the token is expired or about to expire.
        Automatically refreshes the token if needed.

        Returns:
            str: The current valid access token or None if authentication fails
        """
        current_time = time.time()

        # If token doesn't exist or is about to expire, refresh it
        if not self._access_token:
            try:
                self.logger.info("Authenticating to Superset")
                self.authenticate()
                self.logger.info("Successfully authenticated to Superset")
            except Exception as e:
                self.logger.error(f"Error refreshing access token: {str(e)}")
                return None
        else:
            exp = jwt.decode(self._access_token, options={"verify_signature": False})[
                "exp"
            ]
            # Refresh token if it's about to expire
            if exp - current_time < 0:
                try:
                    self.logger.info("Refreshing access token")
                    self.authenticate()
                    self.logger.info("Successfully refreshed access token")
                except Exception as e:
                    self.logger.error(f"Error refreshing access token: {str(e)}")
                    return None

        return self._access_token

    # SHAHAR: this assume empty superset!
    def initial_provision(self):
        """
        Initial provisioning of template dashboards.
        Imports all dashboard templates from zip files and tags them as templates.

        Returns:
            list: List of provisioned template dashboards
        """
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return []

        # first, check if dashboards already exists - if so, abort
        dashboards = self.get_dashboards()
        # if dashboards exists, just abort
        if dashboards:
            self.logger.info(
                "Dashboards already exist in Superset. Aborting initial provisioning."
            )
            return []

        provisioned_dashboards = []

        # 1. Read the dashboards from the templates directory
        try:
            dashboard_templates = os.listdir(self.dashboards_templates_dir)
            dashboard_templates = [
                dt for dt in dashboard_templates if dt.endswith(".zip")
            ]
        except FileNotFoundError:
            self.logger.error(
                f"Dashboard templates directory not found: {self.dashboards_templates_dir}"
            )
            return []

        if not dashboard_templates:
            self.logger.error(
                f"No dashboard templates found in directory: {self.dashboards_templates_dir}"
            )
            return []

        # Ensure the template tag exists in Superset
        self.ensure_tag_exists(self.template_tag)

        number_of_dashboards_templates = len(dashboard_templates)
        for dashboard_template in dashboard_templates:
            template_path = os.path.join(
                self.dashboards_templates_dir, dashboard_template
            )

            # Skip if not a zip file
            if not dashboard_template.endswith(".zip"):
                continue

            try:
                # Import the dashboard template
                self.logger.info(f"Importing template dashboard {dashboard_template}")
                self._import_dashboard_from_zip(template_path)
                self.logger.info(
                    f"Successfully imported template dashboard {dashboard_template}"
                )
            except Exception as e:
                self.logger.exception(
                    f"Error provisioning template dashboard {dashboard_template}"
                )
                raise e

        # all templates are imported, now tag them
        # note that dashboards are numbered from 1 to number_of_dashboards_templates
        # that's why we have to make sure that initially superset doesn't have any dashboards
        for i in range(1, number_of_dashboards_templates + 1):
            self.apply_tag_to_dashboard(i, self.template_tag)
        return provisioned_dashboards

    def provision_dashboards_for_tenant(self, tenant_id: str):
        """
        Provision dashboards for a specific tenant by copying template dashboards using the copy API.

        Args:
            tenant_id (str): The tenant ID to provision dashboards for

        Returns:
            list: List of provisioned dashboards for the tenant
        """
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return []

        tenant_tag = f"keep_tenant_{tenant_id}"
        provisioned_dashboards = []

        # Ensure the tenant tag exists
        self.ensure_tag_exists(tenant_tag)

        # Get all template dashboards
        template_dashboards = self.get_dashboards_by_tag(self.template_tag)

        if not template_dashboards:
            self.logger.error(
                f"No template dashboards found with tag: {self.template_tag}"
            )
            return []

        # Get existing tenant dashboards
        existing_tenant_dashboards = self.get_dashboards_by_tag(tenant_tag)
        existing_dashboard_titles = {
            db["dashboard_title"]: db["id"] for db in existing_tenant_dashboards
        }

        for template_dashboard in template_dashboards:
            dashboard_title = template_dashboard["dashboard_title"]
            dashboard_id = template_dashboard["id"]
            new_dashboard_title = f"{dashboard_title} - {tenant_id}"

            try:
                # If dashboard with this title already exists for this tenant, delete it
                if new_dashboard_title in existing_dashboard_titles:
                    existing_id = existing_dashboard_titles[new_dashboard_title]
                    self._delete_dashboard(existing_id)
                    self.logger.info(
                        f"Deleted existing dashboard '{new_dashboard_title}' for tenant {tenant_id}"
                    )

                # Get the dashboard details to extract json_metadata
                dashboard_details_response = requests.get(
                    f"{self.base_url}/api/v1/dashboard/{dashboard_id}",
                    headers=self.get_headers(),
                    cookies=self.get_cookies(),
                )
                dashboard_details_response.raise_for_status()
                # get the metadata and positions
                dashboard_metadata_json = (
                    dashboard_details_response.json()
                    .get("result", {})
                    .get("json_metadata")
                )
                dashboard_positions = (
                    dashboard_details_response.json()
                    .get("result", {})
                    .get("position_json")
                )

                # Update the metadata with positions - it needs to be a dict
                metadata_dict = json.loads(dashboard_metadata_json)
                metadata_dict["positions"] = json.loads(dashboard_positions)

                # Copy the dashboard using the API
                copy_payload = {
                    "dashboard_title": new_dashboard_title,
                    "duplicate_slices": True,
                    "json_metadata": json.dumps(metadata_dict),
                }

                response = requests.post(
                    f"{self.base_url}/api/v1/dashboard/{dashboard_id}/copy/",
                    headers=self.get_headers(),
                    cookies=self.get_cookies(),
                    json=copy_payload,
                )
                response.raise_for_status()

                new_dashboard = response.json().get("result")

                if new_dashboard and "id" in new_dashboard:
                    # Apply the tenant tag
                    self.apply_tag_to_dashboard(new_dashboard["id"], tenant_tag)
                    provisioned_dashboards.append(new_dashboard)
                    self.logger.info(
                        f"Successfully provisioned dashboard '{new_dashboard_title}' for tenant {tenant_id}"
                    )

                    # last step - make them embedded
                    embedded_response = requests.post(
                        f"{self.base_url}/api/v1/dashboard/{new_dashboard['id']}/embedded",
                        headers=self.get_headers(),
                        cookies=self.get_cookies(),
                        json={
                            "allowed_domains": [],
                        },
                    )
                    embedded_response.raise_for_status()
                    self.logger.info(
                        f"Successfully embedded dashboard '{new_dashboard_title}' for tenant {tenant_id}"
                    )

            except Exception as e:
                self.logger.error(
                    f"Error provisioning dashboard '{dashboard_title}' for tenant {tenant_id}: {str(e)}"
                )
                continue

        return provisioned_dashboards

    def _import_dashboard_from_zip(self, zip_path):
        """
        Import a dashboard from a zip file, modifying the database URI to use
        environment variable DATABASE_CONNECTION_STRING

        Args:
            zip_path (str): Path to the zip file

        Returns:
            bool: True if successful, None otherwise
        """
        try:
            # Create a temporary directory to work in
            temp_dir = tempfile.mkdtemp()
            modified_zip_path = f"{zip_path.rsplit('.', 1)[0]}_modified.zip"

            try:
                # Extract the zip file
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Use glob to find all database YAML files in any subdirectory
                import glob

                # we need to inject:
                # 1. the database connection string
                # 2. the schema (on SQLite its "main", whereas on mysql its "keep")
                # Let's start with the database connection string
                # Find all YAML files in databases directories (handles nested structure)
                db_yaml_files = glob.glob(
                    os.path.join(temp_dir, "**", "databases", "*.yaml"), recursive=True
                )

                if not db_yaml_files:
                    self.logger.warning(f"No database YAML files found in {zip_path}")

                for db_path in db_yaml_files:
                    try:
                        # Read the database config file
                        with open(db_path, "r") as f:
                            content = f.read()

                        # Find and replace the sqlalchemy_uri line
                        uri_line = content.find("sqlalchemy_uri:")
                        if uri_line != -1:
                            # Find the end of the line
                            line_end = content.find("\n", uri_line)
                            if line_end == -1:  # If it's the last line
                                line_end = len(content)

                            # Extract the specific URI part
                            uri_value = content[uri_line:line_end]
                            # TODO: IAM?
                            db_connection_string = os.environ.get(
                                "SUPERSET_DATABASE_CONNECTION_STRING"
                            ) or os.environ.get("DATABASE_CONNECTION_STRING")
                            new_uri_value = f"sqlalchemy_uri: {db_connection_string}"

                            # Replace just that specific line
                            modified_content = content.replace(uri_value, new_uri_value)

                            # Write the modified content back
                            with open(db_path, "w") as f:
                                f.write(modified_content)

                            self.logger.info(
                                f"Modified database URI in {os.path.basename(db_path)} to use environment variable"
                            )
                    except Exception as e:
                        self.logger.error(f"Error modifying {db_path}: {str(e)}")

                datasets_yaml_file = glob.glob(
                    os.path.join(temp_dir, "**", "datasets", "*/*"), recursive=True
                )

                if not datasets_yaml_file:
                    self.logger.warning(f"No database YAML files found in {zip_path}")

                # TODO: do it nicer
                if "sqlite" in db_connection_string:
                    schema = "main"
                elif "mysql" in db_connection_string:
                    schema = "keep"
                elif "postgresql" in db_connection_string:
                    schema = "public"
                else:
                    schema = "public"

                for dataset_path in datasets_yaml_file:
                    try:
                        # Read the database config file
                        with open(dataset_path, "r") as f:
                            content = f.read()

                        # Find and replace the sqlalchemy_uri line
                        uri_line = content.find("schema:")
                        if uri_line != -1:
                            # Find the end of the line
                            line_end = content.find("\n", uri_line)
                            if line_end == -1:  # If it's the last line
                                line_end = len(content)

                            # Extract the specific URI part
                            uri_value = content[uri_line:line_end]
                            new_uri_value = f"schema: {schema}"

                            # Replace just that specific line
                            modified_content = content.replace(uri_value, new_uri_value)

                            # Write the modified content back
                            with open(dataset_path, "w") as f:
                                f.write(modified_content)

                            self.logger.info(
                                f"Modified database URI in {os.path.basename(dataset_path)} to use environment variable"
                            )
                    except Exception as e:
                        self.logger.error(f"Error modifying {db_path}: {str(e)}")

                # Create a new zip file with the modified contents
                with zipfile.ZipFile(
                    modified_zip_path, "w", zipfile.ZIP_DEFLATED
                ) as zipf:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)

                self.logger.info(f"Created modified zip file: {modified_zip_path}")

                # Upload the modified zip
                with open(modified_zip_path, "rb") as f:
                    zip_content = f.read()

                files = {
                    "formData": (
                        os.path.basename(modified_zip_path),
                        zip_content,
                        "application/zip",
                    ),
                }
                data = {
                    "overwrite": "true",
                }

                response = requests.post(
                    f"{self.base_url}/api/v1/dashboard/import/",
                    headers=self.get_headers(),
                    cookies=self.get_cookies(),
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return True

            finally:
                # Clean up temporary files
                shutil.rmtree(temp_dir)
                if os.path.exists(modified_zip_path):
                    os.remove(modified_zip_path)

        except Exception as e:
            self.logger.error(f"Error importing dashboard from zip: {str(e)}")
            return None

    def _delete_dashboard(self, dashboard_id):
        """
        Delete a dashboard by ID

        Args:
            dashboard_id (int): The dashboard ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = requests.delete(
                f"{self.base_url}/api/v1/dashboard/{dashboard_id}",
                headers=self.get_headers(),
                cookies=self.get_cookies(),
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Error deleting dashboard {dashboard_id}: {str(e)}")
            return False

    def ensure_tag_exists(self, tag_name):
        """
        Check if a tag exists in Superset. If not, create it.

        Args:
            tag_name (str): The name of the tag to ensure exists

        Returns:
            int: The ID of the tag
        """
        try:
            # First, check if the tag already exists
            q = f"(filters:!((col:name,opr:eq,value:{tag_name})))"
            url = f"{self.base_url}/api/v1/tag/?q={q}"
            response = requests.get(
                url,
                headers=self.get_headers(),
                cookies=self.get_cookies(),
            )
            response.raise_for_status()

            tags = response.json().get("result", [])
            if tags:
                # Tag already exists, return its ID
                return tags[0]["id"]

            # Create the tag if it doesn't exist
            response = requests.post(
                f"{self.base_url}/api/v1/tag/",
                headers=self.get_headers(),
                cookies=self.get_cookies(),
                json={
                    "name": tag_name,
                    "description": f"Tag for {tag_name} dashboards",
                    "objects_to_tag": [],
                },
            )
            response.raise_for_status()
            return response.json()["id"]

        except Exception as e:
            self.logger.error(f"Error ensuring tag exists {tag_name}: {str(e)}")
            return None

    def apply_tag_to_dashboard(self, dashboard_id, tag_name):
        """
        Apply a tag to a dashboard in Superset.

        Args:
            dashboard_id (int): The ID of the dashboard
            tag_name (str): The name of the tag to apply

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the tag ID
            tag_id = self.ensure_tag_exists(tag_name)
            if not tag_id:
                self.logger.error(f"Could not get or create tag: {tag_name}")
                return False

            # Apply the tag to the dashboard
            # dashboard == object type 3
            # see: https://github.com/apache/superset/blob/master/superset/migrations/versions/2024-01-17_13-09_96164e3017c6_tagged_object_unique_constraint.py#L33
            response = requests.post(
                f"{self.base_url}/api/v1/tag/3/{dashboard_id}/",
                headers=self.get_headers(),
                cookies=self.get_cookies(),
                json={"properties": {"tags": [tag_name]}},
            )
            response.raise_for_status()
            return True

        except Exception as e:
            self.logger.error(
                f"Error applying tag {tag_name} to dashboard {dashboard_id}: {str(e)}"
            )
            return False

    def authenticate(self):
        """
        Authenticate with Superset API and get access token, CSRF token and session cookie.
        Also extracts token expiration time from response.

        Returns:
            self: The client instance for method chaining
        """
        try:
            # Step 1: Login and get access token
            auth_response = requests.post(
                f"{self.base_url}/api/v1/security/login",
                json={
                    "username": self.username,
                    "password": self.password,
                    "provider": "db",
                },
            )
            auth_response.raise_for_status()
            auth_data = auth_response.json()
            self._access_token = auth_data["access_token"]

            # Extract token expiry time - default to 1 hour if not provided
            # Superset typically returns 'refresh_token_expires_at' in seconds from now
            expiry_seconds = auth_data.get("refresh_token_expires_at", 3600)
            self._token_expiry = time.time() + expiry_seconds

            self.logger.debug(f"Token will expire at: {self._token_expiry}")

            # Step 2: Get CSRF token
            csrf_response = requests.get(
                f"{self.base_url}/api/v1/security/csrf_token/",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            csrf_response.raise_for_status()
            self.csrf_token = csrf_response.json()["result"]
            self.session_cookie = csrf_response.cookies.get("session")

            return self
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            # Reset tokens on authentication failure
            self._access_token = None
            self._token_expiry = 0
            self.csrf_token = None
            self.session_cookie = None
            raise

    def get_headers(self):
        """
        Get the headers for API requests, including fresh access token

        Returns:
            dict: Headers dictionary with Authorization and CSRF token
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-CSRFToken": self.csrf_token,
        }

    def get_cookies(self):
        return {"session": self.session_cookie}

    def get_dashboards(self):
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return []

        dashboards_response = requests.get(
            f"{self.base_url}/api/v1/dashboard/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        dashboards_response.raise_for_status()
        dashboards = dashboards_response.json()["result"]
        return dashboards

    def get_dashboards_by_tag(self, tag_name):
        """
        Get all dashboards that have a specific tag

        Args:
            tag_name (str): The tag name to filter by

        Returns:
            list: List of dashboard objects
        """
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return []

        q = f"(filters:!((col:tags,opr:dashboard_tags,value:{tag_name})))"
        try:
            dashboards_response = requests.get(
                f"{self.base_url}/api/v1/dashboard/?q=" + q,
                headers=self.get_headers(),
                cookies=self.get_cookies(),
            )
            dashboards_response.raise_for_status()
            dashboards = dashboards_response.json()["result"]

            # Fetch embedded IDs for each dashboard
            for dashboard in dashboards:
                try:
                    detail_response = requests.get(
                        f"{self.base_url}/api/v1/dashboard/{dashboard['id']}/embedded",
                        headers=self.get_headers(),
                        cookies=self.get_cookies(),
                    )
                    detail_response.raise_for_status()
                    embedded_id = detail_response.json().get("result", {}).get("uuid")
                    dashboard["embedded_id"] = embedded_id
                except Exception as e:
                    self.logger.warning(
                        f"Error getting embedded ID for dashboard {dashboard['id']}: {str(e)}"
                    )
                    dashboard["embedded_id"] = None

            return dashboards
        except Exception as e:
            self.logger.error(f"Error getting dashboards by tag {tag_name}: {str(e)}")
            return []

    def get_dashboards_by_tenant_id(self, tenant_id: str, should_exist: bool = False):
        """
        Get all dashboards for a specific tenant

        Args:
            tenant_id (str): The tenant ID to get dashboards for
            should_exist (bool): If True, will provision dashboards for the tenant if none exist

        Returns:
            list: List of dashboard objects for the tenant
        """
        tenant_tag = f"keep_tenant_{tenant_id}"
        dashboards = self.get_dashboards_by_tag(tenant_tag)

        # If should_exist is True and no dashboards found, provision them
        if should_exist and not dashboards:
            self.logger.info(
                f"No dashboards found for tenant {tenant_id}, provisioning them"
            )
            self.provision_dashboards_for_tenant(tenant_id)
            # Get the newly provisioned dashboards
            dashboards = self.get_dashboards_by_tag(tenant_tag)
            # if still no dashboards - warning error since it should have been provisioned
            if not dashboards:
                self.logger.error(
                    f"No dashboards found for tenant {tenant_id} after provisioning"
                )

        return dashboards

    def _fetch_dataset_ids(self):
        """
        Fetch all dataset ids from Superset

        Returns:
            list: List of dataset IDs
        """
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return []

        self.logger.info("Fetching dataset IDs from Superset")
        datasets_response = requests.get(
            f"{self.base_url}/api/v1/dataset/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
        )
        datasets_response.raise_for_status()
        datasets = datasets_response.json()["result"]
        self.dataset_ids = [dataset["id"] for dataset in datasets]
        self.logger.info(f"Fetched {len(self.dataset_ids)} dataset IDs")
        return self.dataset_ids

    def get_guest_token(self, dashboard_id: str, tenant_id: str):
        """
        Get a guest token for a dashboard

        Args:
            dashboard_id (str): The dashboard ID

        Returns:
            str: The guest token
        """
        if not self.access_token:
            self.logger.error("Failed to authenticate to Superset")
            return None

        # fetch the dataset ids
        if not self.dataset_ids:
            self._fetch_dataset_ids()

        rls = []
        for dataset_id in self.dataset_ids:
            rls.append(
                {
                    "clause": f"tenant_id = '{tenant_id}'",
                    "dataset": dataset_id,
                }
            )
        response = requests.post(
            f"{self.base_url}/api/v1/security/guest_token/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
            json={
                "user": {"username": "apiuser"},
                "resources": [{"type": "dashboard", "id": dashboard_id}],
                "rls": rls,
            },
        )
        response.raise_for_status()
        return response.json()["token"]
