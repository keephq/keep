import { Button, Icon, Subtitle, Title } from "@tremor/react";
import { Dialog } from "@headlessui/react";
import { IoMdClose } from "react-icons/io";

type CreateCorrelationSidebarHeaderProps = {
  toggle: VoidFunction;
};

export const CreateCorrelationSidebarHeader = ({
  toggle,
}: CreateCorrelationSidebarHeaderProps) => (
  <div className="flex justify-between">
    <div>
      <Dialog.Title className="text-3xl font-bold" as={Title}>
        Create Correlations
      </Dialog.Title>
      <Dialog.Description as={Subtitle}>
        Group multiple alerts into single alert
      </Dialog.Description>
    </div>
    <div>
      <Button onClick={toggle} variant="light">
        <Icon color="gray" icon={IoMdClose} size="xl" />
      </Button>
    </div>
  </div>
);
