import { Button, Icon, Subtitle, Title } from "@tremor/react";
import { Dialog } from "@headlessui/react";
import { IoMdClose } from "react-icons/io";
import { useSearchParams } from "next/navigation";

type CorrelationSidebarHeaderProps = {
  toggle: VoidFunction;
};

export const CorrelationSidebarHeader = ({
  toggle,
}: CorrelationSidebarHeaderProps) => {
  const searchParams = useSearchParams();
  const isRuleBeingEdited = searchParams ? searchParams.get("id") : null;

  return (
    <div className="flex justify-between">
      <div>
        <Dialog.Title className="text-3xl font-bold" as={Title}>
          {isRuleBeingEdited ? "Edit" : "Create"} Correlation
        </Dialog.Title>
        <Dialog.Description as={Subtitle}>
          Group multiple alerts into a single incident
        </Dialog.Description>
      </div>
      <div>
        <Button onClick={toggle} variant="light">
          <Icon color="gray" icon={IoMdClose} size="xl" />
        </Button>
      </div>
    </div>
  );
};
