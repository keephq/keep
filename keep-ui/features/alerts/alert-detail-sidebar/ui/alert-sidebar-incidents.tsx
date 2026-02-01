import { useState } from "react";
import Link from "next/link";
import { IncidentDto } from "@/entities/incidents/model";
interface CollapsibleIncidentsListProps {
    incidents: IncidentDto[];
}

const CollapsibleIncidentsList = ({ incidents }: CollapsibleIncidentsListProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const maxVisible = 5; // default max visible rows

    const visibleIncidents = isExpanded
        ? incidents
        : incidents.slice(0, maxVisible);

    const showExpandButton = incidents.length > maxVisible;
    const showCollapseButton = isExpanded && incidents.length > maxVisible;

    return (
        <div className="flex flex-col">
            {visibleIncidents.map((incident) => {
                const title = incident.user_generated_name || incident.ai_generated_name;
                return (
                    <Link
                        href={`/incidents/${incident.id}`}
                        className="text-blue-600 hover:underline truncate max-w-full inline-block"
                        title={title}
                    >
                        {title}
                    </Link>
                );
            })}

            <div className="flex">
                {showExpandButton && !isExpanded && (
                    <button
                        onClick={() => setIsExpanded(true)}
                        className="text-blue-600 hover:underline text-sm mt-1 block"
                    >
                        ... ({incidents.length - maxVisible} more)
                    </button>
                )}

                {showCollapseButton && (
                    <button
                        onClick={() => setIsExpanded(false)}
                        className="text-blue-600 hover:underline text-sm mt-2 block"
                    >
                        Show Less ↑
                    </button>
                )}
            </div>
        </div>
    );
};

export default CollapsibleIncidentsList;