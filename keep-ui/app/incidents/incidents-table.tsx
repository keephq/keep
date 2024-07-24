import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Badge,
} from "@tremor/react";
import {
  DisplayColumnDef,
  ExpandedState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import {IncidentDto, PaginatedIncidentsDto} from "./model";
import React, {Dispatch, SetStateAction, useEffect, useState} from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import IncidentPagination from "./incident-pagination";

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  mutate: () => void;
  setPagination: Dispatch<SetStateAction<any>>;
  editCallback: (rule: IncidentDto) => void;
}

export default function IncidentsTable({
  incidents: incidents,
  mutate,
  setPagination,
  editCallback,
}: Props) {
  const router = useRouter();
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
      cell: ({ row }) => <div className="text-wrap">{row.original.name}</div>,
    }),
    columnHelper.display({
      id: "description",
      header: "Description",
      cell: ({ row }) => <div className="text-wrap">{row.original.description}</div>,
    }),
    // columnHelper.display({
    //   id: "severity",
    //   header: "Severity",
    //   cell: (context) => {
    //     const severity = context.row.original.severity;
    //     let color;
    //     if (severity === "critical") color = "red";
    //     else if (severity === "info") color = "blue";
    //     else if (severity === "warning") color = "yellow";
    //     return <Badge color={color}>{severity}</Badge>;
    //   },
    // }),
    columnHelper.display({
      id: "alert_count",
      header: "Number of Alerts",
      cell: (context) => context.row.original.number_of_alerts,
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
      cell: (context) => context.row.original.assignee,
    }),
    columnHelper.display({
      id: "created_at",
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
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              deleteIncident(context.row.original.id!);
            }}
          />
        </div>
      ),
    }),
  ] as DisplayColumnDef<IncidentDto>[];

  const table = useReactTable({
    columns,
    data: incidents.items,
    state: { expanded, pagination },
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: incidents.count,
    onPaginationChange: setTablePagination,
    onExpandedChange: setExpanded,
  });

  const deleteIncident = (incidentId: string) => {
    const apiUrl = getApiURL();
    if (confirm("Are you sure you want to delete this incident?")) {
      fetch(`${apiUrl}/incidents/${incidentId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      }).then((response) => {
        if (response.ok) {
          mutate();
          toast.success("Incident deleted successfully");
        } else {
          toast.error("Failed to delete incident, contact us if this persists");
        }
      });
    }
  };

  return (
    <div>
      <Table className="mt-4">
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow
              className="border-b border-tremor-border dark:border-dark-tremor-border"
              key={headerGroup.id}
            >
              {headerGroup.headers.map((header) => {
                return (
                  <TableHeaderCell
                    className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
                    key={header.id}
                  >
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  </TableHeaderCell>
                );
              })}
            </TableRow>
          ))}
        </TableHead>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <>
              <TableRow
                className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 cursor-pointer"
                key={row.id}
                onClick={() => {
                  router.push(`/incidents/${row.original.id}`);
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            </>
          ))}
        </TableBody>
      </Table>
      <div className="mt-4 mb-8">
        <IncidentPagination table={table}  isRefreshAllowed={true}/>
      </div>
    </div>
  );
}
