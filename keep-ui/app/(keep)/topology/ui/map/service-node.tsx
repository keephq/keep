import React, { useEffect, useState } from "react";
import { Handle, NodeProps, NodeToolbar, Position } from "@xyflow/react";
import { useRouter } from "next/navigation";
import { ServiceNodeType, TopologyService } from "../../model/models";
import { Badge } from "@tremor/react";
import { getColorForUUID } from "@/app/(keep)/topology/lib/badge-colors";
import { clsx } from "clsx";
import { DynamicImageProviderIcon } from "@/components/ui";

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
  const router = useRouter();
  const [showDetails, setShowDetails] = useState(false);
  const [isTooltipReady, setIsTooltipReady] = useState(false);
  const [tooltipDirection, setTooltipDirection] = useState<Position>(
    Position.Bottom
  );

  useEffect(() => {
    if (!showDetails) {
      setTooltipDirection(Position.Bottom);
      setIsTooltipReady(false);
      return;
    }

    const node = document.querySelector(".tooltip-ref");
    if (!node) return;

    const rect = node.getBoundingClientRect();
    const viewportHeight = window.innerHeight;

    if (rect.bottom + 10 > viewportHeight) {
      setTooltipDirection(Position.Top);
    } else {
      setTooltipDirection(Position.Bottom);
    }
    setIsTooltipReady(true);
  }, [showDetails]);

  const handleClick = () => {
    router.push(`/incidents?services=${encodeURIComponent(data.display_name)}`);
  };

  const incidentsCount = data.incidents ?? 0;
  const badgeColor =
    incidentsCount < THRESHOLD ? "bg-orange-500" : "bg-red-500";

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
            <DynamicImageProviderIcon
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
        {incidentsCount > 0 && (
          <span
            className={`absolute top-[-20px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-xs font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
            onClick={handleClick}
          >
            {incidentsCount}
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

      <NodeToolbar
        isVisible={showDetails}
        position={tooltipDirection}
        className={clsx("tooltip-ref", !isTooltipReady && "invisible")}
      >
        <ServiceDetailsTooltip data={data} />
      </NodeToolbar>

      <>
        <Handle
          type="source"
          className={clsx(data.is_manual === true && "!opacity-100")}
          position={Position.Right}
          id="right"
        />
        <Handle
          type="target"
          className={clsx(data.is_manual === true && "!opacity-100")}
          position={Position.Left}
          id="left"
        />
      </>
    </>
  );
}
