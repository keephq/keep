import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import { Card, Callout } from "@tremor/react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { getApiURL } from "../../utils/apiUrl";
import Loader from "./loader";
import { Provider } from "../providers/providers";
import { fetcher } from "../../utils/fetcher";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

interface Props {
  accessToken: string;
  fileContents: string | null;
  fileName: string;
  enableButtons: () => void;
  enableGenerate: (state: boolean) => void;
  triggerGenerate: number;
}

export function BuilderCard({
  accessToken,
  fileContents,
  fileName,
  enableButtons,
  enableGenerate,
  triggerGenerate,
}: Props) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const apiUrl = getApiURL();

  const { data, error, isLoading } = useSWR(`${apiUrl}/providers`, (url) =>
    fetcher(url, accessToken)
  );

  useEffect(() => {
    if (data && !providers) {
      setProviders(data.providers);
      enableButtons();
    }
  }, [data, providers, enableButtons]);

  return (
    <Card
      className={`p-4 md:p-10 mx-auto max-w-7xl mt-6 ${error ? null : "h-5/6"}`}
    >
      {error ? (
        <Callout
          className="mt-4"
          title="Error"
          icon={ExclamationCircleIcon}
          color="rose"
        >
          Failed to load providers
        </Callout>
      ) : fileContents == "" || isLoading || !providers ? (
        <Loader />
      ) : (
        <Builder
          providers={providers}
          loadedAlertFile={fileContents}
          fileName={fileName}
          enableGenerate={enableGenerate}
          triggerGenerate={triggerGenerate}
        />
      )}
    </Card>
  );
}
