"use client";

import { Card, Subtitle, Title } from "@tremor/react";
import Link from "next/link";
import Image from "next/image";
import deduplicationPlaceholder from "./deduplication-placeholder.svg";
import { useI18n } from "@/i18n/hooks/useI18n";

export const DeduplicationPlaceholder = () => {
  const { t } = useI18n();
  
  return (
    <>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">{t("rules.deduplication.messages.noRules")}</Title>
          <Subtitle className="text-gray-400">
            {t("rules.deduplication.messages.description1")}
            <br /> {t("rules.deduplication.messages.description2")}{" "}
            <Link href="/rules" className="underline text-orange-500">
              {t("rules.correlation.title")}
            </Link>
          </Subtitle>
          <Subtitle className="text-gray-400">
            {t("rules.deduplication.messages.activeHint")}
          </Subtitle>
        </div>
        <Image
          src={deduplicationPlaceholder}
          alt="Deduplication"
          className="max-w-full"
          width={871}
          height={391}
        />
      </Card>
    </>
  );
};
