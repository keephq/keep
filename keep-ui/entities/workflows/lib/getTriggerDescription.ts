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
        if (!trigger.properties?.interval) {
          return "Not set";
        }
        return `Every ${getHumanReadableInterval(trigger.properties.interval)} (${trigger.properties.interval} seconds)`;
      }
      case "alert": {
        const alertProperties = trigger.properties?.alert
          ? trigger.properties.alert
          : trigger.properties;
        return `${Object.entries(alertProperties)
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
