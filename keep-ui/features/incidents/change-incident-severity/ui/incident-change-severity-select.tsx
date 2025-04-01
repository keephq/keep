import { useIncidentActions } from "@/entities/incidents/model";
import React, { useCallback } from "react";
import { Severity } from "@/entities/incidents/model/models";
import { IncidentSeveritySelect } from "./incident-severity-select";

type Props = {
  incidentId: string;
  value: Severity;
  onChange?: (status: Severity) => void;
  className?: string;
};

export function IncidentChangeSeveritySelect({
  incidentId,
  value,
  onChange,
  className,
}: Props) {
  const { changeSeverity } = useIncidentActions();

  const handleChange = useCallback(
    (value: any) => {
      const _asyncUpdate = async (val: any) => {
        await changeSeverity(incidentId, val || null);
        onChange?.(val || null);
      };
      _asyncUpdate(value);
    },
    [incidentId, changeSeverity, onChange]
  );

  return (
    <IncidentSeveritySelect
      className={className}
      value={value}
      onChange={handleChange}
    />
  );
}
