import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Badge
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
import { IncidentDto } from "./model";
import React, { useState } from "react";
import { useIncidents } from "utils/hooks/useIncidents";
import { useRouter } from "next/navigation";
import Image from "next/image";

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: IncidentDto[];
  editCallback: (rule: IncidentDto) => void;
}

export default function IncidentsTable({
  incidents: incidents,
  editCallback,
}: Props) {
  const router = useRouter();
  const { data: session } = useSession();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const { mutate } = useIncidents();

  const columns = [
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: ({ row }) => row.original.name,
    }),
    columnHelper.display({
      id: "description",
      header: "Description",
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
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
    columnHelper.display({
      id: "alert_count",
      header: "Number of Alerts",
      cell: (context) => context.row.original.number_of_alerts,
    }),
    columnHelper.display({
      id: "alert_sources",
      header: "Alert Sources",
      cell: (context) =>
        (context.row.original.alert_sources.map((alert_sources, index) => (
          <Image
            className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
            key={alert_sources}
            alt={alert_sources}
            height={24}
            width={24}
            title={alert_sources}
            src={`/icons/${alert_sources}-icon.png`}
          />
        ))
    )}),
    columnHelper.display({
      id: "services",
      header: "Involved Services",
      cell: (context) => context.row.original.services.map((service) =>
        <Badge className="mr-1">{service}</Badge>
      ),
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
    data: incidents,
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
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
    <Table className="mt-4 [&>table]:table-fixed [&>table]:w-full h-full">
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
  );
}
