import React, { useRef } from "react";
import { Popover } from "@headlessui/react";
import { arrow, FloatingArrow, offset, useFloating } from "@floating-ui/react";
import { Button } from "@tremor/react";
import { IconType } from "react-icons";

interface PopoverProps {
  triggerText: string;
  triggerIcon?: IconType;
  triggerColor?: string;
  triggerVariant?: "light" | "dark";
  content: React.JSX.Element;
  buttonLabel?: string;
  onApply?: () => void;
}

const GenericPopover: React.FC<PopoverProps> = ({
  triggerText,
  triggerIcon,
  triggerColor = "gray",
  triggerVariant = "light",
  content,
  buttonLabel = "Apply",
  onApply,
}) => {
  const arrowRef = useRef(null);
  const { refs, floatingStyles, context } = useFloating({
    strategy: "fixed",
    placement: "bottom-end",
    middleware: [
      offset({ mainAxis: 10 }),
      arrow({
        element: arrowRef,
      }),
    ],
  });

  return (
    <Popover>
      {({ close }) => (
        <>
          <Popover.Button
            variant="light"
            as={Button}
            icon={triggerIcon}
            ref={refs.setReference}
            className="bg-white rounded-lg border-dotted border-2 py-2 px-6 border-gray-200 text-black"
          >
            {triggerText}
          </Popover.Button>
          <Popover.Overlay className="fixed inset-0 bg-black opacity-30 z-20" />
          <Popover.Panel
            className="bg-white z-30 p-4 rounded-sm"
            ref={refs.setFloating}
            style={floatingStyles}
          >
            <FloatingArrow
              className="fill-white [&>path:last-of-type]:stroke-white"
              ref={arrowRef}
              context={context}
            />
            {content}
            <Button
              className="mt-5 float-right"
              color="orange"
              onClick={() => {
                if (onApply) onApply();
                close();
              }}
            >
              {buttonLabel}
            </Button>
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
};

export default GenericPopover;
