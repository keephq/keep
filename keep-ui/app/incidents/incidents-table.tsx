import { Badge, Card, Subtitle, Title } from "@tremor/react";
import {
  ExpandedState,
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
  SortingState,
  getSortedRowModel,
  ColumnDef,
} from "@tanstack/react-table";
import {
  MdModeEdit,
  MdKeyboardDoubleArrowRight,
  MdPlayArrow,
} from "react-icons/md";
import { useSession } from "next-auth/react";
import { IncidentDto, PaginatedIncidentsDto } from "./models";
import React, {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react";
import Image from "next/image";
import IncidentPagination from "./incident-pagination";
import IncidentTableComponent from "./incident-table-component";
import { deleteIncident } from "./incident-candidate-actions";
import IncidentChangeStatusModal from "./incident-change-status-modal";
import { STATUS_COLORS, StatusIcon } from "@/app/incidents/statuses";
import Markdown from "react-markdown";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import ManualRunWorkflowModal from "@/app/workflows/manual-run-workflow-modal";
import AlertTableCheckbox from "@/app/alerts/alert-table-checkbox";
import { Button, Link } from "@/components/ui";
import { useApiUrl } from "@/utils/hooks/useConfig";
import IncidentMergeModal from "@/app/incidents/incident-merge-modal";
import { TrashIcon } from "@heroicons/react/24/outline";
import { capitalize } from "@/utils/helpers";

function SelectedRowActions({
  selectedRowIds,
  onMergeInitiated,
  onDelete,
}: {
  selectedRowIds: string[];
  onMergeInitiated: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex gap-2 items-center justify-end">
      {selectedRowIds.length ? (
        <span className="accent-dark-tremor-content text-sm px-2">
          {selectedRowIds.length} selected
        </span>
      ) : null}
      <Button
        color="orange"
        variant="primary"
        size="md"
        disabled={selectedRowIds.length < 2}
        onClick={onMergeInitiated}
      >
        Merge
      </Button>
      <Button
        color="red"
        variant="primary"
        size="md"
        disabled={!selectedRowIds.length}
        onClick={onDelete}
      >
        Remove
      </Button>
    </div>
  );
}

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  mutate: () => void;
  sorting: SortingState;
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
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [pagination, setTablePagination] = useState({
    pageIndex: Math.ceil(incidents.offset / incidents.limit),
    pageSize: incidents.limit,
  });
  const [changeStatusIncident, setChangeStatusIncident] =
    useState<IncidentDto | null>();
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleChangeStatus = (e: React.MouseEvent, incident: IncidentDto) => {
    e.preventDefault();
    e.stopPropagation();
    setChangeStatusIncident(incident);
  };

  const handleRunWorkflow = (e: React.MouseEvent, incident: IncidentDto) => {
    e.preventDefault();
    e.stopPropagation();
    setRunWorkflowModalIncident(incident);
  };

  useEffect(() => {
    if (incidents.limit != pagination.pageSize) {
      setPagination({
        limit: pagination.pageSize,
        offset: 0,
      });
    }
    const currentOffset = pagination.pageSize * pagination.pageIndex;
    if (incidents.offset != currentOffset) {
      setPagination({
        limit: pagination.pageSize,
        offset: currentOffset,
      });
    }
  }, [incidents.limit, incidents.offset, pagination, setPagination]);

  const columns = [
    columnHelper.display({
      id: "selected",
      size: 10,
      header: (context) => (
        <AlertTableCheckbox
          checked={context.table.getIsAllRowsSelected()}
          indeterminate={context.table.getIsSomeRowsSelected()}
          onChange={context.table.getToggleAllRowsSelectedHandler()}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      cell: (context) => (
        <AlertTableCheckbox
          checked={context.row.getIsSelected()}
          indeterminate={context.row.getIsSomeSelected()}
          onChange={context.row.getToggleSelectedHandler()}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    }),
    columnHelper.display({
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <button
          onClick={(e) => handleChangeStatus(e, row.original!)}
          className="cursor-pointer"
        >
          <Badge
            size="sm"
            color={STATUS_COLORS[row.original.status]}
            className="pointer-events-none"
          >
            <div className="flex items-center justify-center gap-1">
              <StatusIcon
                status={row.original.status}
                className="size-4 [&>svg]:size-4"
              />
              {capitalize(row.original.status)}
            </div>
          </Badge>
        </button>
      ),
    }),
    columnHelper.display({
      id: "name",
      header: "Name & Summary",
      cell: ({ row }) => (
        <div className="min-w-64">
          <Link href={`/incidents/${row.original.id}`} className="text-pretty">
            {row.original.user_generated_name || row.original.ai_generated_name}
          </Link>
          <div className="text-pretty overflow-hidden overflow-ellipsis line-clamp-3">
            <Markdown
              remarkPlugins={[remarkRehype]}
              rehypePlugins={[rehypeRaw]}
            >
              {row.original.user_summary || row.original.generated_summary}
            </Markdown>
          </div>
        </div>
      ),
    }),
    columnHelper.display({
      id: "rule_fingerprint",
      header: "Group by value",
      cell: ({ row }) => (
        <div className="text-wrap">{row.original.rule_fingerprint || "-"}</div>
      ),
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
      cell: ({ row }) =>
        row.original.alert_sources.map((alert_sources, index) => (
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
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {row.original.services
            .filter((service) => service !== "null")
            .map((service) => (
              <Badge key={service}>{service}</Badge>
            ))}
        </div>
      ),
    }),
    columnHelper.display({
      id: "assignee",
      header: "Assignee",
      cell: ({ row }) => row.original.assignee,
    }),
    columnHelper.accessor("creation_time", {
      id: "creation_time",
      header: "Created At",
      cell: ({ row }) =>
        new Date(row.original.creation_time + "Z").toLocaleString(),
    }),
    columnHelper.display({
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className={"space-x-1 flex flex-row items-center justify-center"}>
          {/*If user wants to edit the mapping. We use the callback to set the data in mapping.tsx which is then passed to the create-new-mapping.tsx form*/}
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            tooltip="Edit"
            icon={MdModeEdit}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              editCallback(row.original!);
            }}
          />
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdKeyboardDoubleArrowRight}
            tooltip="Change status"
            onClick={(e) => handleChangeStatus(e, row.original!)}
          />
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdPlayArrow}
            tooltip="Run Workflow"
            onClick={(e) => handleRunWorkflow(e, row.original!)}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            tooltip="Remove"
            icon={TrashIcon}
            onClick={async (e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              await deleteIncident({
                incidentId: row.original.id!,
                mutate,
                session,
                apiUrl: apiUrl!,
              });
            }}
          />
        </div>
      ),
    }),
  ] as ColumnDef<IncidentDto>[];

  const table = useReactTable({
    columns,
    data: incidents.items,
    state: {
      expanded,
      pagination,
      sorting,
      columnPinning: {
        left: ["selected"],
        right: ["actions"],
      },
    },
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: incidents.count,
    onPaginationChange: setTablePagination,
    onExpandedChange: setExpanded,
    onSortingChange: (value) => {
      if (typeof value === "function") {
        setSorting(value);
      }
    },
    getSortedRowModel: getSortedRowModel(),
    enableSorting: true,
    enableMultiSort: false,
    manualSorting: true,
    debugTable: true,
  });

  const selectedRowIds = Object.entries(
    table.getSelectedRowModel().rowsById
  ).reduce<string[]>((acc, [alertId]) => {
    return acc.concat(alertId);
  }, []);

  type MergeOptions = {
    incidents: IncidentDto[];
  };

  const [mergeOptions, setMergeOptions] = useState<MergeOptions | null>(null);
  const handleMergeInitiated = useCallback(() => {
    const selectedIncidents = selectedRowIds.map(
      (incidentId) =>
        incidents.items.find((incident) => incident.id === incidentId)!
    );

    setMergeOptions({
      incidents: selectedIncidents,
    });
  }, [incidents.items, selectedRowIds]);

  const handleDeleteMultiple = useCallback(() => {
    if (selectedRowIds.length === 0) {
      return;
    }

    if (
      !confirm(
        `Are you sure you want to delete ${selectedRowIds.length} incidents? This action cannot be undone.`
      )
    ) {
      return;
    }

    for (let i = 0; i < selectedRowIds.length; i++) {
      const incidentId = selectedRowIds[i];
      deleteIncident({
        incidentId,
        mutate,
        session,
        apiUrl: apiUrl!,
        skipConfirmation: true,
      });
    }
  }, [apiUrl, mutate, selectedRowIds, session]);

  return (
    <>
      <SelectedRowActions
        selectedRowIds={selectedRowIds}
        onMergeInitiated={handleMergeInitiated}
        onDelete={handleDeleteMultiple}
      />
      {incidents.items.length > 0 ? (
        <Card className="p-0 overflow-hidden">
          <IncidentTableComponent table={table} />
        </Card>
      ) : (
        <Card className="flex-grow">
          <div className="flex flex-col items-center justify-center gap-y-8 h-full">
            <div className="text-center space-y-3">
              <Title className="text-2xl">No Incidents Matching Filters</Title>
              <Subtitle className="text-gray-400">
                Try changing the filters
              </Subtitle>
            </div>
          </div>
        </Card>
      )}
      <div className="mt-4 mb-8">
        <IncidentPagination table={table} isRefreshAllowed={true} />
      </div>
      <IncidentChangeStatusModal
        incident={changeStatusIncident}
        mutate={mutate}
        handleClose={() => setChangeStatusIncident(null)}
      />
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
      {mergeOptions && (
        <IncidentMergeModal
          incidents={mergeOptions.incidents}
          mutate={mutate}
          handleClose={() => setMergeOptions(null)}
          onSuccess={() => table.resetRowSelection()}
        />
      )}
    </>
  );
}
