import {
  Button,
  Badge
} from "@tremor/react";
import {
  DisplayColumnDef,
  ExpandedState,
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdDone, MdBlock} from "react-icons/md";
import { useSession } from "next-auth/react";
import {IncidentDto, PaginatedIncidentsDto} from "./model";
import React, { useState } from "react";
import Image from "next/image";
import { IncidentTableComponent } from "./incident-table-component";
import {deleteIncident, handleConfirmPredictedIncident} from "./incident-candidate-actions";

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
            onClick={async (e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              await handleConfirmPredictedIncident({incidentId: context.row.original.id!, mutate, session});
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            tooltip={"Discard"}
            icon={MdBlock}
            onClick={async (e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              await deleteIncident({incidentId: context.row.original.id!, mutate, session});
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



  return <IncidentTableComponent table={table} />;
}
