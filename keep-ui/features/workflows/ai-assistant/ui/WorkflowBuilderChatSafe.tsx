import { useConfig } from "@/utils/hooks/useConfig";
import Image from "next/image";
import BuilderChatPlaceholder from "@/features/workflows/ai-assistant/ui/ai-workflow-placeholder.png";
import { SparklesIcon } from "@heroicons/react/24/outline";
import { Text, Title } from "@tremor/react";
import { Link } from "@/components/ui";
import { DefinitionV2 } from "@/entities/workflows";
import {
  WorkflowBuilderChat,
  WorkflowBuilderChatProps,
} from "@/features/workflows/ai-assistant/ui/WorkflowBuilderChat";

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
  const { data: config } = useConfig();

  // If AI is not enabled, return null to collapse the chat section
  if (!config?.OPEN_AI_API_KEY_SET) {
    return (
      <div className="flex flex-col items-center justify-center h-full relative">
        <Image
          src={BuilderChatPlaceholder}
          alt="Workflow AI Assistant"
          width={400}
          height={895}
          className="w-full h-full object-cover object-top max-w-[500px] mx-auto absolute inset-0"
        />
        <div className="w-full h-full absolute inset-0 bg-white/80" />
        <div className="flex flex-col items-center justify-center h-full z-10">
          <div className="flex flex-col items-center justify-center bg-[radial-gradient(circle,white_50%,transparent)] p-8 rounded-lg aspect-square">
            <SparklesIcon className="size-10 text-orange-500" />
            <Title>AI is disabled</Title>
            <Text>Contact us to enable AI for you.</Text>
            <Link
              href="https://slack.keephq.dev/"
              target="_blank"
              rel="noopener noreferrer"
            >
              Contact us
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
