import { DynamicImageProviderIcon } from "@/components/ui/DynamicProviderIcon";
import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { NodeData } from "../model/types";

export function NodeTriggerIcon({ nodeData }: { nodeData: NodeData }) {
  if (nodeData.componentType !== "trigger") {
    return null;
  }
  switch (nodeData.type) {
    case "manual":
      return <CursorArrowRaysIcon className="size-8" />;
    case "interval":
      return <ClockIcon className="size-8" />;
    case "alert": {
      const alertSource = nodeData.properties?.source;
      console.log(alertSource);
      console.log(nodeData);
      if (alertSource) {
        return (
          <DynamicImageProviderIcon
            key={alertSource}
            providerType={alertSource}
            src={`/icons/${alertSource}-icon.png`}
            height="32"
            width="32"
          />
        );
      }
      return (
        <DynamicImageProviderIcon src="/keep.png" height="32" width="32" />
      );
    }
    case "incident":
      return (
        <DynamicImageProviderIcon src="/keep.png" height="32" width="32" />
      );
    default:
      return <QuestionMarkCircleIcon className="size-8" />;
  }
}
