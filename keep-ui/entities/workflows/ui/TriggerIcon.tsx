import { DynamicImageProviderIcon } from "@/components/ui/DynamicProviderIcon";
import {
  ClockIcon,
  CursorArrowRaysIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Trigger } from "@/shared/api/workflows";

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
    case "alert":
      const alertSource = trigger.filters?.find(
        (f) => f.key === "source"
      )?.value;
      if (alertSource) {
        return (
          <DynamicImageProviderIcon
            providerType={alertSource!}
            height="16"
            width="16"
            className={className}
          />
        );
      }
      return (
        <DynamicImageProviderIcon
          src="/keep.png"
          height="32"
          width="32"
          className={className}
        />
      );
    case "incident":
      return (
        <DynamicImageProviderIcon
          src="/keep.png"
          height="32"
          width="32"
          className={className}
        />
      );
    default:
      return <QuestionMarkCircleIcon className={className} />;
  }
}
