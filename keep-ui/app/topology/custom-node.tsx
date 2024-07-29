import React, { useEffect } from "react";
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

  useEffect(() => {
    if (pollAlerts) {
      mutate();
    }
  }, [pollAlerts, mutate]);

  const relevantAlerts = alerts?.filter((alert) => alert.service === data.service);

  const handleClick = () => {
    router.push(
      `/alerts/feed?cel=service%3D%3D${encodeURIComponent(`"${data.service}"`)}`
    );
  };

  const alertCount = relevantAlerts?.length || 0;
  const badgeColor = alertCount < THRESHOLD ? "bg-orange-500" : "bg-red-500";

  return (
    <div className="bg-white p-4 border rounded-xl shadow-lg relative">
      <strong className="text-lg">{data.service}</strong>
      {alertCount > 0 && (
        <span
          className={`absolute top-[-20px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-xs font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
          onClick={handleClick}
        >
          {alertCount}
        </span>
      )}
      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </div>
  );
};

export default CustomNode;
