import useSWR from "swr";
import { Provider } from "./providers";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { Subtitle, Title, Text, Icon } from "@tremor/react";
import { CopyBlock, a11yLight, railscast } from "react-code-blocks";
import Image from "next/image";
import { ArrowLongRightIcon } from "@heroicons/react/24/outline";

interface WebhookSettings {
  webhookDescription: string;
  webhookTemplate: string;
}

interface Props {
  provider: Provider;
  accessToken: string;
}

export const ProviderSemiAutomated = ({ provider, accessToken }: Props) => {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<WebhookSettings>(
    `${apiUrl}/providers/${provider.type}/webhook`,
    (url) => fetcher(url, accessToken)
  );

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  const settings = {
    theme: { ...a11yLight },
    customStyle: {
      backgroundColor: "white",
      color: "orange",
      maxHeight: "200px",
      overflow: "scroll",
    },
    language: "yaml",
    text: data!.webhookTemplate,
    codeBlock: true,
  };

  return (
    <div className="my-2.5">
      <Title>
        Push alerts from{" "}
        {provider.type.charAt(0).toLocaleUpperCase() + provider.type.slice(1)}
      </Title>
      <div className="flex">
        <Image
          src={`/icons/${provider.type}-icon.png`}
          width={64}
          height={55}
          alt={provider.type}
          className="mt-5 mb-9 mr-2.5"
        />
        <Icon icon={ArrowLongRightIcon} size="xl" color="orange" />
        <Image
          src={`/keep.png`}
          width={55}
          height={64}
          alt={provider.type}
          className="mt-5 mb-9 ml-2.5"
        />
      </div>
      <Subtitle>
        Seamlessly push alerts without actively connecting {provider.type}
      </Subtitle>
      <Text className="my-2.5">{data!.webhookDescription}</Text>
      <CopyBlock {...settings} />
    </div>
  );
};
