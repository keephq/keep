import React from "react";
import { MockStep, MockWorkflow } from "@/shared/api/workflows";
import { TiArrowRight } from "react-icons/ti";
import "react-loading-skeleton/dist/skeleton.css";
import { DynamicImageProviderIcon } from "@/components/ui";

export function WorkflowSteps({ workflow }: { workflow: MockWorkflow }) {
  const isStepPresent =
    !!workflow?.steps?.length &&
    workflow?.steps?.find((step: MockStep) => step?.provider?.type);

  return (
    <div className="container flex gap-1 items-center flex-wrap">
      {workflow?.steps?.map((step: any, index: number) => {
        const provider = step?.provider;
        if (["threshold", "assert", "foreach"].includes(provider?.type)) {
          return null;
        }
        return provider ? (
          <div
            key={`step-${step.id}-${index}`}
            className="flex items-center gap-1 flex-shrink-0"
          >
            {index > 0 && <TiArrowRight size={24} className="text-gray-500" />}
            <DynamicImageProviderIcon
              src={`/icons/${provider?.type}-icon.png`}
              width={24}
              height={24}
              alt={provider?.type}
              className="flex-shrink-0"
            />
          </div>
        ) : null;
      })}
      {workflow?.actions?.map((action: any, index: number) => {
        const provider = action?.provider;
        if (["threshold", "assert", "foreach"].includes(provider?.type)) {
          return null;
        }
        return provider ? (
          <div
            key={`action-${action.id}-${index}`}
            className="flex items-center gap-1 flex-shrink-0"
          >
            {(index > 0 || isStepPresent) && (
              <TiArrowRight size={24} className="text-gray-500" />
            )}
            <DynamicImageProviderIcon
              src={`/icons/${provider?.type}-icon.png`}
              width={24}
              height={24}
              alt={provider?.type}
              className="flex-shrink-0"
            />
          </div>
        ) : null;
      })}
    </div>
  );
}
