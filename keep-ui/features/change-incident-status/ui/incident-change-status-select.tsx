import clsx from "clsx";
// TODO: Move to entities/incidents/model/models.ts
import { Status } from "../../../app/incidents/models";
// TODO: Move to entities/incidents/ui/statuses.ts
import { STATUS_ICONS } from "../../../app/incidents/statuses";
import Select, { ClassNamesConfig } from "react-select";
import { useIncidentActions } from "@/entities/incidents/model/useIncidentActions";
import { useCallback, useEffect, useMemo, useRef } from "react";

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
  value: Status;
  onChange?: (status: Status) => void;
};

export function IncidentChangeStatusSelect({
  incidentId,
  value,
  onChange,
}: Props) {
  // Use a portal to render the menu outside the table container with overflow: hidden
  const menuPortalTarget = useRef<HTMLElement | null>(null);
  useEffect(() => {
    menuPortalTarget.current = document.body;
  }, []);

  const { changeStatus } = useIncidentActions();
  const statusOptions = useMemo(
    () =>
      Object.values(Status).map((status) => ({
        value: status,
        label: (
          <div className="flex items-center">
            {STATUS_ICONS[status]}
            <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
          </div>
        ),
      })),
    [Status]
  );

  const handleChange = useCallback(
    (option: any) => {
      const _asyncUpdate = async (option: any) => {
        await changeStatus(incidentId, option?.value || null);
        onChange?.(option?.value || null);
      };
      _asyncUpdate(option);
    },
    [incidentId, changeStatus, onChange]
  );

  const selectedOption = useMemo(
    () => statusOptions.find((option) => option.value === value),
    [value]
  );

  return (
    <Select
      isSearchable={false}
      options={statusOptions}
      value={selectedOption}
      onChange={handleChange}
      placeholder="Status"
      classNames={customClassNames}
      menuPortalTarget={menuPortalTarget.current}
      menuPosition="fixed"
    />
  );
}
