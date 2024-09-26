import React, { useEffect, useState } from "react";
import { Handle, Position } from "@xyflow/react";
import { useAlerts } from "utils/hooks/useAlerts";
import { useAlertPolling } from "utils/hooks/usePusher";
import { useRouter } from "next/navigation";
import { TopologyService } from "./models";

const THRESHOLD = 5;

const CustomNode = ({ data }: { data: TopologyService }) => {
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
      className="bg-white p-4 border rounded-xl shadow-lg relative"
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
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 p-4 bg-white border rounded-xl shadow-lg z-50">
          {data.service && (
            <p>
              <strong>Service:</strong> {data.service}
            </p>
          )}
          {data.display_name && (
            <p>
              <strong>Display Name:</strong> {data.display_name}
            </p>
          )}
          {data.description && (
            <p>
              <strong>Description:</strong> {data.description}
            </p>
          )}
          {data.team && (
            <p>
              <strong>Team:</strong> {data.team}
            </p>
          )}
          {data.application && (
            <p>
              <strong>Application:</strong> {data.application}
            </p>
          )}
          {data.email && (
            <p>
              <strong>Email:</strong> {data.email}
            </p>
          )}
          {data.slack && (
            <p>
              <strong>Slack:</strong> {data.slack}
            </p>
          )}
          {data.ip_address && (
            <p>
              <strong>IP Address:</strong> {data.ip_address}
            </p>
          )}
          {data.mac_address && (
            <p>
              <strong>MAC Address:</strong> {data.mac_address}
            </p>
          )}
          {data.manufacturer && (
            <p>
              <strong>Manufacturer:</strong> {data.manufacturer}
            </p>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
};

export default CustomNode;
