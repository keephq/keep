import React, { useState } from "react";
import { MockStep, MockWorkflow } from "@/shared/api/workflows";
import Loading from "@/app/(keep)/loading";
import { Button, Card, Tab, TabGroup, TabList } from "@tremor/react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { TiArrowRight } from "react-icons/ti";

export function WorkflowSteps({ workflow }: { workflow: MockWorkflow }) {
  const isStepPresent =
    !!workflow?.steps?.length &&
    workflow?.steps?.find((step: MockStep) => step?.provider?.type);

  return (
    <div className="container flex gap-2 items-center overflow-x-auto max-w-full whitespace-nowrap">
      {workflow?.steps?.map((step: any, index: number) => {
        const provider = step?.provider;
        if (["threshold", "assert", "foreach"].includes(provider?.type)) {
          return null;
        }
        return (
          <>
            {provider && (
              <div
                key={`step-${step.id}`}
                className="flex items-center gap-2 flex-shrink-0"
              >
                {index > 0 && (
                  <TiArrowRight size={24} className="text-gray-500" />
                )}
                <Image
                  src={`/icons/${provider?.type}-icon.png`}
                  width={30}
                  height={30}
                  alt={provider?.type}
                  className="flex-shrink-0"
                />
              </div>
            )}
          </>
        );
      })}
      {workflow?.actions?.map((action: any, index: number) => {
        const provider = action?.provider;
        if (["threshold", "assert", "foreach"].includes(provider?.type)) {
          return null;
        }
        return (
          <>
            {provider && (
              <div
                key={`action-${action.id}`}
                className="flex items-center gap-2 flex-shrink-0"
              >
                {(index > 0 || isStepPresent) && (
                  <TiArrowRight size={24} className="text-gray-500" />
                )}
                <Image
                  src={`/icons/${provider?.type}-icon.png`}
                  width={30}
                  height={30}
                  alt={provider?.type}
                  className="flex-shrink-0"
                />
              </div>
            )}
          </>
        );
      })}
    </div>
  );
}

export const MockFilterTabs = ({
  tabs,
}: {
  tabs: { name: string; onClick?: () => void }[];
}) => (
  <div className="max-w-lg space-y-12">
    <TabGroup>
      <TabList variant="solid">
        {tabs?.map(
          (tab: { name: string; onClick?: () => void }, index: number) => (
            <Tab key={index} value={tab.name}>
              {tab.name}
            </Tab>
          )
        )}
      </TabList>
    </TabGroup>
  </div>
);

export default function MockWorkflowCardSection({
  mockWorkflows,
  mockError,
  mockLoading,
}: {
  mockWorkflows: MockWorkflow[];
  mockError: any;
  mockLoading: boolean | null;
}) {
  const router = useRouter();
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const getNameFromId = (id: string) => {
    if (!id) {
      return "";
    }

    return id.split("-").join(" ");
  };

  // if mockError is not null, handle the error case
  if (mockError) {
    return <p>Error: {mockError.message}</p>;
  }

  return (
    <div className="w-full">
      <h2 className="text-xl sm:text-2xl font-semibold mb-6">
        Discover workflow templates
      </h2>
      {/* TODO: Implement the commented out code block */}
      {/* This is a placeholder comment until the commented out code block is implemented */}
      {/* <div className="flex flex-col sm:flex-row justify-between mb-6 flex-wrap gap-2">
        <div className="flex flex-col sm:flex-row flex-wrap gap-2" >
          <input
            type="text"
            placeholder="Search through workflow examples..."
            className="px-4 py-2 border rounded"
          />
          <button className="px-4 py-2 bg-gray-200 border rounded">Integrations used</button>
        </div>
        <MockFilterTabs tabs={[
          {name: "All workflows"},
          {name: "Notifications"},
          {name: "Databases"},
          {name: "CI/CD"},
          {name: "Other"},
          ]}/>
      </div> */}
      {mockError && (
        <p className="text-center text-red-100 m-auto">
          Error: {mockError.message || "Something went wrong!"}
        </p>
      )}
      {!mockLoading && !mockError && mockWorkflows.length === 0 && (
        <p className="text-center m-auto">No workflows found</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 w-full gap-4">
        {mockError && (
          <p className="text-center text-red-100">
            Error: {mockError.message || "Something went wrong!"}
          </p>
        )}
        {mockLoading && <Loading />}
        {!mockLoading &&
          mockWorkflows.length > 0 &&
          mockWorkflows.map((template: any, index: number) => {
            const workflow = template.workflow;
            return (
              <Card
                key={index}
                className="p-4 flex flex-col justify-between w-full border-2 border-transparent hover:border-orange-400 "
              >
                <div>
                  <WorkflowSteps workflow={workflow} />
                  <h3 className="text-lg sm:text-xl font-semibold line-clamp-2">
                    {workflow.name || getNameFromId(workflow.id)}
                  </h3>
                  <p className="mt-2 text-sm sm:text-base line-clamp-3">
                    {workflow.description}
                  </p>
                </div>
                <div>
                  <Button
                    className="flex justify-center mt-8 px-4 py-2 border-none bg-gray-200 hover:bg-gray-300 bold-medium transition text-black rounded"
                    onClick={(e) => {
                      e.preventDefault();
                      setLoadingId(workflow.id);
                      localStorage.setItem(
                        "preview_workflow",
                        JSON.stringify(template)
                      );
                      router.push(`/workflows/preview/${workflow.id}`);
                    }}
                    disabled={!!(loadingId && loadingId !== workflow.id)}
                    loading={loadingId === workflow.id}
                  >
                    Preview
                  </Button>
                </div>
              </Card>
            );
          })}
      </div>
    </div>
  );
}
