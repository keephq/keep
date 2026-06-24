import { Card, Subtitle, Title } from "@tremor/react";
import Link from "next/link";
import Image from "next/image";
import deduplicationPlaceholder from "./deduplication-placeholder.svg";
import { useTranslations } from "next-intl";

export const DeduplicationPlaceholder = () => {
  const t = useTranslations("deduplication");
  return (
    <>
      <Card className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">{t("noDeduplicationsYet")}</Title>
          <Subtitle className="text-gray-400">
            {t("deduplicationDescription")}
            <br /> {t("checkCorrelations")}{" "}
            <Link href="/rules" className="underline text-orange-500">
              {t("correlations")}
            </Link>
          </Subtitle>
          <Subtitle className="text-gray-400">
            {t("pageWillBecomeActive")}
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
