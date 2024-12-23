import { Accordion, AccordionBody, AccordionHeader } from "@tremor/react";
import { AlertDto, AlertKnownKeys } from "@/entities/alerts/model";

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
  const onAccordionToggle = () => {
    setIsToggled(!isToggled);
  };

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
      <AccordionBody>
        <pre className="overflow-auto">
          {JSON.stringify(extraPayload, null, 2)}
        </pre>
      </AccordionBody>
    </Accordion>
  );
}
