import React, { useEffect, useState } from "react";
import { Handle, NodeProps, NodeToolbar, Position } from "@xyflow/react";
import { useAlerts } from "@/utils/hooks/useAlerts";
import { useAlertPolling } from "@/utils/hooks/usePusher";
import { useRouter } from "next/navigation";
import { ServiceNodeType, TopologyService } from "../../model/models";
import { Badge } from "@tremor/react";
import { getColorForUUID } from "@/app/topology/lib/badge-colors";
import { clsx } from "clsx";
import Image from "next/image";

const THRESHOLD = 5;

function ServiceDetailsTooltip({ data }: { data: TopologyService }) {
  return (
    <div className="py-2 px-3 bg-tremor-background-muted border rounded shadow-lg flex flex-col gap-2 text-xs">
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
  );
}

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
    <>
      <div
        className={clsx(
          "flex flex-col gap-1 bg-white p-4 border-2 border-gray-200 rounded-xl shadow-lg relative transition-colors",
          selected && "border-tremor-brand"
        )}
        onMouseEnter={() => setShowDetails(true)}
        onMouseLeave={() => setShowDetails(false)}
      >
        {data.category && (
          <div className="absolute top-2 right-2 text-gray-400">
            <Image
              className="inline-block"
              alt={data.category}
              height={24}
              width={24}
              title={data.category}
              src={`/icons/${data.category.toLowerCase()}-icon.png`}
            />
          </div>
        )}
        <strong className="text-lg">{data.display_name || data.service}</strong>
        {alertCount > 0 && (
          <span
            className={`absolute top-[-20px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-xs font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
            onClick={handleClick}
          >
            {alertCount}
          </span>
        )}
        <div className="flex flex-wrap gap-1">
          {data?.applications?.map((app) => {
            const color = getColorForUUID(app.id);
            return (
              <Badge key={app.id} color={color}>
                {app.name}
              </Badge>
            );
          })}
        </div>
      </div>

      <NodeToolbar isVisible={showDetails} position={Position.Bottom}>
        <ServiceDetailsTooltip data={data} />
      </NodeToolbar>

      <Handle type="source" position={Position.Right} id="right" />
      <Handle type="target" position={Position.Left} id="left" />
    </>
  );
}
