import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import { CodeBlock, CopyBlock, a11yLight } from "react-code-blocks";
import { stringify } from "yaml";
import { Alert } from "./alert";
import { useState } from "react";
import ReactLoading from "react-loading";
import { ArrowDownTrayIcon } from "@heroicons/react/20/solid";

interface Props {
  closeModal: () => void;
  compiledAlert: Alert | null;
}

export default function BuilderModalContent({
  closeModal,
  compiledAlert,
}: Props) {
  const [isLoading, setIsLoading] = useState(true);

  // Mocking some async code
  setTimeout(() => {
    setIsLoading(false);
  }, Math.floor(Math.random() * 2500 + 1000));

  function download() {}

  return (
    <>
      <div className="flex justify-between items-center">
        <div>
          <Title>Generated Alert</Title>
          <Subtitle>Keep alert specification ready to use</Subtitle>
        </div>
        <div>
          <Button
            color="orange"
            className="w-36"
            icon={XMarkIcon}
            onClick={closeModal}
            size="xs"
          >
            Close
          </Button>
        </div>
      </div>
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6 h-full`}>
        <div className="flex flex-col">
          {!isLoading ? (
            <>
              <CopyBlock
                language="yaml"
                text={stringify(compiledAlert, { indent: 2 })}
                theme={a11yLight}
                customStyle={{
                  height: "450px",
                  overflowY: "scroll",
                }}
                codeBlock={true}
              />
              <div className="flex justify-end">
                <Button
                  color="orange"
                  className="w-36 mt-2.5"
                  icon={ArrowDownTrayIcon}
                  onClick={download}
                  size="xs"
                  variant="secondary"
                  //   disabled={isLoading}
                  disabled={true}
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
