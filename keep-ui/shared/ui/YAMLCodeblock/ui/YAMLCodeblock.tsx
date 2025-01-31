"use client";

import { CopyBlock, a11yLight } from "react-code-blocks";
import { ArrowDownTrayIcon } from "@heroicons/react/20/solid";
import { Button } from "@/components/ui";
import { Card } from "@tremor/react";

interface Props {
  yamlString: string;
  filename: string;
}

export function downloadFileFromString(data: string, filename: string) {
  var blob = new Blob([data], { type: "text/plain" });
  var url = URL.createObjectURL(blob);

  var link = document.createElement("a");
  link.href = url;
  link.download = filename;

  link.click();

  URL.revokeObjectURL(url);
}

export function YAMLCodeblock({ yamlString, filename }: Props) {
  function download() {
    downloadFileFromString(yamlString, `${filename}.yaml`);
  }

  const copyBlockProps = {
    // gray-50 background
    theme: { ...a11yLight, backgroundColor: "#f9fafb" },
    customStyle: {
      height: "600px",
      overflowY: "scroll",
    },
    language: "yaml",
    text: yamlString,
    codeBlock: true,
  };

  return (
    <Card className="p-0 flex flex-col overflow-hidden">
      <CopyBlock {...copyBlockProps} />
      <div className="flex justify-end p-2 border-t border-gray-200">
        <Button
          color="orange"
          className="w-36"
          icon={ArrowDownTrayIcon}
          onClick={download}
          size="xs"
          variant="secondary"
        >
          Download
        </Button>
      </div>
    </Card>
  );
}
