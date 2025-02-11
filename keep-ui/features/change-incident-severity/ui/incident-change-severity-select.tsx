import clsx from "clsx";
import { Status } from "@/entities/incidents/model";
import {IncidentSeverityBadge, STATUS_ICONS} from "@/entities/incidents/ui";
import Select, { ClassNamesConfig } from "react-select";
import { useIncidentActions } from "@/entities/incidents/model";
import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { capitalize } from "@/utils/helpers";
import {Severity} from "@/entities/incidents/model/models";
import {getIncidentSeverityIconAndColor} from "@/entities/incidents/lib/utils";
import {ExclamationCircleIcon} from "@heroicons/react/24/outline";
import {Icon} from "@tremor/react";

const customClassNames: ClassNamesConfig<any, false, any> = {
  container: () => "inline-flex",
  control: (state) =>
    clsx(
      "p-1 min-w-14 !rounded-full !min-h-0",
      state.isFocused ? "border-orange-500" : ""
    ),
  valueContainer: () => "!p-0",
  dropdownIndicator: () => "!p-0",
  indicatorSeparator: () => "hidden",
  menuList: () => "!p-0",
  menu: () => "!p-0 !overflow-hidden min-w-36",
  option: (state) =>
    clsx(
      "!p-1",
      state.isSelected ? "!bg-orange-500 !text-white [&_svg]:text-white" : "",
      state.isFocused && !state.isSelected ? "!bg-slate-100" : ""
    ),
};

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
  // Use a portal to render the menu outside the table container with overflow: hidden
  const menuPortalTarget = useRef<HTMLElement | null>(null);
  useEffect(() => {
    menuPortalTarget.current = document.body;
  }, []);

  const { changeSeverity } = useIncidentActions();

  const severityOptions = useMemo(
    () =>
      Object.values(Severity).map((severity) => {
        const { icon, color } = getIncidentSeverityIconAndColor(severity);
        return {
          value: severity,
          label: (
            <div className="flex items-center">
              <Icon
                icon={icon}
                tooltip={capitalize(severity)}
                color={color}
                className="w-4 h-4 mr-2"
              />
              <span>{capitalize(severity)}</span>
            </div>
          ),
        }
      }), []
  );

  const handleChange = useCallback(
    (option: any) => {
      const _asyncUpdate = async (option: any) => {
        await changeSeverity(incidentId, option?.value || null);
        onChange?.(option?.value || null);
      };
      _asyncUpdate(option);
    },
    [incidentId, changeSeverity, onChange]
  );

  const selectedOption = useMemo(
    () => severityOptions.find((option) => option.value === value),
    [severityOptions, value]
  );

  return (
    <Select
      className={className}
      isSearchable={false}
      options={severityOptions}
      value={selectedOption}
      onChange={handleChange}
      placeholder="Severity"
      classNames={customClassNames}
      menuPortalTarget={menuPortalTarget.current}
      menuPosition="fixed"
    />
  );
}
