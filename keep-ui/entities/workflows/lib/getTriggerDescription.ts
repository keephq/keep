import { Trigger } from "@/shared/api/workflows";
import { getHumanReadableInterval } from "./getHumanReadableInterval";
import { V2StepTrigger } from "../model/types";

export function getTriggerDescription(trigger: Trigger) {
  try {
    switch (trigger.type) {
      case "manual": {
        return "Run now button";
      }
      case "interval": {
        return `Every ${getHumanReadableInterval(trigger.value)} (${trigger.value} seconds)`;
      }
      case "alert": {
        if (!trigger.filters) {
          return "On any alert";
        }
        return `${trigger.filters.map((f) => `${f.key}=${f.value}`).join(", ")}`;
      }
      case "incident": {
        return `On incident ${trigger.events.join(", ")}`;
      }
    }
  } catch (error) {
    console.error(error);
    return trigger.type;
  }
}

export function getTriggerDescriptionFromStep(trigger: V2StepTrigger) {
  try {
    switch (trigger.type) {
      case "manual": {
        return "Run now button";
      }
      case "interval": {
        // Handle both cases: properties as object with interval property, or properties as direct interval value
        let intervalValue;
        if (typeof trigger.properties === "string" || typeof trigger.properties === "number") {
          intervalValue = trigger.properties;
        } else if (trigger.properties?.interval) {
          intervalValue = trigger.properties.interval;
        }
        
        if (!intervalValue) {
          return "Not set";
        }
        return `Every ${getHumanReadableInterval(intervalValue)} (${intervalValue} seconds)`;
      }
      case "alert": {
        if (trigger.properties?.cel) {
          return `CEL: ${trigger.properties.cel}`;
        }
        const alertFilters = trigger.properties?.filters
          ? trigger.properties.filters
          : {};
        return `${Object.entries(alertFilters)
          .map(([key, value]) => `${key}=${value}`)
          .join(", ")}`;
      }
      case "incident": {
        return `On incident ${trigger.properties.incident.events.join(", ")}`;
      }
    }
  } catch (error) {
    console.error(error);
    return trigger.type;
  }
}
