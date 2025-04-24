import { DynamicImageProviderIcon } from "@/components/ui/DynamicProviderIcon";
import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Trigger } from "@/shared/api/workflows";
import clsx from "clsx";

export function TriggerIcon({
  trigger,
  className = "size-5",
}: {
  trigger: Trigger;
  className?: string;
}) {
  const { type } = trigger;
  switch (type) {
    case "manual":
      return <CursorArrowRaysIcon className={className} />;
    case "interval":
      return <ClockIcon className={className} />;
    case "alert": {
      const alertSource = trigger.filters?.find((f) => f.key === "source")
        ?.value;
      if (alertSource) {
        return (
          <div className={clsx("flex items-center justify-center", className)}>
            <DynamicImageProviderIcon
              providerType={alertSource}
              src={`/icons/${alertSource}-icon.png`}
              height="16"
              width="16"
            />
          </div>
        );
      }
      return (
        <DynamicImageProviderIcon
          src="/keep.png"
          height="32"
          width="32"
          className={clsx("object-contain object-center", className)}
        />
      );
    }
    case "incident":
      return (
        <DynamicImageProviderIcon
          src="/keep.png"
          height="32"
          width="32"
          className={clsx("object-contain object-center", className)}
        />
      );
    default:
      return <QuestionMarkCircleIcon className={className} />;
  }
}
