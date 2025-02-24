import useSWR from "swr";
import { Provider } from "@/shared/api/providers";
import { Subtitle, Title, Text, Icon } from "@tremor/react";
import { CopyBlock, a11yLight, railscast } from "react-code-blocks";
import Image from "next/image";
import { ArrowLongRightIcon } from "@heroicons/react/24/outline";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useApi } from "@/shared/lib/hooks/useApi";
import { DynamicImageProviderIcon } from "@/components/ui";

interface WebhookSettings {
  webhookDescription: string;
  webhookTemplate: string;
  webhookMarkdown: string;
}

interface Props {
  provider: Provider;
}

export const ProviderSemiAutomated = ({ provider }: Props) => {
  const api = useApi();
  const { data, error, isLoading } = useSWR<WebhookSettings>(
    `/providers/${provider.type}/webhook`,
    (url: string) => api.get(url)
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

  const isMultiline = data!.webhookDescription.includes("\n");
  const descriptionLines = data!.webhookDescription.split("\n");
  const settingsNotEmpty = settings.text.trim().length > 0;
  const webhookMarkdown = data!.webhookMarkdown;
  return (
    <div className="my-2.5">
      <Title>
        Push alerts from{" "}
        {provider.type.charAt(0).toLocaleUpperCase() +
          provider.display_name.slice(1)}
      </Title>
      <div className="flex">
        <DynamicImageProviderIcon
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
        Seamlessly push alerts without actively connecting{" "}
        {provider.display_name}
      </Subtitle>
      {isMultiline ? (
        descriptionLines.map((line, index) => (
          <Text key={index} className="my-2.5 whitespace-pre-wrap">
            {line}
          </Text>
        ))
      ) : (
        <Text className="my-2.5">{data!.webhookDescription}</Text>
      )}
      {settingsNotEmpty && <CopyBlock {...settings} />}
      {webhookMarkdown && (
        <div className="prose whitespace-nowrap">
          <Markdown remarkPlugins={[remarkGfm]}>{webhookMarkdown}</Markdown>
        </div>
      )}
    </div>
  );
};
