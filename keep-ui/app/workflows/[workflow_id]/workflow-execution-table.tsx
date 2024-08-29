import {
    createColumnHelper,
    DisplayColumnDef,
} from "@tanstack/react-table";
import { PaginatedWorkflowExecutionDto, WorkflowExecution } from "../builder/types";
import { GenericTable } from "@/components/table/GenericTable";
import { PlayIcon } from "@radix-ui/react-icons";
import Link from "next/link";
import { Dispatch, SetStateAction } from "react";
import Image from "next/image";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/20/solid";

interface Pagination {
    limit: number;
    offset: number;
}
interface Props {
    executions: PaginatedWorkflowExecutionDto;
    setPagination: Dispatch<SetStateAction<Pagination>>;
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
export function ExecutionTable({
    executions,
    setPagination,
}: Props) {

    const columnHelper = createColumnHelper<WorkflowExecution>();

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

        columnHelper.accessor("triggered_by", {
            header: "Trigger",
        }),
        columnHelper.accessor("execution_time", {
            header: "Execution time",
        }),
        columnHelper.display({
            id: "started",
            header: "Started at",
            cell: ({ row }) =>
                new Date(row.original.started + "Z").toLocaleString(),
        }),
        // columnHelper.display({
        //   id: "error",
        //   header: "Error",
        //   cell: ({ row }) => (
        //     <div className="max-w-xl truncate" title={row.original.error || ""}>
        //       {row.original.error}
        //     </div>
        //   ),
        // }),

        columnHelper.display({
            id: "logs",
            header: "Logs",
            cell: ({ row }) => (
                <Link
                    className="text-orange-500 hover:underline flex items-center"
                    href={`/workflows/${row.original.workflow_id}/runs/${row.original.id}`}
                    passHref
                >
                    <PlayIcon className="h-4 w-4 ml-1" />
                </Link>
            ),
        }),
    ] as DisplayColumnDef<WorkflowExecution>[];


    return <GenericTable<WorkflowExecution>
        data={executions.items}
        columns={columns}
        rowCount={executions.count ?? 0} // Assuming pagination is not needed, you can adjust this if you have pagination
        offset={executions.offset} // Customize as needed
        limit={executions.limit} // Customize as needed
        onPaginationChange={(newLimit: number, newOffset: number) => setPagination({ limit: newLimit, offset: newOffset })}
    />

}