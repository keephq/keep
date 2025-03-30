import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

from keep.api.consts import PROVIDER_POLL_INTERVAL_MINUTE
from keep.api.core.config import config
from keep.api.core.db import update_provider_last_pull_time
from keep.api.models.db.provider import Provider
from keep.api.tasks.process_event_task import (
    process_event,
    process_incident,
    process_topology,
)
from keep.providers.base.base_provider import BaseIncidentProvider, BaseTopologyProvider
from keep.providers.providers_factory import ProvidersFactory


class EventPoller:
    _instance = None
    _lock = threading.Lock()

    @staticmethod
    def get_instance() -> "EventPoller":
        with EventPoller._lock:
            if EventPoller._instance is None:
                EventPoller._instance = EventPoller()
        return EventPoller._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pollers: List[Provider] = []
        self.poll_thread_pool: Optional[ThreadPoolExecutor] = None
        self.started = False
        self.poll_interval = 60  # Default poll check interval in seconds
        self._stop_event = threading.Event()
        self._poll_scheduler_thread = None
        self.polling_status: Dict[str, Dict] = {}
        self.max_workers = config("KEEP_POLLER_MAX_WORKERS", default=5, cast=int)

    def status(self):
        """Returns the status of the pollers"""
        return {
            "started": self.started,
            "pollers_count": len(self.pollers),
            "polling_status": self.polling_status,
        }

    async def start(self):
        """Start the poller thread pool"""
        if self.started:
            self.logger.info("Event Poller already started")
            return

        self.logger.info("Starting event poller")
        self._stop_event.clear()

        # Get all polling providers
        self.pollers = ProvidersFactory.get_polling_providers()
        self.logger.info(f"Found {len(self.pollers)} polling providers")

        # Initialize the thread pool
        self.poll_thread_pool = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="event_poller_"
        )

        # Start the polling scheduler in a separate thread
        self._poll_scheduler_thread = threading.Thread(
            target=self._poll_scheduler, name="poll_scheduler", daemon=True
        )
        self._poll_scheduler_thread.start()

        self.started = True
        self.logger.info("Event poller started successfully")

    def stop(self):
        """Stops the poller thread pool"""
        if not self.started:
            self.logger.info("Event Poller is not running")
            return

        self.logger.info("Stopping event poller")
        self._stop_event.set()

        if self._poll_scheduler_thread:
            self._poll_scheduler_thread.join(timeout=5.0)

        if self.poll_thread_pool:
            self.poll_thread_pool.shutdown(wait=True, cancel_futures=True)
            self.poll_thread_pool = None

        self.started = False
        self.polling_status = {}
        self.logger.info("Event poller stopped")

    def _poll_scheduler(self):
        """
        Continuously checks which providers need polling and submits
        polling tasks to the thread pool
        """
        self.logger.info("Poll scheduler started")

        while not self._stop_event.is_set():
            try:
                current_time = datetime.now()

                # Refresh the list of polling providers periodically
                if not self._stop_event.is_set():
                    self.pollers = ProvidersFactory.get_polling_providers()

                for provider in self.pollers:
                    # Skip if provider has polling disabled
                    if not provider.pulling_enabled:
                        continue

                    provider_key = f"{provider.type}_{provider.id}"

                    # Check if enough time has passed since the last poll
                    should_poll = False
                    if provider.last_poll_time is None:
                        # Never polled before
                        should_poll = True
                    else:
                        minutes_passed = (
                            current_time - provider.last_poll_time
                        ).total_seconds() / 60
                        should_poll = minutes_passed > PROVIDER_POLL_INTERVAL_MINUTE

                    # If polling is due and not already in progress
                    if should_poll and (
                        provider_key not in self.polling_status
                        or self.polling_status[provider_key].get("status")
                        != "in_progress"
                    ):

                        self.polling_status[provider_key] = {
                            "status": "in_progress",
                            "started_at": current_time,
                            "provider_type": provider.type,
                            "provider_id": provider.id,
                        }

                        # Submit task to thread pool
                        self.poll_thread_pool.submit(
                            self._poll_provider, provider, provider_key
                        )

            except Exception as e:
                self.logger.exception(f"Error in poll scheduler: {str(e)}")

            # Sleep for the poll interval
            self._stop_event.wait(self.poll_interval)

        self.logger.info("Poll scheduler stopped")

    def _poll_provider(self, provider: Provider, provider_key: str):
        """
        Poll a specific provider for data

        Args:
            provider: The provider to poll
            provider_key: Unique identifier for this provider
        """
        tenant_id = provider.tenant_id
        trace_id = f"poll_{provider_key}_{int(time.time())}"
        start_time = datetime.now()

        extra = {
            "provider_type": provider.type,
            "provider_id": provider.id,
            "tenant_id": tenant_id,
            "trace_id": trace_id,
        }

        try:
            self.logger.info(
                f"Polling provider {provider.type} ({provider.id})", extra=extra
            )

            # Update last poll time
            update_provider_last_pull_time(tenant_id=tenant_id, provider_id=provider.id)

            # Get provider implementation
            provider_class = ProvidersFactory.get_installed_provider(
                tenant_id=tenant_id,
                provider_id=provider.id,
                provider_type=provider.type,
            )

            # Get alerts by fingerprint
            sorted_provider_alerts_by_fingerprint = (
                provider_class.get_alerts_by_fingerprint(tenant_id=tenant_id)
            )
            self.logger.info(
                f"Pulled {len(sorted_provider_alerts_by_fingerprint)} alerts from provider {provider.type} ({provider.id})",
                extra=extra,
            )

            # Handle incidents if provider supports it
            self._poll_incidents(provider_class, tenant_id, provider, trace_id, extra)

            # Handle topology if provider supports it
            self._poll_topology(provider_class, tenant_id, provider, extra)

            # Process alerts
            for fingerprint, alert in sorted_provider_alerts_by_fingerprint.items():
                process_event(
                    {},
                    tenant_id,
                    provider.type,
                    provider.id,
                    fingerprint,
                    None,
                    trace_id,
                    alert,
                    notify_client=False,
                )

            # Update polling status
            self.polling_status[provider_key] = {
                "status": "completed",
                "started_at": start_time,
                "completed_at": datetime.now(),
                "provider_type": provider.type,
                "provider_id": provider.id,
                "alerts_count": len(sorted_provider_alerts_by_fingerprint),
            }

        except Exception as e:
            self.logger.exception(
                f"Error polling provider {provider.type} ({provider.id})",
                extra={**extra, "exception": str(e)},
            )

            # Update polling status with error
            self.polling_status[provider_key] = {
                "status": "error",
                "started_at": start_time,
                "error_at": datetime.now(),
                "provider_type": provider.type,
                "provider_id": provider.id,
                "error": str(e),
            }

    def _poll_incidents(self, provider_class, tenant_id, provider, trace_id, extra):
        """Poll incidents if the provider supports it"""
        if not isinstance(provider_class, BaseIncidentProvider):
            self.logger.debug(
                f"Provider {provider.type} ({provider.id}) does not implement pulling incidents",
                extra=extra,
            )
            return

        try:
            incidents = provider_class.get_incidents()
            process_incident(
                {},
                tenant_id=tenant_id,
                provider_id=provider.id,
                provider_type=provider.type,
                incidents=incidents,
                trace_id=trace_id,
            )
        except NotImplementedError:
            self.logger.debug(
                f"Provider {provider.type} ({provider.id}) does not implement pulling incidents",
                extra=extra,
            )
        except Exception as e:
            self.logger.exception(
                f"Unknown error pulling incidents from provider {provider.type} ({provider.id})",
                extra={**extra, "trace_id": trace_id, "exception": str(e)},
            )

    def _poll_topology(self, provider_class, tenant_id, provider, extra):
        """Poll topology data if the provider supports it"""
        try:
            if isinstance(provider_class, BaseTopologyProvider):
                self.logger.info("Pulling topology data", extra=extra)
                topology_data, _ = provider_class.pull_topology()
                self.logger.info(
                    "Pulling topology data finished, processing",
                    extra={**extra, "topology_length": len(topology_data)},
                )
                process_topology(tenant_id, topology_data, provider.id, provider.type)
                self.logger.info("Finished processing topology data", extra=extra)
        except NotImplementedError:
            self.logger.debug(
                f"Provider {provider.type} ({provider.id}) does not implement pulling topology data",
                extra=extra,
            )
        except Exception as e:
            self.logger.exception(
                f"Unknown error pulling topology from provider {provider.type} ({provider.id})",
                extra={**extra, "exception": str(e)},
            )
