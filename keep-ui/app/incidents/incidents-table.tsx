import {
  Button,
  Badge,
} from "@tremor/react";
import {
  ExpandedState,
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
  SortingState,
  getSortedRowModel,
  ColumnDef,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { useSession } from "next-auth/react";
import {IncidentDto, PaginatedIncidentsDto} from "./model";
import React, {Dispatch, SetStateAction, useEffect, useState} from "react";
import Image from "next/image";
import IncidentPagination from "./incident-pagination";
import IncidentTableComponent from "./incident-table-component";
import {deleteIncident} from "./incident-candidate-actions";

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  mutate: () => void;
  sorting: SortingState,
  setSorting: Dispatch<SetStateAction<any>>;
  setPagination: Dispatch<SetStateAction<any>>;
  editCallback: (rule: IncidentDto) => void;
}

export default function IncidentsTable({
  incidents: incidents,
  mutate,
  setPagination,
  sorting,
  setSorting,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [pagination, setTablePagination] = useState({
    pageIndex: Math.ceil(incidents.offset / incidents.limit),
    pageSize: incidents.limit,
  });

  useEffect(() => {
    if (incidents.limit != pagination.pageSize) {
      setPagination({
        limit: pagination.pageSize,
        offset: 0,
      })
    }
    const currentOffset = pagination.pageSize * pagination.pageIndex;
    if (incidents.offset != currentOffset) {
      setPagination({
        limit: pagination.pageSize,
        offset: currentOffset,
      })
    }
  }, [pagination])

  const columns = [
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: ({ row }) => (
        <div className="text-wrap">
          {row.original.user_generated_name || row.original.ai_generated_name}
        </div>
      ),
    }),
    columnHelper.display({
      id: "user_summary",
      header: "Summary",
      cell: ({ row }) => <div className="text-wrap">{row.original.user_summary}</div>,
    }),
    columnHelper.display({
      id: "rule_fingerprint",
      header: "Group by value",
      cell: ({ row }) => <div className="text-wrap">{row.original.rule_fingerprint || "-"}</div>,
    }),
    columnHelper.accessor("severity", {
      id: "severity",
      header: "Severity",
      cell: (context) => {
        const severity = context.row.original.severity;
        let color;
        if (severity === "critical") color = "red";
        else if (severity === "info") color = "blue";
        else if (severity === "warning") color = "yellow";
        return <Badge color={color}>{severity}</Badge>;
      },
    }),
    columnHelper.accessor("alerts_count", {
      id: "alerts_count",
      header: "Number of Alerts",
    }),
    columnHelper.display({
      id: "alert_sources",
      header: "Alert Sources",
      cell: (context) =>
        context.row.original.alert_sources.map((alert_sources, index) => (
          <Image
            className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
            key={alert_sources}
            alt={alert_sources}
            height={24}
            width={24}
            title={alert_sources}
            src={`/icons/${alert_sources}-icon.png`}
          />
        )),
    }),
    columnHelper.display({
      id: "services",
      header: "Involved Services",
      cell: ({row}) =>
        <div className="text-wrap">{row.original.services.map((service) =>
          <Badge key={service} className="mr-1">{service}</Badge>
        )}
      </div>,
    }),
    columnHelper.display({
      id: "assignee",
      header: "Assignee",
      cell: ({row}) => row.original.assignee
    }),
    columnHelper.accessor("creation_time", {
      id: "creation_time",
      header: "Created At",
      cell: ({ row }) =>
        new Date(row.original.creation_time + "Z").toLocaleString(),
    }),
    columnHelper.display({
      id: "delete",
      header: "",
      cell: (context) => (
        <div className={"space-x-1 flex flex-row items-center justify-center"}>
          {/*If user wants to edit the mapping. We use the callback to set the data in mapping.tsx which is then passed to the create-new-mapping.tsx form*/}
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdModeEdit}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              editCallback(context.row.original!);
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            icon={MdRemoveCircle}
            onClick={async (e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              await deleteIncident({incidentId: context.row.original.id!, mutate, session});
            }}
          />
        </div>
      ),
    }),
  ] as ColumnDef<IncidentDto>[];

  const table = useReactTable({
    columns,
    data: incidents.items,
    state: { expanded, pagination, sorting },
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: incidents.count,
    onPaginationChange: setTablePagination,
    onExpandedChange: setExpanded,
    onSortingChange: (value) => {
      if (typeof value === "function") {
        setSorting(value)
      }
    },
    getSortedRowModel: getSortedRowModel(),
    enableSorting: true,
    enableMultiSort: false,
    manualSorting: true,
    debugTable: true,
  });

  return (
    <div>
      <IncidentTableComponent table={table} />
      <div className="mt-4 mb-8">
        <IncidentPagination table={table}  isRefreshAllowed={true}/>
      </div>
    </div>
  );
}
