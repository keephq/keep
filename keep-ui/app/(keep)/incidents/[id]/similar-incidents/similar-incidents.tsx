"use client";

import { Badge, Card } from "@tremor/react";
import {
    ExpandedState,
    createColumnHelper,
    getCoreRowModel,
    useReactTable,
    SortingState,
    getSortedRowModel,
    ColumnDef,
    Table,
} from "@tanstack/react-table";
import type {
    IncidentDto,
    PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import React from "react";
import IncidentTableComponent from "@/features/incidents/incident-list/ui/incident-table-component";
import Markdown from "react-markdown";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import { Link } from "@/components/ui";

import { getIncidentName } from "@/entities/incidents/lib/utils";
import {
    DateTimeField,
    EmptyStateCard,
    TableSeverityCell,
    UISeverity,
} from "@/shared/ui";

import { BellAlertIcon, } from "@heroicons/react/24/outline";
import { useSimilarIncidents } from "@/utils/hooks/useIncidents";


const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
    id: string;
}

export default function SimilarIncidentsTable({
    id
}: Props) {
    // Fetch similar incidents based on the incident ID
    const {
        data: incidentItems,
        isLoading,
        error,
    } = useSimilarIncidents(id);

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
            id: "services",
            header: "Services",
            cell: ({ row }) => {
                const maxServices = 2;
                const notNullServices = row.original.services.filter(
                    (service) => service !== "null"
                );
                return (
                    <div className="flex flex-wrap items-baseline gap-1">
                        {notNullServices
                            .map((service) => <Badge key={service}>{service}</Badge>)
                            .slice(0, maxServices)}
                        {notNullServices.length > maxServices ? (
                            <span>
                                and{" "}
                                <Link href={`/incidents/${row.original.id}/alerts`}>
                                    {notNullServices.length - maxServices} more
                                </Link>
                            </span>
                        ) : null}
                    </div>
                );
            },
        }),
        columnHelper.accessor("creation_time", {
            id: "creation_time",
            header: "Created At",
            cell: ({ row }) => <DateTimeField date={row.original.creation_time} />,
        }),

    ] as ColumnDef<IncidentDto>[];


    const table = useReactTable({
        columns,
        data: incidentItems?.items || [],
        state: {
            columnPinning: {
                left: ["severity", "selected"],
                right: ["actions"],
            },
        },
        getRowId: (row) => row.id,
        getCoreRowModel: getCoreRowModel(),
    });


    if (isLoading || error || !incidentItems?.items || incidentItems.items.length === 0) {
        return (
            <EmptyStateCard
                className="w-full"
                title="No Similar Incidents Found  yet"
                description="There are no similar incidents found for this incident. Similar incidents will be displayed here once they are detected."
                icon={BellAlertIcon}
            >
            </EmptyStateCard>
        );
    }



    return (
        <Card className="p-0 overflow-hidden">
            <IncidentTableComponent table={table} />
        </Card>
    );
}
