import { Accordion, AccordionBody, AccordionHeader } from "@tremor/react";
import { AlertDto, AlertKnownKeys } from "./models";
import { useEffect, useRef, useState } from "react";

export const getExtraPayloadNoKnownKeys = (alert: AlertDto) => {
  const extraPayload = Object.entries(alert).filter(
    ([key]) => !AlertKnownKeys.includes(key)
  );

  return {
    extraPayload: Object.fromEntries(extraPayload),
    extraPayloadLength: extraPayload.length,
  };
};

interface Props {
  alert: AlertDto;
  isToggled: boolean;
  setIsToggled: (newValue: boolean) => void;
}

export default function AlertExtraPayload({
  alert,
  isToggled = false,
  setIsToggled,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  const onAccordionToggle = () => {
    setIsToggled(!isToggled);
  };

  useEffect(() => {
    if (isToggled && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isToggled]);

  const { extraPayload, extraPayloadLength } =
    getExtraPayloadNoKnownKeys(alert);

  if (extraPayloadLength === 0) {
    return null;
  }

  return (
    <Accordion defaultOpen={isToggled}>
      <AccordionHeader onClick={onAccordionToggle}>
        Extra Payload
      </AccordionHeader>
      <AccordionBody ref={ref}>
        <pre className="overflow-auto max-w-lg">
          {JSON.stringify(extraPayload, null, 2)}
        </pre>
      </AccordionBody>
    </Accordion>
  );
}
