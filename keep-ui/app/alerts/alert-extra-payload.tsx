import { Accordion, AccordionBody, AccordionHeader } from "@tremor/react";
import { AlertDto, AlertKnownKeys } from "./models";

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
  const { extraPayload, extraPayloadLength } =
    getExtraPayloadNoKnownKeys(alert);

  if (extraPayloadLength === 0) {
    return null;
  }

  return (
    <div>
      <Accordion>
        <AccordionHeader>Extra Payload</AccordionHeader>
        <AccordionBody>
          <pre className="overflow-y-scroll">
            {JSON.stringify(extraPayload, null, 2)}
          </pre>
        </AccordionBody>
      </Accordion>
    </div>
  );
}
