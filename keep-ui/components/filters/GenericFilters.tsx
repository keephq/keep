import GenericPopover from "@/components/popover/GenericPopover";
import { Textarea, Badge, Button, Tab, TabGroup, TabList } from "@tremor/react";
import moment from "moment";
import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { useRef, useState, useEffect, ChangeEvent } from "react";
import { GoPlusCircle } from "react-icons/go";
import { DateRangePicker, DateRangePickerValue, Title } from "@tremor/react";
import { MdOutlineDateRange } from "react-icons/md";
import { IconType } from "react-icons";
import { endOfDay } from "date-fns";


type Filter = {
  key: string;
  value: string | string[] | Record<string, string>;
  type: string;
  options?: { value: string; label: string }[];
  name: string;
  icon?: IconType;
};

interface FiltersProps {
  filters: Filter[];
}

interface PopoverContentProps {
  filterRef: React.MutableRefObject<Filter[]>;
  filterKey: string;
  type: string;
}

function toArray(value: string | string[]) {
  if (!value) return [];

  if (!Array.isArray(value) && value) {
    return [value];
  }
  return value;
}

// TODO: Testing is needed
function CustomSelect({
  filter,
  setLocalFilter,
}: {
  filter: Filter | null;
  setLocalFilter: (value: string | string[]) => void;
}) {
  const filterKey = filter?.key || "";
  const [selectedOptions, setSelectedOptions] = useState<Set<string>>(
    new Set<string>()
  );

  useEffect(() => {
    if (filter) {
      setSelectedOptions(new Set(toArray(filter.value as string | string[])));
    }
  }, [filter]);

  const handleCheckboxChange = (option: string, checked: boolean) => {
    setSelectedOptions((prev) => {
      const updatedOptions = new Set(prev);
      if (checked) {
        updatedOptions.add(option);
      } else {
        updatedOptions.delete(option);
      }
      if (filter) {
        setLocalFilter(Array.from(updatedOptions));
        // setFilter((prev) => ({ ...prev, ...filter }));
      }
      return updatedOptions;
    });
  };

  if (!filter) {
    return null;
  }

  return (
    <>
      <span className="text-gray-400 text-sm">
        Select {filterKey?.charAt(0)?.toUpperCase() + filterKey?.slice(1)}
      </span>
      <ul className="flex flex-col mt-3 max-h-96 overflow-auto">
        {filter.options?.map((option) => (
          <li key={option.value}>
            <label className="cursor-pointer p-2 flex items-center">
              <input
                className="mr-2"
                type="checkbox"
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  handleCheckboxChange(option.value, e.target.checked)
                }
                checked={selectedOptions.has(option.value)}
              />
              {option.label}
            </label>
          </li>
        ))}
      </ul>
    </>
  );
}

function getParsedValue(filter: Filter) {
  const value = filter?.value as string;
  if (!value) {
    return 0;
  }
  if (typeof value !== "string") {
    return 0;
  }
  try {
    return JSON.parse(value) || {};
  } catch (e) {
    return 0;
  }
}

function CustomDate({
  filter,
  handleDate,
}: {
  filter: Filter | null;
  handleDate: (from?: Date, to?: Date) => void;
}) {
  const [dateRange, setDateRange] = useState<DateRangePickerValue>({
    from: undefined,
    to: undefined,
  });

  const onDateRangePickerChange = ({
    from: start,
    to: end,
  }: DateRangePickerValue) => {
    const endDate = end || start;
    const endOfDayDate = endDate ? endOfDay(endDate) : end;


    setDateRange({ from: start ?? undefined, to: endOfDayDate ?? undefined });
    handleDate(start, endOfDayDate);
  };

  useEffect(() => {
    if (filter) {
      const filterValue = getParsedValue(filter!);
      const from = filterValue.start ? new Date(filterValue.start) : undefined;
      const to = filterValue.end ? new Date(filterValue.end) : undefined;
      onDateRangePickerChange({ from, to });
    }
  }, [filter?.value]);

  if (!filter) return null;

  return (
    <div className="flex justify-center items-center m-x-4">
      <DateRangePicker
        value={dateRange}
        onValueChange={onDateRangePickerChange}
        enableYearNavigation
      />
    </div>
  );
}

