"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { RiSparkling2Line } from "react-icons/ri";

import { useEffect, useState } from "react";
import { usePollAILogs } from "utils/hooks/useAI";
import { useI18n } from "@/i18n/hooks/useI18n";

export const AILink = () => {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [newText, setNewText] = useState(() => t("aiPlugins.title"));
  const [iteratedText, setIteratedText] = useState(() => t("aiPlugins.iterated"));

  const mutateAILogs = (logs: any) => {
    setNewText(iteratedText);
  };

  usePollAILogs(mutateAILogs);

  useEffect(() => {
    let index = 0;

    const interval = setInterval(() => {
      setText(newText.slice(0, index + 1));
      index++;

      if (index === newText.length) {
        clearInterval(interval);
      }
    }, 100);

    return () => {
      clearInterval(interval);
    };
  }, [newText]);

  return (
    <LinkWithIcon href="/ai" icon={RiSparkling2Line} className="w-full">
      <div className="flex justify-between items-center w-full">
        <Subtitle className="text-xs break-all">{text}</Subtitle>
      </div>
    </LinkWithIcon>
  );
};
