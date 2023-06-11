"use client";

import { Card, Title, Text, Button } from "@tremor/react";
import dynamic from "next/dynamic";
import { useState } from "react";
import Loader from "./loader";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

export default function Page() {
  const [fileContents, setFileContents] = useState<string | null>("");
  const [fileName, setFileName] = useState("");

  function loadAlert() {
    document.getElementById("alertFile")?.click();
  }

  function newAlert() {
    setFileContents(null);
    setFileName("");
  }

  function handleFileChange(event: any) {
    const file = event.target.files[0];
    const fName = event.target.files[0].name;
    const reader = new FileReader();
    reader.onload = (event) => {
      setFileName(fName);
      const contents = event.target!.result as string;
      setFileContents(contents);
    };
    reader.readAsText(file);
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl h-full">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>Builder</Title>
          <Text>Alert building kit</Text>
        </div>
        <div>
          <Button color="orange" size="md" className="mr-2" onClick={newAlert}>
            +
          </Button>
          <Button color="orange" size="md" className="mr-2" onClick={loadAlert}>
            Load
          </Button>
          <input
            type="file"
            id="alertFile"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          <Button disabled={true} color="orange" size="md">
            Generate 🚧
          </Button>
        </div>
      </div>
      <Card className="p-4 md:p-10 h-5/6 mx-auto max-w-7xl mt-6">
        {fileContents == "" ? (
          <Loader />
        ) : (
          <Builder loadedAlertFile={fileContents} fileName={fileName} />
        )}
      </Card>
    </main>
  );
}
