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
import { MdDone, MdBlock} from "react-icons/md";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import {IncidentDto, PaginatedIncidentsDto} from "./model";
import React, { useState } from "react";
import Image from "next/image";

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  mutate: () => void;
  editCallback: (rule: IncidentDto) => void;
}

export default function PredictedIncidentsTable({
  incidents: incidents,
  mutate,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const handleConfirmPredictedIncident = async (incidentId: string) => {
    const apiUrl = getApiURL();
    const response = await fetch(
      `${apiUrl}/incidents/${incidentId}/confirm`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
      }
    );
    if (response.ok) {
      await mutate();
      toast.success("Predicted incident confirmed successfully");
    } else {
      toast.error(
        "Failed to confirm predicted incident, please contact us if this issue persists."
      );
    }
  }

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
      cell: ({row}) => <div className="text-wrap">{row.original.services.map((service) =>
          <Badge key={service} className="mr-1">{service}</Badge>
        )}
      </div>,
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
            tooltip="Confirm incident"
            variant="secondary"
            icon={MdDone}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              handleConfirmPredictedIncident(context.row.original.id!);
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            tooltip={"Discard"}
            icon={MdBlock}
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
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  const deleteIncident = (incidentFingerprint: string) => {
    const apiUrl = getApiURL();
    if (confirm("Are you sure you want to delete this incident?")) {
      fetch(`${apiUrl}/incidents/${incidentFingerprint}`, {
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
              className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100"
              key={row.id}
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
