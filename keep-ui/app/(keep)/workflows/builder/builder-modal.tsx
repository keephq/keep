import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { stringify } from "yaml";
import { LegacyWorkflow } from "./legacy-workflow.types";
import { YAMLCodeblock } from "@/shared/ui";

interface Props {
  closeModal: () => void;
  compiledAlert: LegacyWorkflow | string | null;
  id?: string;
  hideCloseButton?: boolean;
}

export default function BuilderModalContent({
  closeModal,
  compiledAlert,
  id,
  hideCloseButton,
}: Props) {
  const alertYaml =
    typeof compiledAlert !== "string"
      ? stringify(compiledAlert)
      : compiledAlert;

  const fileName =
    (typeof compiledAlert == "string" ? id : compiledAlert!.id) ?? "workflow";

  return (
    <>
      <div className="flex justify-between items-center mb-2">
        <div>
          <Title>Generated Workflow YAML</Title>
          <Subtitle>Keep workflow specification ready to use</Subtitle>
        </div>
        <div>
          {!hideCloseButton && (
            <Button
              color="orange"
              className="w-36"
              icon={XMarkIcon}
              onClick={closeModal}
              size="xs"
            >
              Close
            </Button>
          )}
        </div>
      </div>
      <Card className="p-0 max-w-7xl overflow-hidden">
        <YAMLCodeblock yamlString={alertYaml} filename={fileName} />
      </Card>
    </>
  );
}