const PopoverContent: React.FC<PopoverContentProps> = ({
  filterRef,
  filterKey,
  type,
}) => {
  // Initialize local state for selected options

  const filter = filterRef.current?.find((filter) => filter.key === filterKey);

  const [localFilter, setLocalFilter] = useState<Filter | null>(null);

  useEffect(() => {
    if (filter) {
      setLocalFilter({ ...filter });
    }
  }, []);

  useEffect(() => {
    if (localFilter && filter) {
      filter.value = localFilter.value;
    }
  }, [localFilter?.value]);

  const handleLocalFilter = (value: string | string[]) => {
    if (filter) {
      filter.value = value;
    }
    setLocalFilter((prev) => {
      if (prev) {
        return { ...prev, value };
      }
      return null;
    });
  };

  const handleDate = (start?: Date, end?: Date) => {
    let newValue = ""
    if (!start && !end) {
      newValue = "";
    } else {
      newValue = JSON.stringify({
        start: start,
        end: end || start,
      });
    }
    if (filter) {
      filter.value = newValue;
    }
    setLocalFilter((prev) => {
      if (prev) {
        return { ...prev, value: newValue };
      }
      return null;
    });
  };

  // Return the appropriate content based on the selected type
  switch (type) {
    case "select":
      return (
        <CustomSelect filter={localFilter} setLocalFilter={handleLocalFilter} />
      );
    case "date":
      return <CustomDate filter={localFilter} handleDate={handleDate} />;
    default:
      return null;
  }
};

export const GenericFilters: React.FC<FiltersProps> = ({ filters }) => {
  // Initialize filterRef to store filter values
  const filterRef = useRef<Filter[]>(filters);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamString = searchParams?.toString();
  const [apply, setApply] = useState(false);

  useEffect(() => {
    if (apply && filterRef.current) {
      const newParams = new URLSearchParams(
        searchParams ? searchParams.toString() : ""
      );
      const keys = filterRef.current.map((filter) => filter.key);
      keys.forEach((key) => newParams.delete(key));
      for (const { key, value } of filterRef.current) {
        if (Array.isArray(value)) {
          for (const item of value) {
            newParams.append(key, item);
          }
        } else if (value && typeof value === "string") {
          newParams.append(key, value);
        } else if (value && typeof value === "object") {
          for (const [k, v] of Object.entries(value)) {
            newParams.append(`$[${k}]`, v);
          }
        }
      }

      router.push(`${pathname}?${newParams.toString()}`);
      setApply(false); // Reset apply state
    }
  }, [apply]);

  useEffect(() => {
    if (searchParams) {
      // Convert URLSearchParams to a key-value pair object
      const entries = Array.from(searchParams.entries());
      const params = entries.reduce((acc, [key, value]) => {
        if (key in acc) {
          if (Array.isArray(acc[key])) {
            acc[key] = [...acc[key], value];
            return acc;
          }else {
            acc[key] = [acc[key] as string, value];
          }
          return acc;
        }
        acc[key] = value;
        return acc;
      }, {} as Record<string, string | string[]>);

      // Update filterRef.current with the new params
      filterRef.current = filters.map((filter) => ({
        ...filter,
        value: params[filter.key] || "",
      }));
    }
  }, [searchParamString, filters]);
  // Handle textarea value change
  const onValueChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    //to do handle the value change
    e.preventDefault();
    if (filterRef.current) {
    }
  };

  // Handle key down event for textarea
  const handleKeyDown = (e: any) => {
    if (e.key === "Enter") {
      e.preventDefault();
      setApply(true);
    }
  };

  return (
    <div className="relative flex flex-col md:flex-row lg:flex-row gap-4 items-center">
      {filters &&
        filters?.map(({ key, type, name, icon }) => {
          //only type==select and date need popover i guess other text and textarea can be handled different. for now handling select and date
          icon = icon ?? type === "date" ? MdOutlineDateRange : GoPlusCircle;
          return (
            <div key={key} className="flex gap-4">
              <GenericPopover
                triggerText={name}
                triggerIcon={icon}
                content={
                  <PopoverContent
                    filterRef={filterRef}
                    filterKey={key}
                    type={type}
                  />
                }
                onApply={() => setApply(true)}
              />
            </div>
          );
        })}
      {/* TODO : Add clear filters functionality */}
      {/* <Button className="shadow-lg p-2" onClick={() => { filterRef.current = { trigger: [], status: [], execution_id: '' }; setApply(true) }}>Clear Filters</Button> */}
    </div>
  );
};
