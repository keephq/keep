import { Badge } from "@tremor/react";
import { DynamicImageProviderIcon } from "./DynamicProviderIcon";
import * as HoverCard from "@radix-ui/react-hover-card";
import { FieldHeader } from "@/shared/ui";

interface RCAPoint {
  providerType: string;
  content: string;
}

export function RootCauseAnalysis({
  points,
  className,
}: {
  points: RCAPoint[];
  className?: string;
}) {
  if (!points || points.length === 0) return null;

  return (
    <div>
      <FieldHeader>Root Cause Analysis</FieldHeader>
      <HoverCard.Root openDelay={100} closeDelay={200}>
        <HoverCard.Trigger asChild>
          <div className={`relative inline-flex items-center ${className}`}>
            <div className="absolute top-1/2 -translate-y-1/2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
              </span>
            </div>

            <Badge size="sm" color="orange" className="ml-4">
              🕵🏻‍♂️ Investigation
            </Badge>
          </div>
        </HoverCard.Trigger>

        <HoverCard.Portal>
          <HoverCard.Content
            className="w-[360px] rounded-tremor-default border border-tremor-border bg-tremor-background p-4 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-[9999] overflow-y-scroll"
            sideOffset={5}
          >
            <div className="space-y-2">
              <h4 className="font-medium text-tremor-content-emphasis mb-3">
                Analysis Points
              </h4>
              <ul className="space-y-3">
                {points.map((point, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 text-tremor-content p-2 rounded-tremor-small bg-tremor-background-muted"
                  >
                    <div className="mt-1 shrink-0">
                      <DynamicImageProviderIcon
                        providerType={point.providerType ?? "keep"}
                        width="16"
                        height="16"
                      />
                    </div>

                    <span className="flex-1 text-sm">{point.content}</span>
                  </li>
                ))}
              </ul>
            </div>

            <HoverCard.Arrow className="fill-tremor-border" />
          </HoverCard.Content>
        </HoverCard.Portal>
      </HoverCard.Root>
    </div>
  );
}
