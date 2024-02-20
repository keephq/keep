import copy
import hashlib
import json
import logging

import celpy

from keep.api.core.db import get_alert_by_hash, get_all_filters
from keep.api.models.alert import AlertDto


# decide whether this should be a singleton so that we can keep the filters in memory
class AlertDeduplicator:
    # this fields will be removed from the alert before hashing
    # TODO: make this configurable
    DEFAULT_FIELDS = ["lastReceived"]

    def __init__(self, tenant_id):
        self.filters = get_all_filters(tenant_id)
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id

    def is_deduplicated(self, alert: AlertDto) -> bool:
        # Apply all deduplication filters
        for filt in self.filters:
            alert = self._apply_deduplication_filter(filt, alert)

        # Remove default fields
        for field in AlertDeduplicator.DEFAULT_FIELDS:
            alert = self._remove_field(field, alert)

        # Calculate the hash
        alert_hash = hashlib.sha256(
            json.dumps(alert.dict(), default=str).encode()
        ).hexdigest()

        # Check if the hash is already in the database
        alert_deduplicate = (
            True if get_alert_by_hash(self.tenant_id, alert_hash) else False
        )
        return alert_hash, alert_deduplicate

    def _run_matcher(self, matcher, alert: AlertDto) -> bool:
        # run the CEL matcher
        env = celpy.Environment()
        ast = env.compile(matcher)
        prgm = env.program(ast)
        activation = celpy.json_to_cel(
            json.loads(json.dumps(alert.dict(), default=str))
        )
        try:
            r = prgm.evaluate(activation)
        except celpy.evaluation.CELEvalError as e:
            # this is ok, it means that the subrule is not relevant for this event
            if "no such member" in str(e):
                return False
            # unknown
            raise
        return True if r else False

    def _apply_deduplication_filter(self, filt, alert: AlertDto) -> AlertDto:
        # check if the matcher applies
        filter_apply = self._run_matcher(filt.matcher_cel, alert)
        if not filter_apply:
            self.logger.debug(f"Filter {filt.id} did not match")
            return alert

        # remove the fields
        for field in filt.fields:
            alert = self._remove_field(field, alert)

        return alert

    def _remove_field(self, field, alert: AlertDto) -> AlertDto:
        # remove the field from the alert
        alert = copy.deepcopy(alert)
        field_parts = field.split(".")
        # if its not a nested field
        if len(field_parts) == 1:
            try:
                delattr(alert, field)
            except AttributeError:
                self.logger.warning("Failed to delete attribute {field} from alert")
                pass
        # if its a nested field, copy the dictionaty and remove the field
        # this is for cases such as labels/tags
        else:
            alert_attr = field_parts[0]
            d = copy.deepcopy(getattr(alert, alert_attr))
            for part in field_parts[1:-1]:
                d = d[part]
            del d[field_parts[-1]]
            setattr(alert, field_parts[0], d)
        return alert
