"use client";
import {
    Callout,
    Card,
    Title,
    Tab,
    TabGroup,
    TabList,
    Button,
} from "@tremor/react";
import React, { Dispatch, SetStateAction, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import {
    ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import Loading from "../../loading";
import { useRouter, useSearchParams } from "next/navigation";
import { useWorkflowExecutionsV2 } from "utils/hooks/useWorkflowExecutions";

import WorkflowGraph from "../workflow-graph";
import { Workflow } from '../models';
import { WorkflowSteps } from "../mockworkflows";
import { JSON_SCHEMA, load } from "js-yaml";
import { ExecutionTable } from "./workflow-execution-table";
import SideNavBar from "./side-nav-bar";
import { useWorkflowRun } from "utils/hooks/useWorkflowRun";
import BuilderWorkflowTestRunModalContent from "../builder/builder-workflow-testrun-modal";
import Modal from "react-modal";
import { TableFilters } from "./table-filters";

const tabs = [
    { name: "All Time", value: 'alltime' },
    { name: "Last 30d", value: "last_30d" },
    { name: "Last 7d", value: "last_7d" },
    { name: "Today", value: "today" },
];

export const FilterTabs = ({
    tabs,
    setTab,
    tab
}: {
    tabs: { name: string; value: string }[];
    setTab: Dispatch<SetStateAction<number>>;
    tab: number;
}) => {

    return (
        <div className="max-w-lg space-y-12 pt-6">
            <TabGroup
                index={tab}
                onIndexChange={(index: number) => { setTab(index) }}
            >
                <TabList variant="solid" color="black" className="bg-gray-300">
                    {tabs.map((tabItem, index) => (
                        <Tab
                            key={tabItem.value}
                        >
                            {tabItem.name}
                        </Tab>
                    ))}
                </TabList>
            </TabGroup>
        </div>
    );
};

export function StatsCard({ children, data }: { children: any, data?: string }) {
    return <Card className="group relative container flex flex-col p-4 space-y-2 min-w-1/5">
            {!!data && <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block bg-gray-800 text-white rounded py-1 p-2 text-2xl font-bold">
                {data}
            </div>}
            {children}
    </Card>
}

interface Pagination {
    limit: number;
    offset: number;
}

export default function WorkflowDetailPage({
    params,
}: {
    params: { workflow_id: string };
}) {
    const router = useRouter();
    const { data: session, status, update } = useSession();

    const [executionPagination, setExecutionPagination] = useState<Pagination>({
        limit: 25,
        offset: 0,
    });
    const [tab, setTab] = useState<number>(1)
    const searchParams = useSearchParams();

    useEffect(() => {
        setExecutionPagination({
            ...executionPagination,
            offset: 0,
        })
    }, [tab, searchParams]);


    const {
        data,
        isLoading,
        error
    } = useWorkflowExecutionsV2(params.workflow_id, tab, executionPagination.limit, executionPagination.offset);

    const {
        loading,
        runModalOpen,
        setRunModalOpen,
        runningWorkflowExecution,
        setRunningWorkflowExecution } = useWorkflowRun(data?.workflow?.workflow_raw!)


    if (isLoading || !data) return <Loading />;

    if (error) {
        return (
            <Callout
                className="mt-4"
                title="Error"
                icon={ExclamationCircleIcon}
                color="rose"
            >
                Failed to load workflow
            </Callout>
        );
    }
    if (status === "loading" || isLoading || !data) return <Loading />;
    if (status === "unauthenticated") router.push("/signin");

    const parsedWorkflowFile = load(data?.workflow?.workflow_raw ?? '', {
        schema: JSON_SCHEMA,
    }) as any;


    const formatNumber = (num: number) => {
        if (num >= 1_000_000) {
            return `${(num / 1_000_000).toFixed(1)}m`;
        } else if (num >= 1_000) {
            return `${(num / 1_000).toFixed(1)}k`;
        } else {
            return num.toString();
        }
    };

    const workflow = { last_executions: data.items } as Partial<Workflow>
    return (
        <>
            <Card className="relative flex p-4 w-full gap-3">
                <SideNavBar workflow={data.workflow} />
                <div className="relative overflow-auto p-0.5 flex-1 flex-shrink-1">
                    <div className="sticky top-0 flex justify-between items-end">
                        <div className="flex-1">
                            {/*TO DO update searchParams for these filters*/}
                            <FilterTabs tabs={tabs} setTab={setTab} tab={tab} />
                        </div>
                        <Button className="p-2 px-4" onClick={(e) => { e.preventDefault(); setRunModalOpen(true) }}>Run now</Button>
                    </div>
                    {data?.items && (
                        <div className="mt-2 flex flex-col gap-2">
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 p-0.5">
                                <StatsCard data={`${data.count ?? 0}`}>
                                    <Title>
                                        Total Executions
                                    </Title>
                                    <div>
                                        <h1 className="text-2xl font-bold">{formatNumber(data.count ?? 0)}</h1>
                                        {/* <div className="text-sm text-gray-500">__ from last month</div> */}
                                    </div>
                                </StatsCard>
                                <StatsCard data= {`${data.passCount}/${data.failCount}`}>
                                    <Title>
                                        Pass / Fail ratio
                                    </Title>
                                    <div>
                                        <h1 className="text-2xl font-bold">{formatNumber(data.passCount)}{'/'}{formatNumber(data.failCount)}</h1>
                                        {/* <div className="text-sm text-gray-500">__ from last month</div> */}
                                    </div>

                                </StatsCard>
                                <StatsCard>
                                    <Title>
                                        Success %
                                    </Title>
                                    <div>
                                        <h1 className="text-2xl font-bold">{(data.count ? (data.passCount / data.count) * 100 : 0).toFixed(2)}{"%"}</h1>
                                        {/* <div className="text-sm text-gray-500">__ from last month</div> */}
                                    </div>

                                </StatsCard>
                                <StatsCard>
                                    <Title>
                                        Avg. duration
                                    </Title>
                                    <div>
                                        <h1 className="text-2xl font-bold">{(data.avgDuration ?? 0).toFixed(2)}</h1>
                                        {/* <div className="text-sm text-gray-500">__ from last month</div> */}
                                    </div>

                                </StatsCard>
                                <StatsCard>
                                    <Title>
                                        Invloved Services
                                    </Title>
                                    <WorkflowSteps workflow={parsedWorkflowFile} />
                                </StatsCard>
                            </div>
                            <WorkflowGraph showLastExecutionStatus={false} workflow={workflow} limit={executionPagination.limit} showAll={true} size="sm" />
                            <h1 className="text-xl font-bold mt-4">Execution History</h1>
                            <TableFilters workflowId={data.workflow.id} />
                            <ExecutionTable
                                executions={data}
                                setPagination={setExecutionPagination}
                            />
                        </div>
                    )}
                </div>
            </Card>
            <Modal
                isOpen={runModalOpen}
                onRequestClose={() => { setRunModalOpen(false); setRunningWorkflowExecution(null) }}
                className="bg-gray-50 p-4 md:p-10 mx-auto max-w-7xl mt-20 border border-orange-600/50 rounded-md"
            >
                <BuilderWorkflowTestRunModalContent
                    closeModal={() => { setRunModalOpen(false); setRunningWorkflowExecution(null) }}
                    workflowExecution={runningWorkflowExecution}
                />
            </Modal>
        </>
    );
}
