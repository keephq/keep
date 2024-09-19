import React, { useEffect, useState } from "react";
import { Handle, NodeProps, Position } from "@xyflow/react";
import { useAlerts } from "utils/hooks/useAlerts";
import { useAlertPolling } from "utils/hooks/usePusher";
import { useRouter } from "next/navigation";
import { ServiceNodeType } from "../types";
import { cn } from "utils/helpers";

const THRESHOLD = 5;

export function ServiceNode({ data, selected }: NodeProps<ServiceNodeType>) {
  const { useAllAlerts } = useAlerts();
  const { data: alerts, mutate } = useAllAlerts("feed");
  const { data: pollAlerts } = useAlertPolling();
  const router = useRouter();
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (pollAlerts) {
      mutate();
    }
  }, [pollAlerts, mutate]);

  const relevantAlerts = alerts?.filter(
    (alert) => alert.service === data.service
  );

  const handleClick = () => {
    router.push(
      `/alerts/feed?cel=service%3D%3D${encodeURIComponent(`"${data.service}"`)}`
    );
  };

  const alertCount = relevantAlerts?.length || 0;
  const badgeColor = alertCount < THRESHOLD ? "bg-orange-500" : "bg-red-500";

  return (
    <div
      className={cn(
        "bg-white p-4 border-2 border-gray-200 rounded-xl shadow-lg relative",
        selected && "border-tremor-brand"
      )}
      onMouseEnter={() => setShowDetails(true)}
      onMouseLeave={() => setShowDetails(false)}
    >
      <strong className="text-lg">{data.display_name ?? data.service}</strong>
      {alertCount > 0 && (
        <span
          className={`absolute top-[-20px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-xs font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
          onClick={handleClick}
        >
          {alertCount}
        </span>
      )}
      {showDetails && (
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 p-4 bg-white border rounded-xl shadow-lg z-50 flex flex-col gap-2">
          {data.service && (
            <div>
              <p className="text-gray-500">Service</p>
              <span>{data.service}</span>
            </div>
          )}
          {data.display_name && (
            <div>
              <p className="text-gray-500">Display Name</p>
              <span>{data.display_name}</span>
            </div>
          )}
          {data.description && (
            <div>
              <p className="text-gray-500">Description</p>
              <span>{data.description}</span>
            </div>
          )}
          {data.team && (
            <div>
              <p className="text-gray-500">Team</p>
              <span>{data.team}</span>
            </div>
          )}
          {data.application && (
            <div>
              <p className="text-gray-500">Application</p>
              <span>{data.application}</span>
            </div>
          )}
          {data.email && (
            <div>
              <p className="text-gray-500">Email</p>
              <span>{data.email}</span>
            </div>
          )}
          {data.slack && (
            <div>
              <p className="text-gray-500">Slack</p>
              <span>{data.slack}</span>
            </div>
          )}
          {data.ip_address && (
            <div>
              <p className="text-gray-500">IP Address</p>
              <span>{data.ip_address}</span>
            </div>
          )}
          {data.mac_address && (
            <div>
              <p className="text-gray-500">MAC Address</p>
              <span>{data.mac_address}</span>
            </div>
          )}
          {data.manufacturer && (
            <div>
              <p className="text-gray-500">Manufacturer</p>
              <span>{data.manufacturer}</span>
            </div>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
}
