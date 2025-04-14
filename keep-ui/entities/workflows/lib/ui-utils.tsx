import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import Image from "next/image";

const KeepIncidentIcon = () => (
  <Image
    src="/keep.png"
    className="tremor-Badge-icon shrink-0 -ml-1 mr-1.5"
    width={16}
    height={16}
    alt="Keep Incident"
  />
);
const KeepAlertIcon = () => (
  <Image
    src="/keep.png"
    className="tremor-Badge-icon shrink-0 -ml-1 mr-1.5"
    width={16}
    height={16}
    alt="Keep Alert"
  />
);

export function getTriggerIcon(triggered_by: string) {
  switch (triggered_by) {
    case "manual":
      return CursorArrowRaysIcon;
    case "interval":
      return ClockIcon;
    case "alert":
      return KeepAlertIcon;
    case "incident":
      return KeepIncidentIcon;
    default:
      return QuestionMarkCircleIcon;
  }
}

export function getTriggerIconV2(type: string, details: string) {
  switch (type) {
    case "manual":
      return CursorArrowRaysIcon;
    case "interval":
      return ClockIcon;
    case "alert":
      return KeepAlertIcon;
    case "incident":
      return KeepIncidentIcon;
    default:
      return QuestionMarkCircleIcon;
  }
}

export function extractTriggerValue(triggered_by: string | undefined): string {
  if (!triggered_by) return "others";

  if (triggered_by.startsWith("scheduler")) {
    return "interval";
  } else if (triggered_by.startsWith("type:alert")) {
    return "alert";
  } else if (triggered_by.startsWith("manually")) {
    return triggered_by;
  } else if (triggered_by.startsWith("type:incident:")) {
    const incidentType = triggered_by
      .substring("type:incident:".length)
      .split(" ")[0];
    return `incident ${incidentType}`;
  } else {
    return "others";
  }
}

export function extractTriggerType(
  triggered_by: string | undefined
): "interval" | "alert" | "manual" | "incident" | "unknown" {
  if (!triggered_by) {
    return "unknown";
  }

  if (triggered_by.startsWith("scheduler")) {
    return "interval";
  } else if (triggered_by.startsWith("type:alert")) {
    return "alert";
  } else if (triggered_by.startsWith("manually")) {
    return "manual";
  } else if (triggered_by.startsWith("type:incident:")) {
    return "incident";
  } else {
    return "unknown";
  }
}

export function extractTriggerDetails(
  triggered_by: string | undefined
): string[] {
  if (!triggered_by) {
    return [];
  }

  let details: string;
  if (triggered_by.startsWith("scheduler")) {
    details = triggered_by.substring("scheduler".length).trim();
  } else if (triggered_by.startsWith("type:alert")) {
    details = triggered_by.substring("type:alert".length).trim();
  } else if (triggered_by.startsWith("manual")) {
    details = triggered_by.substring("manual".length).trim();
  } else if (triggered_by.startsWith("type:incident:")) {
    // Handle 'type:incident:{some operator}' by removing the operator
    details = triggered_by.substring("type:incident:".length).trim();
    const firstSpaceIndex = details.indexOf(" ");
    if (firstSpaceIndex > -1) {
      details = details.substring(firstSpaceIndex).trim();
    } else {
      details = "";
    }
  } else {
    details = triggered_by;
  }

  // Split the string into key-value pairs, where values may contain spaces
  const regex = /\b(\w+:[^:]+?)(?=\s\w+:|$)/g;
  const matches = details.match(regex);

  return matches ?? [];
}

type TriggerDetails = {
  type: "manual" | "interval" | "alert" | "incident" | "unknown";
  details: Record<string, string>;
};

export function extractTriggerDetailsV2(
  triggered_by: string | undefined
): TriggerDetails {
  if (!triggered_by) {
    return { type: "unknown", details: {} };
  }

  let type: TriggerDetails["type"] = extractTriggerType(triggered_by);
  let details: string;
  if (triggered_by.startsWith("scheduler")) {
    // details = triggered_by.substring("scheduler".length).trim();
    details = "scheduler";
  } else if (triggered_by.startsWith("type:alert")) {
    details = triggered_by.substring("type:alert".length).trim();
  } else if (triggered_by.startsWith("manually by")) {
    details = "user:" + triggered_by.substring("manually by".length).trim();
  } else if (triggered_by.startsWith("type:incident:")) {
    // Handle 'type:incident:{some operator}' by removing the operator
    details = triggered_by.substring("type:incident:".length).trim();
    const firstSpaceIndex = details.indexOf(" ");
    if (firstSpaceIndex > -1) {
      details = details.substring(firstSpaceIndex).trim();
    } else {
      details = "";
    }
  } else {
    details = triggered_by;
  }

  // Split the string into key-value pairs, where values may contain spaces
  const regex = /\b(\w+:[^:]+?)(?=\s\w+:|$)/g;
  const matches = details.match(regex);

  return {
    type,
    details: matches
      ? Object.fromEntries(
          matches.map((match) => {
            const [key, value] = match.split(":");
            return [key, value];
          })
        )
      : {},
  };
}
