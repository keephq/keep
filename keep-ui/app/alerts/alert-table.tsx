import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
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
  workflows,
  providers,
  mutate,
  isAsyncLoading = false,
  onDelete,
  setAssignee,
  users = [],
  currentUser,
  openModal,
}: Props) {
  const columnHelper = createColumnHelper<AlertDto>();

  const columns = [
    columnHelper.accessor("severity", {
      cell: (info) => info.getValue(),
    }),
    columnHelper.accessor("name", {
      header: () => "Name",
      cell: (info) => <i>{info.getValue()}</i>,
    }),
    columnHelper.accessor("description", {
      header: () => "Description",
      cell: (info) => info.renderValue(),
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
    }),
    columnHelper.accessor("status", {
      header: "Status",
    }),
    columnHelper.accessor("lastReceived", {
      header: "When",
    }),
    columnHelper.accessor("source", {
      header: "Source",
    }),
    columnHelper.accessor("assignee", {
      header: "Assignee",
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
    }),
    // columnHelper.accessor("", {
    //   header: "Extra Payload",
    // }),
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
        <AlertsTableBody
          alerts={alerts}
          groupBy={groupBy}
          groupedByData={groupedByAlerts}
          openModal={openModal}
          workflows={workflows}
          providers={providers}
          mutate={mutate}
          showSkeleton={isAsyncLoading}
          onDelete={onDelete}
          setAssignee={setAssignee}
          users={users}
          currentUser={currentUser}
        />
      </Table>
    </>
  );
}
