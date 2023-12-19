import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
  CategoryBar,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { AlertDto } from "./models";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Provider } from "app/providers/providers";
import { User } from "app/settings/models";
import { User as NextUser } from "next-auth";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import PushPullBadge from "@/components/ui/push-pulled-badge/push-pulled-badge";
import moment from "moment";
import Image from "next/image";
import AlertAssignee from "./alert-assignee";
import AlertMenu from "./alert-menu";
import AlertName from "./alert-name";
import { Workflow } from "app/workflows/models";
import { useRouter } from "next/navigation";
import AlertSeverity from "./alert-severity";
import AlertExtraPayload from "./alert-extra-payload";

const getAlertLastReceieved = (lastRecievedFromAlert: Date) => {
  let lastReceived = "unknown";
  if (lastRecievedFromAlert) {
    lastReceived = lastRecievedFromAlert.toString();
    try {
      lastReceived = moment(lastRecievedFromAlert).fromNow();
    } catch {}
  }
  return lastReceived;
};

const columnHelper = createColumnHelper<AlertDto>();

interface Props {
  alerts: AlertDto[];
  groupBy?: string;
  groupedByAlerts?: { [key: string]: AlertDto[] };
  workflows?: any[];
  providers?: Provider[];
  mutate?: () => void;
  isAsyncLoading?: boolean;
  onDelete?: (
    fingerprint: string,
    lastReceived: Date,
    restore?: boolean
  ) => void;
  setAssignee?: (fingerprint: string, unassign: boolean) => void;
  users?: User[];
  currentUser: NextUser;
  openModal?: (alert: AlertDto) => void;
}

export function AlertTable({
  alerts,
  groupedByAlerts = {},
  groupBy,
  workflows = [],
  providers = [],
  mutate,
  isAsyncLoading = false,
  onDelete,
  setAssignee,
  users = [],
  currentUser,
  openModal,
}: Props) {
  const router = useRouter();

  const handleWorkflowClick = (workflows: Workflow[]) => {
    if (workflows.length === 1) {
      router.push(`workflows/${workflows[0].id}`);
    } else {
      router.push("workflows");
    }
  };

  const columns = [
    columnHelper.display({
      id: "alertMenu",
      cell: (cell) => (
        <div className="pb-9">
          <AlertMenu
            alert={cell.row.original}
            canOpenHistory={!groupedByAlerts![(alert as any)[groupBy!]]}
            openHistory={() => openModal!(cell.row.original)}
            provider={providers.find(
              (p) => p.type === cell.row.original.source![0]
            )}
            mutate={mutate}
            callDelete={onDelete}
            setAssignee={setAssignee}
            currentUser={currentUser}
          />
        </div>
      ),
    }),
    columnHelper.accessor("severity", {
      header: () => "Severity",
      cell: (cell) => <AlertSeverity severity={cell.getValue()} />,
    }),
    columnHelper.accessor("name", {
      header: () => "Name",
      cell: (cell) => (
        <AlertName
          alert={cell.row.original}
          workflows={workflows}
          handleWorkflowClick={handleWorkflowClick}
        />
      ),
    }),
    columnHelper.accessor("description", {
      header: () => "Description",
      cell: (cell) => (
        <div
          className="max-w-[340px] flex items-center"
          title={cell.getValue()}
        >
          <div className="truncate">{cell.getValue()}</div>,
        </div>
      ),
    }),
    columnHelper.accessor("pushed", {
      header: () => (
        <div className="flex items-center gap-1">
          <span>Pushed</span>
          <Icon
            icon={QuestionMarkCircleIcon}
            tooltip="Whether the alert was pushed or pulled from the alert source"
            variant="simple"
            color="gray"
          />
        </div>
      ),
      cell: (cell) => <PushPullBadge pushed={cell.getValue()} />,
    }),
    columnHelper.accessor("status", {
      header: "Status",
    }),
    columnHelper.accessor("lastReceived", {
      header: "When",
      cell: (cell) => getAlertLastReceieved(cell.getValue()),
    }),
    columnHelper.accessor("source", {
      header: "Source",
      cell: (cell) =>
        (cell.getValue() ?? []).map((source, index) => (
          <Image
            className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
            key={source}
            alt={source}
            height={24}
            width={24}
            title={source}
            src={`/icons/${source}-icon.png`}
          />
        )),
    }),
    columnHelper.accessor("assignee", {
      header: "Assignee",
      cell: (cell) => (
        <AlertAssignee assignee={cell.getValue()} users={users} />
      ),
    }),
    columnHelper.accessor("fatigueMeter", {
      header: () => (
        <div className="flex items-center gap-1">
          <span>Fatigue Meter</span>
          <Icon
            icon={QuestionMarkCircleIcon}
            tooltip="Calculated based on various factors"
            variant="simple"
            color="gray"
          />
        </div>
      ),
      cell: (cell) => (
        <CategoryBar
          values={[40, 30, 20, 10]}
          colors={["emerald", "yellow", "orange", "rose"]}
          markerValue={cell.getValue() ?? 0}
          tooltip={(cell.getValue() ?? 0).toString() ?? "0"}
          className="min-w-[192px]"
        />
      ),
    }),
    columnHelper.display({
      id: "extraPayload",
      cell: (cell) => <AlertExtraPayload alert={cell.row.original} />,
    }),
  ];

  const table = useReactTable({
    data: alerts,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <>
      {isAsyncLoading && (
        <Callout
          title="Getting your alerts..."
          icon={CircleStackIcon}
          color="gray"
          className="mt-5"
        >
          Alerts will show up in this table as they are added to Keep...
        </Callout>
      )}
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHeaderCell key={header.id}>
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </TableHeaderCell>
              ))}
            </TableRow>
          ))}
        </TableHead>
        <AlertsTableBody table={table} showSkeleton={isAsyncLoading} />
      </Table>
    </>
  );
}
