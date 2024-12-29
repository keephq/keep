import React, { useMemo } from "react";
import { Globe, Database, Cpu } from "lucide-react";
import { TraceData } from "./Trace";
import { Card } from "@tremor/react";

const traceData: TraceData = {
  root_id: "2678538113127591416",
  spans: {
    "11443492233119063143": {
      children_ids: [],
      duration: 0.000124,
      end: 1735397527.2738528,
      name: "opentelemetry.instrumentation.fastapi.internal",
      parent_id: "2678538113127591416",
      resource: "GET /workflows http send",
      service: "keep-api",
      start: 1735397527.273729,
      type: "custom",
    },
    "2678538113127591416": {
      children_ids: [
        "352387617887994732",
        "11443492233119063143",
        "7264237120137931860",
        "405133968154136709",
      ],
      duration: 0.467228,
      end: 1735397527.277233,
      name: "opentelemetry.instrumentation.fastapi.server",
      parent_id: "0",
      resource: "GET /workflows",
      service: "keep-api",
      start: 1735397526.810005,
      type: "web",
    },
    "352387617887994732": {
      children_ids: [],
      duration: 0.000129,
      end: 1735397527.263743,
      name: "opentelemetry.instrumentation.fastapi.internal",
      parent_id: "2678538113127591416",
      resource: "GET /workflows http send",
      service: "keep-api",
      start: 1735397527.263614,
      type: "custom",
    },
    "405133968154136709": {
      children_ids: [],
      duration: 0.040109,
      end: 1735397527.1345012,
      inferred_entity: {
        entity: "keepdb",
        entity_key: "peer.db.name",
      },
      name: "opentelemetry.instrumentation.sqlalchemy.client",
      parent_id: "2678538113127591416",
      resource: "WITH keepdb",
      service: "keep-api",
      start: 1735397527.094392,
      type: "db",
    },
    "7264237120137931860": {
      children_ids: [],
      duration: 0.000183,
      end: 1735397527.276816,
      name: "opentelemetry.instrumentation.fastapi.internal",
      parent_id: "2678538113127591416",
      resource: "GET /workflows http send",
      service: "keep-api",
      start: 1735397527.276633,
      type: "custom",
    },
  },
};

const TraceViewer = ({ traceId }: { traceId: string }) => {
  const processedData = useMemo(() => {
    const calculateLevel = (
      spanId: string,
      memo: Map<string, number> = new Map()
    ): number => {
      if (memo.has(spanId)) return memo.get(spanId) as number;

      const span = traceData.spans[spanId];
      if (span.parent_id === "0") {
        memo.set(spanId, 0);
        return 0;
      }

      const parentLevel = calculateLevel(span.parent_id, memo);
      const level = parentLevel + 1;
      memo.set(spanId, level);
      return level;
    };

    const rootSpan = traceData.spans[traceData.root_id];
    const timelineStart = rootSpan.start;
    const timelineDuration = rootSpan.end - rootSpan.start;

    return Object.entries(traceData.spans)
      .map(([spanId, span]) => {
        const startOffset =
          ((span.start - timelineStart) / timelineDuration) * 100;
        const duration = (span.duration / timelineDuration) * 100;
        const level = calculateLevel(spanId);

        // Get display name based on inferred_entity or service
        const displayName = span.inferred_entity?.entity || span.service;

        return {
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
        };
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
        </div>
        {processedData.map((span) => (
          <div key={span.id} className="group hover:bg-gray-50 rounded">
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
                        span.type === "web"
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
            </div>
            <div
              className="text-xs text-gray-500 ml-2 mb-1 hidden group-hover:block"
              style={{ marginLeft: `${span.level * 16 + 24}px` }}
            >
              Type: {span.type}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

export { TraceViewer };
