import { useState } from "react";
import Link from "next/link";
import { IncidentDto } from "@/entities/incidents/model";
import { useI18n } from "@/i18n/hooks/useI18n";
interface CollapsibleIncidentsListProps {
    incidents: IncidentDto[];
}

const CollapsibleIncidentsList = ({ incidents }: CollapsibleIncidentsListProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const { t } = useI18n();
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
                        {t("alerts.incidentsList.moreCount", { count: incidents.length - maxVisible })}
                    </button>
                )}

                {showCollapseButton && (
                    <button
                        onClick={() => setIsExpanded(false)}
                        className="text-blue-600 hover:underline text-sm mt-2 block"
                    >
                        {t("alerts.incidentsList.showLess")}
                    </button>
                )}
            </div>
        </div>
    );
};

export default CollapsibleIncidentsList;