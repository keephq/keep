"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";

export default function NotFound() {
  const router = useRouter();
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Title>{t("notFound.title")}</Title>
      <Subtitle>
        {t("notFound.message")}
        {" "}
        <Link
          href="https://slack.keephq.dev/"
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("notFound.slack")}
        </Link>
      </Subtitle>
      <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      <Button
        onClick={() => {
          router.back();
        }}
        color="orange"
        variant="secondary"
      >
        {t("notFound.goBack")}
      </Button>
    </div>
  );
}
