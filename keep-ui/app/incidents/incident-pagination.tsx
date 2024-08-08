import {
  ArrowPathIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TableCellsIcon,
} from "@heroicons/react/24/outline";
import { Button, Text } from "@tremor/react";
import { StylesConfig, SingleValueProps, components, GroupBase } from 'react-select';
import Select from 'react-select';
import { Table } from "@tanstack/react-table";
import {IncidentDto} from "./model";
import {AlertDto} from "../alerts/models";

interface Props {
  table: Table<IncidentDto> | Table<AlertDto>;
  isRefreshAllowed: boolean;
}

interface OptionType {
  value: string;
  label: string;
}

const customStyles: StylesConfig<OptionType, false, GroupBase<OptionType>> = {
  control: (provided, state) => ({
    ...provided,
    borderColor: state.isFocused ? 'orange' : provided.borderColor,
    '&:hover': { borderColor: 'orange' },
    boxShadow: state.isFocused ? '0 0 0 1px orange' : provided.boxShadow,
  }),
  singleValue: (provided) => ({
    ...provided,
    display: 'flex',
    alignItems: 'center',
  }),
  menu: (provided) => ({
    ...provided,
    color: 'orange',
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected ? 'orange' : provided.backgroundColor,
    '&:hover': { backgroundColor: state.isSelected ? 'orange' : '#f5f5f5' },
    color: state.isSelected ? 'white' : provided.color,
  }),
};

const SingleValue = ({ children, ...props }: SingleValueProps<OptionType, false, GroupBase<OptionType>>) => (
  <components.SingleValue {...props}>
    {children}
    <TableCellsIcon className="w-4 h-4 ml-2" />
  </components.SingleValue>
);


export default function IncidentPagination({  table, isRefreshAllowed }: Props) {

  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();

  return (
    <div className="flex justify-between items-center">
      <Text>
        Showing {pageCount === 0 ? 0 : pageIndex + 1} of {pageCount}
      </Text>
      <div className="flex gap-1">
      <Select
        styles={customStyles}
        components={{ SingleValue }}
         value={{ value: table.getState().pagination.pageSize.toString(), label: table.getState().pagination.pageSize.toString() }}
         onChange={(selectedOption) => table.setPageSize(Number(selectedOption!.value))}
         options={[
           { value: "10", label: "10" },
           { value: "20", label: "20" },
           { value: "50", label: "50" },
           { value: "100", label: "100" },
         ]}
         menuPlacement="top"
        />
        <div className="flex">
          <Button
            icon={ChevronDoubleLeftIcon}
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronLeftIcon}
            onClick={table.previousPage}
            disabled={!table.getCanPreviousPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronRightIcon}
            onClick={table.nextPage}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
          <Button
            icon={ChevronDoubleRightIcon}
            onClick={() => table.setPageIndex(pageCount - 1)}
            disabled={!table.getCanNextPage()}
            size="xs"
            color="orange"
            variant="secondary"
          />
        </div>
      </div>
    </div>
  );
}
