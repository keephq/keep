import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CopyBlock, a11yLight } from "react-code-blocks";
import { stringify } from "yaml";
import { Alert } from "./alert";
import { useState } from "react";
import ReactLoading from "react-loading";
import { ArrowDownTrayIcon } from "@heroicons/react/20/solid";
import { downloadFileFromString } from "./utils";

interface Props {
  closeModal: () => void;
  compiledAlert: Alert | string | null;
  id?: string;
  hideCloseButton?: boolean;
}

export default function BuilderModalContent({
  closeModal,
  compiledAlert,
  id,
  hideCloseButton,
}: Props) {
  const [isLoading, setIsLoading] = useState(true);

  // Mocking some async code
  setTimeout(
    () => {
      setIsLoading(false);
    },
    Math.floor(Math.random() * 2500 + 1000)
  );

  const alertYaml =
    typeof compiledAlert !== "string"
      ? stringify(compiledAlert)
      : compiledAlert;

  function download() {
    const fileName = typeof compiledAlert == "string" ? id : compiledAlert!.id;
    downloadFileFromString(alertYaml, `${fileName}.yaml`);
  }

  const copyBlockProps = {
    theme: { ...a11yLight },
    customStyle: {
      height: "450px",
      overflowY: "scroll",
    },
    language: "yaml",
    text: alertYaml,
    codeBlock: true,
  };

  return (
    <>
      <div className="flex justify-between items-center">
        <div>
          <Title>Generated Alert</Title>
          <Subtitle>Keep alert specification ready to use</Subtitle>
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
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6 h-full`}>
        <div className="flex flex-col">
          {!isLoading ? (
            <>
              <CopyBlock {...copyBlockProps} />
              <div className="flex justify-end">
                <Button
                  color="orange"
                  className="w-36 mt-2.5"
                  icon={ArrowDownTrayIcon}
                  onClick={download}
                  size="xs"
                  variant="secondary"
                  disabled={isLoading}
                >
                  Download
                </Button>
              </div>
            </>
          ) : (
            <div className="flex justify-center">
              <ReactLoading
                type="spin"
                color="rgb(234 160 112)"
                height={50}
                width={50}
              />
            </div>
          )}
        </div>
      </Card>
    </>
  );
}
