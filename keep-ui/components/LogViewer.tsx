import { MappingLogEntry } from "@/shared/api/mapping-executions";
import { Card } from "@tremor/react";

interface Props {
  logs: MappingLogEntry[];
}

export function LogViewer({ logs }: Props) {
  return (
    <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
      {logs.map((log, index) => (
        <div key={index} className="whitespace-pre-wrap mb-2">
          <span className="text-gray-500">[{log.timestamp}]</span>{" "}
          <span className="text-green-400">{log.message}</span>
          {log.context && (
            <div className="text-blue-400 ml-8">
              {JSON.stringify(log.context, null, 2)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
