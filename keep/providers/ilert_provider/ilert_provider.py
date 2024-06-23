class IlertProvider(BaseProvider):
    # Existing code...

    def fetch_all_incidents(self):
        """
        Fetch all incidents from iLert with metadata.
        """
        self.logger.info("Fetching all incidents from iLert")

        headers = {"Authorization": self.authentication_config.ilert_token}
        incidents = []
        page = 1
        page_size = 100  # Adjust based on API documentation or constraints

        while True:
            response = requests.get(
                f"{self.authentication_config.ilert_host}/incidents?page={page}&pageSize={page_size}",
                headers=headers,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to fetch incidents from iLert",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                )
                raise Exception(
                    f"Failed to fetch incidents from iLert: {response.status_code} {response.text}"
                )

            data = response.json()
            incidents.extend(data["incidents"])

            if len(data["incidents"]) < page_size:
                break  # Exit if there are no more incidents to fetch

            page += 1

        self.logger.info(
            "Fetched all incidents from iLert",
            extra={"total_incidents": len(incidents)},
        )
        return incidents

    # Existing methods...

    def _notify(
        self,
        _type: Literal["incident", "event"] = "event",
        summary: str = "",
        status: IlertIncidentStatus = IlertIncidentStatus.INVESTIGATING,
        message: str = "",
        affectedServices: str | list = "[]",
        id: str = "0",
        event_type: Literal["ALERT", "ACCEPT", "RESOLVE"] = "ALERT",
        details: str = "",
        alert_key: str = "",
        priority: Literal["HIGH", "LOW"] = "HIGH",
        images: list = [],
        links: list = [],
        custom_details: dict = {},
        routing_key: str = "",
        **kwargs: dict,
    ):
        self.logger.info("Notifying Ilert", extra=locals())
        if _type == "incident":
            return self.__create_or_update_incident(
                summary, status, message, affectedServices, id
            )
        else:
            return self.__post_ilert_event(
                event_type,
                summary,
                details,
                alert_key,
                priority,
                images,
                links,
                custom_details,
                routing_key,
            )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    api_key = os.environ.get("ILERT_API_TOKEN")

    provider_config = {
        "authentication": {"ilert_token": api_key},
    }
    provider: IlertProvider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="ilert",
        provider_type="ilert",
        provider_config=provider_config,
    )
    # Fetch all incidents
    all_incidents = provider.fetch_all_incidents()
    print(json.dumps(all_incidents, indent=4))
