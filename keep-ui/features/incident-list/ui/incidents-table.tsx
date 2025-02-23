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
import type {
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import React, {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react";
import IncidentTableComponent from "./incident-table-component";
import Markdown from "react-markdown";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import { Button, Link } from "@/components/ui";
import { MergeIncidentsModal } from "@/features/merge-incidents";
import { IncidentDropdownMenu } from "./incident-dropdown-menu";
import clsx from "clsx";
import { IncidentChangeStatusSelect } from "@/features/change-incident-status/";
import { useIncidentActions } from "@/entities/incidents/model";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import {
  DateTimeField,
  TableIndeterminateCheckbox,
  TablePagination,
  TableSeverityCell,
  UISeverity,
} from "@/shared/ui";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { GenerateReportModal } from "./incidents-report";

function SelectedRowActions({
  selectedRowIds,
  onMergeInitiated,
  onDelete,
  onGenerateReport,
}: {
  selectedRowIds: string[];
  onMergeInitiated: () => void;
  onDelete: () => void;
  onGenerateReport: () => void;
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
        onClick={onGenerateReport}
      >
        Generate report
      </Button>
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
        Delete
      </Button>
    </div>
  );
}

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  incidents: PaginatedIncidentsDto;
  sorting: SortingState;
  setSorting: Dispatch<SetStateAction<any>>;
  setPagination: Dispatch<SetStateAction<any>>;
  editCallback: (rule: IncidentDto) => void;
}

export default function IncidentsTable({
  incidents: incidents,
  setPagination,
  sorting,
  setSorting,
  editCallback,
}: Props) {
  const { deleteIncident } = useIncidentActions();
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [pagination, setTablePagination] = useState({
    pageIndex: Math.ceil(incidents.offset / incidents.limit),
    pageSize: incidents.limit,
  });
  const [isGenerateReportModalOpen, setIsGenerateReportModalOpen] =
    useState(false);
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

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
      id: "severity",
      header: () => <></>,
      cell: ({ row }) => (
        <TableSeverityCell
          severity={row.original.severity as unknown as UISeverity}
        />
      ),
      size: 4,
      minSize: 4,
      maxSize: 4,
      meta: {
        tdClassName: "p-0",
        thClassName: "p-0",
      },
    }),
    columnHelper.display({
      id: "selected",
      minSize: 32,
      maxSize: 32,
      header: (context) => (
        <TableIndeterminateCheckbox
          checked={context.table.getIsAllRowsSelected()}
          indeterminate={context.table.getIsSomeRowsSelected()}
          onChange={context.table.getToggleAllRowsSelectedHandler()}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      cell: (context) => (
        <TableIndeterminateCheckbox
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
        <IncidentChangeStatusSelect
          incidentId={row.original.id}
          value={row.original.status}
        />
      ),
    }),
    columnHelper.display({
      id: "name",
      header: "Incident",
      cell: ({ row }) => (
        <div className="min-w-32 lg:min-w-64">
          <Link
            href={`/incidents/${row.original.id}/alerts`}
            className="text-pretty"
          >
            {getIncidentName(row.original)}
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
    columnHelper.accessor("alerts_count", {
      id: "alerts_count",
      header: "Alerts",
    }),
    columnHelper.display({
      id: "alert_sources",
      header: "Sources",
      cell: ({ row }) =>
        row.original.alert_sources.map((alert_source, index) => (
          <DynamicImageProviderIcon
            key={alert_source}
            className={clsx(
              "inline-block",
              index == 0
                ? ""
                : "-ml-2 bg-white border-white border-2 rounded-full"
            )}
            alt={alert_source}
            height={24}
            width={24}
            title={alert_source}
            src={`/icons/${alert_source}-icon.png`}
          />
        )),
    }),
    columnHelper.display({
      id: "services",
      header: "Involved Services",
      cell: ({ row }) => {
        const notNullServices = row.original.services.filter(
          (service) => service !== "null"
        );
        return (
          <div className="flex flex-wrap items-baseline gap-1">
            {notNullServices
              .map((service) => <Badge key={service}>{service}</Badge>)
              .slice(0, 3)}
            {notNullServices.length > 3 ? (
              <span>
                and{" "}
                <Link href={`/incidents/${row.original.id}/alerts`}>
                  {notNullServices.length - 3} more
                </Link>
              </span>
            ) : null}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "assignee",
      header: "Assignee",
      cell: ({ row }) => (
        <UserStatefulAvatar email={row.original.assignee} size="xs" />
      ),
    }),
    columnHelper.accessor("creation_time", {
      id: "creation_time",
      header: "Created At",
      cell: ({ row }) => <DateTimeField date={row.original.creation_time} />,
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex justify-end">
          <IncidentDropdownMenu
            incident={row.original}
            handleEdit={editCallback}
            handleRunWorkflow={() => setRunWorkflowModalIncident(row.original)}
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
        left: ["severity", "selected"],
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

    const isConfirmed = confirm(
      `Are you sure you want to delete ${selectedRowIds.length} incidents? This action cannot be undone.`
    );

    if (!isConfirmed) {
      return;
    }

    for (let i = 0; i < selectedRowIds.length; i++) {
      const incidentId = selectedRowIds[i];
      deleteIncident(incidentId, true);
    }
  }, [deleteIncident, selectedRowIds]);

  const generateReport = useCallback(
    () => setIsGenerateReportModalOpen(true),
    [setIsGenerateReportModalOpen]
  );

  return (
    <>
      <SelectedRowActions
        selectedRowIds={selectedRowIds}
        onMergeInitiated={handleMergeInitiated}
        onDelete={handleDeleteMultiple}
        onGenerateReport={generateReport}
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
        <TablePagination table={table} />
      </div>
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
      {mergeOptions && (
        <MergeIncidentsModal
          incidents={mergeOptions.incidents}
          handleClose={() => setMergeOptions(null)}
          onSuccess={() => table.resetRowSelection()}
        />
      )}
      {isGenerateReportModalOpen && (
        <GenerateReportModal
          incidentIds={selectedRowIds}
          onClose={() => setIsGenerateReportModalOpen(false)}
        />
      )}
    </>
  );
}
