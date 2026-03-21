import { Button, Badge } from "@tremor/react";
import {
  DisplayColumnDef,
  ExpandedState,
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdDone, MdBlock } from "react-icons/md";
import {
  IncidentDto,
  PaginatedIncidentsDto,
  useIncidentActions,
} from "@/entities/incidents/model";
import React, { useState } from "react";
import { IncidentTableComponent } from "@/features/incidents/incident-list";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useTranslations } from "next-intl";

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  editCallback: (rule: IncidentDto) => void;
}

// Deprecated
export default function PredictedIncidentsTable({
  incidents: incidents,
}: Props) {
  const t = useTranslations("incidents");
  const { deleteIncident, confirmPredictedIncident } = useIncidentActions();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const columns = [
    columnHelper.display({
      id: "ai_generated_name",
      header: t("labels.name"),
      cell: ({ row }) => (
        <div className="text-wrap">{row.original.ai_generated_name}</div>
      ),
    }),
    columnHelper.display({
      id: "user_summary",
      header: t("labels.summary"),
      cell: ({ row }) => (
        <div className="text-wrap">{row.original.generated_summary}</div>
      ),
    }),
    columnHelper.display({
      id: "alerts_count",
      header: t("labels.numberOfAlerts"),
      cell: (context) => context.row.original.alerts_count,
    }),
    columnHelper.display({
      id: "alert_sources",
      header: t("labels.alertSources"),
      cell: (context) =>
        context.row.original.alert_sources.map((alert_sources, index) => (
          <DynamicImageProviderIcon
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
      header: t("labels.involvedServices"),
      cell: ({ row }) => (
        <div className="text-wrap">
          {row.original.services.map((service) => (
            <Badge key={service} className="mr-1">
              {service}
            </Badge>
          ))}
        </div>
      ),
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
            tooltip={t("messages.confirmIncident")}
            variant="secondary"
            icon={MdDone}
            onClick={async (e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              confirmPredictedIncident(context.row.original.id!);
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            tooltip={t("actions.discard")}
            icon={MdBlock}
            onClick={async (e: React.MouseEvent) => {
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
    getRowId: (row) => row.id,
    columns,
    data: incidents.items,
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  return <IncidentTableComponent table={table} />;
}
