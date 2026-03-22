import { useConfig } from "@/utils/hooks/useConfig";
import { useI18n } from "@/i18n/hooks/useI18n";
import Image from "next/image";
import { SparklesIcon } from "@heroicons/react/24/outline";
import { Text, Title } from "@tremor/react";
import { Link } from "@/components/ui";
import { DefinitionV2 } from "@/entities/workflows";
import {
  WorkflowBuilderChat,
  WorkflowBuilderChatProps,
} from "./WorkflowBuilderChat";
import BuilderChatPlaceholder from "./ai-workflow-placeholder.png";

type WorkflowBuilderChatSafeProps = Omit<
  WorkflowBuilderChatProps,
  "definition"
> & {
  definition: DefinitionV2 | null;
};

export function WorkflowBuilderChatSafe({
  definition,
  ...props
}: WorkflowBuilderChatSafeProps) {
  const { t } = useI18n();
  const { data: config } = useConfig();

  // If AI is not enabled, return null to collapse the chat section
  if (!config?.OPEN_AI_API_KEY_SET) {
    return (
      <div className="flex flex-col items-center justify-center h-full relative">
        <Image
          src={BuilderChatPlaceholder}
          alt={t("workflows.aiAssistant.aiDisabledTitle")}
          width={400}
          height={895}
          className="w-full h-full object-cover object-top max-w-[500px] mx-auto absolute inset-0"
        />
        <div className="w-full h-full absolute inset-0 bg-white/80" />
        <div className="flex flex-col items-center justify-center h-full z-10">
          <div className="flex flex-col items-center justify-center bg-[radial-gradient(circle,white_50%,transparent)] p-8 rounded-lg aspect-square">
            <SparklesIcon className="size-10 text-orange-500" />
            <Title>{t("workflows.aiAssistant.aiDisabled")}</Title>
            <Text>{t("workflows.aiAssistant.aiDisabledDescription")}</Text>
            <Link
              href="https://slack.keephq.dev/"
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("workflows.aiAssistant.contactUs")}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (definition == null) {
    return null;
  }

  return <WorkflowBuilderChat definition={definition} {...props} />;
}
