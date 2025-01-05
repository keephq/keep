import { DynamicIcon } from "./DynamicIcon";
import * as HoverCard from "@radix-ui/react-hover-card";

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
    <HoverCard.Root openDelay={100} closeDelay={200}>
      <HoverCard.Trigger asChild>
        <div
          className={`rounded-tremor-default border border-tremor-border bg-tremor-background-subtle p-4 cursor-pointer hover:border-tremor-brand transition-colors relative ${className}`}
        >
          <div className="absolute -top-1.5 -right-1.5">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
          </div>

          <div className="flex items-center gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-tremor-content-emphasis"
            >
              <path d="M21 11V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6" />
              <path d="m12 12 4 10 1.7-4.3L22 16Z" />
            </svg>
            <h3 className="font-medium text-tremor-content-emphasis">
              Root Cause Analysis
            </h3>
          </div>
        </div>
      </HoverCard.Trigger>

      <HoverCard.Portal>
        <HoverCard.Content
          className="w-[360px] rounded-tremor-default border border-tremor-border bg-tremor-background p-4 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-[9999]"
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
                  {point.providerType && (
                    <div className="mt-1 shrink-0">
                      <DynamicIcon
                        providerType={point.providerType}
                        width="16px"
                        height="16px"
                      />
                    </div>
                  )}
                  <span className="flex-1 text-sm">{point.content}</span>
                </li>
              ))}
            </ul>
          </div>

          <HoverCard.Arrow className="fill-tremor-border" />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}
