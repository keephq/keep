import {
  createColumnHelper,
  DisplayColumnDef,
  Row,
} from "@tanstack/react-table";
import {
  PaginatedWorkflowExecutionDto,
  WorkflowExecutionDetail,
} from "@/shared/api/workflow-executions";
import { GenericTable } from "@/components/table/GenericTable";
import Link from "next/link";
import { Dispatch, Fragment, SetStateAction } from "react";
import Image from "next/image";
import {
  CheckCircleIcon,
  EllipsisHorizontalIcon,
  XCircleIcon,
  NoSymbolIcon,
} from "@heroicons/react/20/solid";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import { formatDistanceToNowStrict } from "date-fns";
import { Menu, Transition } from "@headlessui/react";
import { Badge, Icon } from "@tremor/react";
import { HiBellAlert } from "react-icons/hi2";
import { useRouter } from "next/navigation";
import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";

interface Pagination {
  limit: number;
  offset: number;
}
interface Props {
  executions: PaginatedWorkflowExecutionDto;
  setPagination: Dispatch<SetStateAction<Pagination>>;
}

function ExecutionRowMenu({ row }: { row: Row<WorkflowExecutionDetail> }) {
  const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
  };
  return (
    <Menu as="div" className="realtive inline-block text-left">
      <div>
        <Menu.Button
          className="inline-flex w-full justify-center rounded-md text-sm"
          onClick={stopPropagation}
        >
          <Icon
            size="sm"
            icon={EllipsisHorizontalIcon}
            className="hover:bg-gray-100 w-8 h-8"
            color="gray"
          />
        </Menu.Button>
      </div>
      <Transition
        as={Fragment}
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute z-20 right-0 mt-2 w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
          {/* <Menu.Items className="absolute right-0 z-20 mb-2 w-36 divide-y  origin-middle-left divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"> */}
          <div className="px-1 py-1">
            <Menu.Item>
              {({ active }) => (
                <Link
                  className="flex items-center p-2"
                  href={`/workflows/${row.original.workflow_id}/runs/${row.original.id}`}
                  passHref
                >
                  View Logs
                </Link>
              )}
            </Menu.Item>
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
  );
}

export function getIcon(status: string) {
  let icon = (
    <Image
      className="animate-bounce size-6 cover"
      src="/keep.svg"
      alt="loading"
      width={40}
      height={40}
    />
  );
  switch (status) {
    case "success":
      icon = <CheckCircleIcon className="size-6 cover text-green-500" />;
      break;
    case "skipped":
      icon = (
        <NoSymbolIcon className="size-6 cover text-slate-500" title="Skipped" />
      );
      break;
    case "failed":
    case "fail":
    case "failure":
    case "error":
    case "timeout":
      icon = <XCircleIcon className="size-6 cover text-red-500" />;
      break;
    case "in_progress":
      icon = <div className="loader"></div>;
      break;
    default:
      icon = <div className="loader"></div>;
  }
  return icon;
}

export function getTriggerIcon(triggered_by: string) {
  switch (triggered_by) {
    case "manual":
      return CursorArrowRaysIcon;
    case "interval":
      return ClockIcon;
    case "alert":
      return HiBellAlert;
    case "incident":
      return HiBellAlert;
    default:
      return QuestionMarkCircleIcon;
  }
}

export function extractTriggerValue(triggered_by: string | undefined): string {
  if (!triggered_by) return "others";

  if (triggered_by.startsWith("scheduler")) {
    return "interval";
  } else if (triggered_by.startsWith("type:alert")) {
    return "alert";
  } else if (triggered_by.startsWith("manual")) {
    return "manual";
  } else if (triggered_by.startsWith("type:incident:")) {
    const incidentType = triggered_by
      .substring("type:incident:".length)
      .split(" ")[0];
    return `incident ${incidentType}`;
  } else {
    return "others";
  }
}

