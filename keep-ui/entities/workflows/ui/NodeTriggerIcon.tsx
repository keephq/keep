import { DynamicImageProviderIcon } from "@/components/ui/DynamicProviderIcon";
import { FlowNode } from "../model/types";
import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";

export function NodeTriggerIcon({ nodeData }: { nodeData: FlowNode["data"] }) {
  const { type } = nodeData;
  switch (type) {
    case "manual":
      return <CursorArrowRaysIcon className="size-8" />;
    case "interval":
      return <ClockIcon className="size-8" />;
    case "alert": {
      const alertSource = nodeData.properties?.source;
      if (alertSource) {
        return (
          <DynamicImageProviderIcon
            key={alertSource}
            providerType={alertSource}
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
