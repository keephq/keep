import { Button } from "@tremor/react";

import {
  Drawer as TremorDrawer,
  DrawerBody,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  DrawerDescription,
} from "./TremorDrawer";

export function Drawer({
  children,
  isOpen,
  onClose,
  title,
  description,
  className,
}: {
  children: React.ReactNode;
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  className?: string;
}) {
  return (
    <TremorDrawer
      open={isOpen}
      onOpenChange={(modalOpen) => {
        if (!modalOpen) {
          onClose();
        }
      }}
    >
      {/* <DrawerTrigger asChild>
        <Button variant="secondary">Open Drawer</Button>
      </DrawerTrigger> */}
      <DrawerContent className="sm:max-w-lg">
        {/* <DrawerHeader>
          <DrawerTitle>{title}</DrawerTitle>
          <DrawerDescription className="mt-1 text-sm">
            {description}
          </DrawerDescription>
        </DrawerHeader> */}
        <DrawerBody>{children}</DrawerBody>
        {/* <DrawerFooter className="mt-6">
          <DrawerClose asChild>
            <Button
              className="mt-2 w-full sm:mt-0 sm:w-fit"
              variant="secondary"
            >
              Go back
            </Button>
          </DrawerClose>
          <DrawerClose asChild>
            <Button className="w-full sm:w-fit">Ok, got it!</Button>
          </DrawerClose>
        </DrawerFooter> */}
      </DrawerContent>
    </TremorDrawer>
  );
}
