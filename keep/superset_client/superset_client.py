import logging
import os
import tempfile

import requests

from keep.api.core.config import config


class SupersetClient:
    def __init__(
        self, base_url: str = None, username: str = None, password: str = None
    ):
        self.base_url = base_url or config(
            "SUPERSET_URL", default="http://localhost:8088"
        )
        self.username = username or config("SUPERSET_USER", default="admin")
        self.password = password or config("SUPERSET_PASSWORD", default="admin")
        self.dashboards_templates_dir = config(
            "SUPERSET_DASHBOARDS_TEMPLATES_DIR", default="superset/dashboards"
        )
        self.access_token = None
        self.csrf_token = None
        self.session_cookie = None
        self.logger = logging.getLogger(__name__)
        # Template dashboards tag
        self.template_tag = "keep_template_dashboards"

    # SHAHAR: this assume empty superset!
    def initial_provision(self):
        """
        Initial provisioning of template dashboards.
        Imports all dashboard templates from zip files and tags them as templates.

        Returns:
            list: List of provisioned template dashboards
        """
        if not self.access_token:
            self.authenticate()

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
        Provision dashboards for a specific tenant by copying template dashboards.

        Args:
            tenant_id (str): The tenant ID to provision dashboards for

        Returns:
            list: List of provisioned dashboards for the tenant
        """
        if not self.access_token:
            self.authenticate()

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

            try:
                # Export the template dashboard
                export_response = requests.get(
                    f"{self.base_url}/api/v1/dashboard/export/?q=!({dashboard_id})",
                    headers=self.get_headers(),
                    cookies=self.get_cookies(),
                )
                export_response.raise_for_status()

                # Create a temporary directory for processing
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Save the exported dashboard zip
                    export_path = os.path.join(temp_dir, "dashboard_export.zip")
                    with open(export_path, "wb") as f:
                        f.write(export_response.content)

                    # Prepare for import
                    if dashboard_title in existing_dashboard_titles:
                        # Delete existing dashboard for this tenant
                        existing_id = existing_dashboard_titles[dashboard_title]
                        self._delete_dashboard(existing_id)
                        self.logger.info(
                            f"Deleted existing dashboard '{dashboard_title}' for tenant {tenant_id}"
                        )

                    # Import the dashboard for the tenant
                    tenant_dashboard_info = self._import_dashboard_from_zip(export_path)

                    if tenant_dashboard_info and "id" in tenant_dashboard_info:
                        # Apply the tenant tag
                        self.apply_tag_to_dashboard(
                            tenant_dashboard_info["id"], tenant_tag
                        )
                        provisioned_dashboards.append(tenant_dashboard_info)
                        self.logger.info(
                            f"Successfully provisioned dashboard '{dashboard_title}' for tenant {tenant_id}"
                        )

            except Exception as e:
                self.logger.error(
                    f"Error provisioning dashboard '{dashboard_title}' for tenant {tenant_id}: {str(e)}"
                )
                continue

        return provisioned_dashboards

    def _import_dashboard_from_zip(self, zip_path):
        """
        Import a dashboard from a zip file

        Args:
            zip_path (str): Path to the zip file

        Returns:
            dict: Dashboard information if successful, None otherwise
        """
        try:
            with open(zip_path, "rb") as f:
                zip_content = f.read()

            files = {
                "formData": (zip_path, zip_content, "application/zip"),
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
                json={"tags": [tag_name]},
            )
            response.raise_for_status()
            return True

        except Exception as e:
            self.logger.error(
                f"Error applying tag {tag_name} to dashboard {dashboard_id}: {str(e)}"
            )
            return False

    def authenticate(self):
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
        self.access_token = auth_response.json()["access_token"]

        # Step 2: Get CSRF token
        csrf_response = requests.get(
            f"{self.base_url}/api/v1/security/csrf_token/",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        csrf_response.raise_for_status()
        self.csrf_token = csrf_response.json()["result"]
        self.session_cookie = csrf_response.cookies.get("session")

        return self

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-CSRFToken": self.csrf_token,
        }

    def get_cookies(self):
        return {"session": self.session_cookie}

    def get_dashboards(self):
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
            self.authenticate()

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

    def get_guest_token(self, dashboard_id: str):
        """
        Get a guest token for a dashboard

        Args:
            dashboard_id (str): The dashboard ID

        Returns:
            str: The guest token
        """
        if not self.access_token:
            self.authenticate()

        response = requests.post(
            f"{self.base_url}/api/v1/security/guest_token/",
            headers=self.get_headers(),
            cookies=self.get_cookies(),
            json={
                "user": {"username": "apiuser"},
                "resources": [{"type": "dashboard", "id": dashboard_id}],
                "rls": [],
            },
        )
        response.raise_for_status()
        return response.json()["token"]
