import { Table } from "@tanstack/table-core";
import { Subtitle } from "@tremor/react";
import { AlertDto } from "./models";
import { MouseEventHandler } from "react";
import Select, {
  components,
  MultiValueGenericProps,
  MultiValueProps,
  Props,
} from "react-select";
import {
  SortableContainer,
  SortableContainerProps,
  SortableElement,
  SortEndHandler,
  SortableHandle,
} from "react-sortable-hoc";
import { Column } from "@tanstack/react-table";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  columnOrder: string[];
  presetName?: string;
  isLoading: boolean;
  setColumnVisibility: any;
}

export interface Option {
  readonly value: string;
  readonly label: string;
  readonly color: string;
  readonly isFixed?: boolean;
  readonly isDisabled?: boolean;
}

function arrayMove<T>(array: readonly T[], from: number, to: number) {
  const slicedArray = array.slice();
  slicedArray.splice(
    to < 0 ? array.length + to : to,
    0,
    slicedArray.splice(from, 1)[0]
  );
  return slicedArray;
}

const columnsWithFixedPosition = ["alertMenu", "checkbox"];

const SortableMultiValue = SortableElement((props: MultiValueProps<Option>) => {
  // this prevents the menu from being opened/closed when the user clicks
  // on a value to begin dragging it. ideally, detecting a click (instead of
  // a drag) would still focus the control and toggle the menu, but that
  // requires some magic with refs that are out of scope for this example
  const onMouseDown: MouseEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };
  const innerProps = { ...props.innerProps, onMouseDown };
  return <components.MultiValue {...props} innerProps={innerProps} />;
});

const SortableMultiValueLabel = SortableHandle(
  (props: MultiValueGenericProps) => <components.MultiValueLabel {...props} />
);

const SortableSelect = SortableContainer(Select) as React.ComponentClass<
  Props<Option, true> & SortableContainerProps
>;

const convertColumnToOption = (column: any) => {
  return {
    label: column.id,
    value: column.id,
    isFixed: columnsWithFixedPosition.includes(column.id),
  } as Option;
};

export const getHiddenColumnsLocalStorageKey = (
  presetName: string = "default"
) => {
  return `hiddenFields-${presetName}`;
};

export const getColumnsOrderLocalStorageKey = (
  presetName: string = "default"
) => {
  return `columnsOrder-${presetName}`;
};

const filterFixedPositionColumns = (column: Column<AlertDto, unknown>) => {
  return !columnsWithFixedPosition.includes(column.id);
};

export default function AlertColumnsSelect({
  table,
  presetName,
  setColumnVisibility,
  isLoading,
  columnOrder,
}: AlertColumnsSelectProps) {
  const columnsOptions = table
    .getAllLeafColumns()
    .filter(filterFixedPositionColumns)
    .map(convertColumnToOption);
  const selectedColumns = table
    .getAllColumns()
    .filter((col) => col.getIsVisible() && filterFixedPositionColumns(col))
    .map(convertColumnToOption)
    .sort(
      (a, b) => columnOrder.indexOf(a.label) - columnOrder.indexOf(b.label)
    );

  const onChange = (valueKeys: string[]) => {
    const hiddenColumns = table
      .getAllColumns()
      .filter((col) => !valueKeys.includes(col.id))
      .map((col) => col.id)
      .reduce((obj, key) => {
        // { "columnX": false, "columnY": false }
        obj[key] = false;
        return obj;
      }, {} as any);
    // This is where visibility is being actually saved
    localStorage.setItem(
      getHiddenColumnsLocalStorageKey(presetName),
      JSON.stringify(hiddenColumns)
    );
    setColumnVisibility(hiddenColumns);
    saveColumnsOrder(valueKeys);
  };

  const saveColumnsOrder = (newColumnsOrder: string[]) => {
    table.setColumnOrder(newColumnsOrder);
    // This is where ordering is being actually saved
    localStorage.setItem(
      getColumnsOrderLocalStorageKey(presetName),
      JSON.stringify(newColumnsOrder)
    );
  };

  const onSortEnd: SortEndHandler = ({ oldIndex, newIndex }) => {
    const newColumnsOrder = arrayMove(selectedColumns, oldIndex, newIndex);
    // todo (tb): this is a stupid hack to keep the checkbox and alertMenu columns in fixed positions
    const newColumnsByKey = [
      "checkbox",
      ...newColumnsOrder.map((v) => v.value),
      "alertMenu",
    ];
    saveColumnsOrder(newColumnsByKey);
  };

  return (
    <>
      <Subtitle>Columns</Subtitle>
      <SortableSelect
        isMulti
        isClearable={false}
        axis="xy"
        useDragHandle
        value={selectedColumns}
        options={columnsOptions}
        isDisabled={isLoading}
        closeMenuOnSelect={false}
        getHelperDimensions={({ node }) => node.getBoundingClientRect()}
        components={{
          // @ts-ignore We're failing to provide a required index prop to SortableElement
          MultiValue: SortableMultiValue,
          // @ts-ignore same as above
          MultiValueLabel: SortableMultiValueLabel,
        }}
        onSortEnd={onSortEnd}
        onChange={(value) =>
          // todo (tb): this is a stupid hack to keep the checkbox and alertMenu columns displayed
          onChange(["checkbox", ...value.map((v) => v.value), "alertMenu"])
        }
      />
    </>
  );
}
