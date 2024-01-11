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
}

export default function AlertExtraPayload({ alert }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  function handleAccordionToggle() {
    setIsExpanded(!isExpanded);
  }

  useEffect(() => {
    if (isExpanded && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [isExpanded]);

  const { extraPayload, extraPayloadLength } =
    getExtraPayloadNoKnownKeys(alert);

  if (extraPayloadLength === 0) {
    return null;
  }

  return (
    <div>
      <Accordion>
        <AccordionHeader onClick={handleAccordionToggle}>
          Extra Payload
        </AccordionHeader>
        <AccordionBody ref={ref}>
          <pre className="overflow-y-scroll">
            {JSON.stringify(extraPayload, null, 2)}
          </pre>
        </AccordionBody>
      </Accordion>
    </div>
  );
}