export function extractTriggerDetails(
  triggered_by: string | undefined
): string[] {
  if (!triggered_by) return [];

  let details: string;
  if (triggered_by.startsWith("scheduler")) {
    details = triggered_by.substring("scheduler".length).trim();
  } else if (triggered_by.startsWith("type:alert")) {
    details = triggered_by.substring("type:alert".length).trim();
  } else if (triggered_by.startsWith("manual")) {
    details = triggered_by.substring("manual".length).trim();
  } else if (triggered_by.startsWith("type:incident:")) {
    // Handle 'type:incident:{some operator}' by removing the operator
    details = triggered_by.substring("type:incident:".length).trim();
    const firstSpaceIndex = details.indexOf(" ");
    if (firstSpaceIndex > -1) {
      details = details.substring(firstSpaceIndex).trim();
    } else {
      details = "";
    }
  } else {
    details = triggered_by;
  }

  // Split the string into key-value pairs, where values may contain spaces
  const regex = /\b(\w+:[^:]+?)(?=\s\w+:|$)/g;
  const matches = details.match(regex);

  return matches ? matches : [];
}

export function ExecutionTable({ executions, setPagination }: Props) {
  const columnHelper = createColumnHelper<WorkflowExecutionDetail>();
  const router = useRouter();

  const columns = [
    columnHelper.display({
      id: "status",
      header: "Status",
      cell: ({ row }) => {
        const status = row.original.status;
        return <div>{getIcon(status)}</div>;
      },
    }),
    columnHelper.display({
      id: "id",
      header: "Execution ID",
      cell: ({ row }) => {
        const status = row.original.status;
        const isError = ["timeout", "error", "fail", "failed"].includes(status);
        return (
          <div className={`${isError ? "text-red-500" : ""}`}>
            {row.original.id}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "triggered_by",
      header: "Trigger",
      cell: ({ row }) => {
        const triggered_by = row.original.triggered_by;
        const valueToShow = extractTriggerValue(triggered_by);

        return triggered_by ? (
          <Badge
            color="gray"
            className="capitalize"
            tooltip={triggered_by ?? ""}
            icon={getTriggerIcon(valueToShow)}
          >
            {valueToShow}
          </Badge>
        ) : null;
      },
    }),
    columnHelper.display({
      id: "execution_time",
      header: "Execution Duration",
      cell: ({ row }) => {
        const customFormatter = (seconds: number | null) => {
          if (seconds === undefined || seconds === null) {
            return "";
          }

          const hours = Math.floor(seconds / 3600);
          const minutes = Math.floor((seconds % 3600) / 60);
          const remainingSeconds = seconds % 60;

          if (hours > 0) {
            return `${hours} hr ${minutes}m ${remainingSeconds}s`;
          } else if (minutes > 0) {
            return `${minutes}m ${remainingSeconds}s`;
          } else {
            return `${remainingSeconds.toFixed(2)}s`;
          }
        };

        return (
          <div>{customFormatter(row.original.execution_time ?? null)}</div>
        );
      },
    }),

    columnHelper.display({
      id: "started",
      header: "Started at",
      cell: ({ row }) => {
        const customFormatter: Formatter = (
          value: number,
          unit: Unit,
          suffix: Suffix
        ) => {
          if (!row?.original?.started) {
            return "";
          }

          const formattedString = formatDistanceToNowStrict(
            new Date(row.original.started + "Z"),
            { addSuffix: true }
          );

          return formattedString
            .replace("about ", "")
            .replace("minute", "min")
            .replace("second", "sec")
            .replace("hour", "hr");
        };
        return (
          <TimeAgo
            date={row.original.started + "Z"}
            formatter={customFormatter}
          />
        );
      },
    }),
    columnHelper.display({
      id: "menu",
      header: "",
      cell: ({ row }) => <ExecutionRowMenu row={row} />,
    }),
  ] as DisplayColumnDef<WorkflowExecutionDetail>[];

  //To DO pagiantion limit and offest can also be added to url searchparams
  return (
    <GenericTable<WorkflowExecutionDetail>
      data={executions.items}
      columns={columns}
      rowCount={executions.count ?? 0} // Assuming pagination is not needed, you can adjust this if you have pagination
      offset={executions.offset} // Customize as needed
      limit={executions.limit} // Customize as needed
      onPaginationChange={(newLimit: number, newOffset: number) =>
        setPagination({ limit: newLimit, offset: newOffset })
      }
      onRowClick={(row: WorkflowExecutionDetail) => {
        router.push(`/workflows/${row.workflow_id}/runs/${row.id}`);
      }}
    />
  );
}
