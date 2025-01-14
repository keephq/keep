import React, { useMemo } from "react";
import { Globe, Database, Cpu } from "lucide-react";
import { TraceData } from "./Trace";
import { Card } from "@tremor/react";
import {
  TooltipProvider,
  TooltipTrigger,
  TooltipContent,
  Tooltip,
  Portal,
} from "@radix-ui/react-tooltip";

interface ProcessedSpan {
  id: string;
  displayName: string;
  resource: string;
  service: string;
  type: string;
  startOffset: number;
  duration: number;
  level: number;
  durationMs: number;
  children: string[];
  httpStatus?: string;
  isErrorStatus: boolean | string;
  meta?: { [key: string]: string };
}

const SpanTooltipContent = ({ span }: { span: ProcessedSpan }) => {
  return (
    <div className="p-2 max-w-md">
      <div className="font-medium">{span.displayName}</div>
      <div className="text-sm text-gray-500">
        Duration: {span.duration.toFixed(2)}%
      </div>
      <div className="text-sm text-gray-500">Service: {span.service}</div>
      {span.meta?.["db.statement"] && (
        <div className="mt-2">
          <div className="text-sm font-medium text-gray-700">SQL Query:</div>
          <div className="text-xs bg-gray-100 p-2 rounded mt-1 font-mono whitespace-pre-wrap">
            {span.meta["db.statement"]}
          </div>
        </div>
      )}
    </div>
  );
};

const SimpleTraceViewer = ({ trace }: { trace: TraceData }) => {
  const processedData = useMemo(() => {
    const calculateLevel = (
      spanId: string,
      memo: Map<string, number> = new Map()
    ): number => {
      if (memo.has(spanId)) return memo.get(spanId) as number;

      const span = trace.spans[spanId];
      if (!span || !span.parent_id) {
        memo.set(spanId, 0);
        return 0;
      }

      const parentLevel = calculateLevel(span.parent_id, memo);
      const level = parentLevel + 1;
      memo.set(spanId, level);
      return level;
    };

    const rootSpan = trace.spans[trace.root_id];
    if (!rootSpan) {
      console.error("Root span not found:", trace.root_id);
      return [];
    }

    const timelineStart = rootSpan.start;
    const timelineDuration = rootSpan.end - rootSpan.start;

    return Object.entries(trace.spans)
      .map(([spanId, span]) => {
        const startOffset =
          ((span.start - timelineStart) / timelineDuration) * 100;
        const duration = (span.duration / timelineDuration) * 100;
        const level = calculateLevel(spanId);
        const displayName = span.inferred_entity?.entity || span.service;

        const isErrorStatus = span.status === "error";

        const processedSpan: ProcessedSpan = {
          id: spanId,
          displayName,
          resource: span.resource,
          service: span.service,
          type: span.type,
          startOffset,
          duration,
          level,
          durationMs: span.duration * 1000,
          children: span.children_ids,
          isErrorStatus,
          meta: span.meta,
        };

        return processedSpan;
      })
      .sort((a, b) => {
        if (a.level !== b.level) return a.level - b.level;
        return a.startOffset - b.startOffset;
      });
  }, []);

  interface TypeIconProps {
    type: string;
    className: string;
  }

  const TypeIcon: React.FC<TypeIconProps> = ({ type, className }) => {
    const iconProps = {
      size: 16,
      className: `${className} mr-2`,
    };

    switch (type) {
      case "web":
        return <Globe {...iconProps} />;
      case "db":
        return <Database {...iconProps} />;
      default:
        return <Cpu {...iconProps} />;
    }
  };

  return (
    <Card className="w-full max-w-6xl">
      <div className="space-y-1">
        <div className="flex text-sm font-medium text-gray-500 mb-2">
          <div className="w-64">Name</div>
          <div className="flex-1">Timeline</div>
          <div className="w-24 text-right">Duration</div>
          <div className="w-20 text-right">Status</div>
        </div>
        {processedData.map((span) => (
          <TooltipProvider key={span.id}>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <div key={span.id} className="rounded">
                  <div className="flex items-center space-x-2">
                    <div
                      className="w-64 truncate text-sm flex items-center"
                      style={{ paddingLeft: `${span.level * 16}px` }}
                    >
                      <TypeIcon
                        type={span.type}
                        className={
                          span.type === "web"
                            ? "text-purple-500"
                            : span.type === "db"
                            ? "text-green-500"
                            : "text-blue-500"
                        }
                      />
                      <span className="font-bold">{span.displayName}</span>
                      <span className="mx-1">:</span>
                      <span>{span.resource}</span>
                    </div>
                    <div className="flex-1 h-8 relative">
                      <div
                        className={`
                      absolute h-full rounded
                      ${
                        span.isErrorStatus
                          ? "bg-red-100"
                          : span.type === "web"
                          ? "bg-purple-100"
                          : span.type === "db"
                          ? "bg-green-100"
                          : "bg-blue-100"
                      }
                    `}
                        style={{
                          left: `${span.startOffset}%`,
                          width: `${Math.max(span.duration, 0.1)}%`,
                        }}
                      />
                    </div>
                    <div className="w-24 text-right text-sm text-gray-600">
                      {span.durationMs.toFixed(2)}ms
                    </div>
                    {span.httpStatus && (
                      <div
                        className={`w-20 text-right text-sm ${
                          span.isErrorStatus
                            ? "text-red-600 font-medium"
                            : "text-gray-600"
                        }`}
                      >
                        {span.httpStatus}
                      </div>
                    )}
                  </div>
                </div>
              </TooltipTrigger>
              <Portal>
                <TooltipContent
                  side="right"
                  className="bg-white shadow-lg border z-50"
                  sideOffset={5}
                  collisionPadding={10}
                  sticky="partial"
                >
                  <SpanTooltipContent span={span} />
                </TooltipContent>
              </Portal>
            </Tooltip>
          </TooltipProvider>
        ))}
      </div>
    </Card>
  );
};

export { SimpleTraceViewer };
