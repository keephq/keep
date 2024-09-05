import {
    createColumnHelper,
    DisplayColumnDef,
    Row,
} from "@tanstack/react-table";
import { PaginatedWorkflowExecutionDto, WorkflowExecution } from "../builder/types";
import { GenericTable } from "@/components/table/GenericTable";
import { DownloadIcon, PlayIcon, TrashIcon } from "@radix-ui/react-icons";
import Link from "next/link";
import { Dispatch, Fragment, SetStateAction } from "react";
import Image from "next/image";
import { CheckCircleIcon, EllipsisHorizontalIcon, EyeIcon, WrenchIcon, XCircleIcon } from "@heroicons/react/20/solid";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import { formatDistanceToNowStrict } from "date-fns";
import { Menu, Transition } from "@headlessui/react";
import { Button, Icon } from "@tremor/react";
import { PiDiamondsFourFill } from "react-icons/pi";
import { FaHandPointer } from "react-icons/fa";
import { HiBellAlert } from "react-icons/hi2";
import { useRouter } from "next/navigation";


interface Pagination {
    limit: number;
    offset: number;
}
interface Props {
    executions: PaginatedWorkflowExecutionDto;
    setPagination: Dispatch<SetStateAction<Pagination>>;
}


function ExecutionRowMenu({ row }: { row: Row<WorkflowExecution> }) {
    const stopPropagation = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
    };
    return (
        <Menu as="div" className="realtive inline-block text-left">
            <div>
                <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm" onClick={stopPropagation} >
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
    )
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


function getTriggerIcon(triggered_by: string) {
    switch (triggered_by) {
        case "Manual": return FaHandPointer;
        case "Scheduler": return PiDiamondsFourFill;
        case "Alert": return HiBellAlert;
        default: return PiDiamondsFourFill;
    }
}
export function ExecutionTable({
    executions,
    setPagination,
}: Props) {

    const columnHelper = createColumnHelper<WorkflowExecution>();
    const router = useRouter();

    const columns = [
        columnHelper.display({
            id: "status",
            header: "Status",
            cell: ({ row }) => {
                const status = row.original.status;
                return <div>{getIcon(status)}</div>
            }
        }),
        columnHelper.display({
            id: "id",
            header: "Execution ID",
            cell: ({ row }) => {
                const status = row.original.status;
                const isError = ['timeout', 'error', 'fail', 'failed'].includes(status);
                return <div className={`${isError ? 'text-red-500' : ''}`}>{row.original.id}</div>
            }
        }),
        columnHelper.display({
            id: "triggered_by",
            header: "Trigger",
            cell: ({ row }) => {
                const triggered_by = row.original.triggered_by;
                let valueToShow = 'Others';
                if (triggered_by) {
                    switch (true) {
                        case triggered_by.substring(0, 9) === "scheduler":
                            valueToShow = "Scheduler";
                            break;
                        case triggered_by.substring(0, 10) === "type:alert":
                            valueToShow = "Alert";
                            break;
                        case triggered_by.substring(0, 6) === "manual":
                            valueToShow = "Manual";
                            break;
                    }
                }

                return triggered_by ? (
                    <Button
                        className="px-3 py-0.5 bg-white text-black rounded-xl border-2 border-gray-400 inline-flex items-center gap-2 font-bold hover:bg-white border-gray-400"
                        variant="secondary"
                        tooltip={triggered_by ?? ''}
                        icon={getTriggerIcon(valueToShow)}
                    >
                        <div>{valueToShow}</div>
                    </Button>) : null
            }
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
                    const remainingSeconds = (seconds % 60);

                    if (hours > 0) {
                        return `${hours} hr ${minutes}m ${remainingSeconds}s`;
                    } else if (minutes > 0) {
                        return `${minutes}m ${remainingSeconds}s`;
                    } else {
                        return `${remainingSeconds.toFixed(2)}s`;
                    }
                };

                return (
                    <div>
                        {customFormatter(row.original.execution_time || null)}
                    </div>
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
                        return ""
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
                return <TimeAgo
                    date={row.original.started + "Z"}
                    formatter={customFormatter}
                />
            }
        }),
        columnHelper.display({
            id: "menu",
            header: "",
            cell: ({ row }) => (
                <ExecutionRowMenu row={row} />
            ),
        }),
    ] as DisplayColumnDef<WorkflowExecution>[];

    //To DO pagiantion limit and offest can also be added to url searchparams
    return <GenericTable<WorkflowExecution>
        data={executions.items}
        columns={columns}
        rowCount={executions.count ?? 0} // Assuming pagination is not needed, you can adjust this if you have pagination
        offset={executions.offset} // Customize as needed
        limit={executions.limit} // Customize as needed
        onPaginationChange={(newLimit: number, newOffset: number) => setPagination({ limit: newLimit, offset: newOffset })}
        onRowClick = {(row:WorkflowExecution) => {
            router.push(`/workflows/${row.workflow_id}/runs/${row.id}`);
        }}
    />

}