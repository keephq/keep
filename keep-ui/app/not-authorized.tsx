"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";

export default function NotAuthorized({ message }: { message?: string }) {
  const { t } = useI18n();
  const router = useRouter();
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Title>{t("notAuthorized.title")}</Title>
      <div className="flex flex-col items-center">
        <Subtitle>
          {message || t("notAuthorized.message")}
        </Subtitle>
        <Subtitle>
          <br />
          {t("notAuthorized.contactUs")}{" "}
          <Link
            href="https://slack.keephq.dev/"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("notAuthorized.slack")}
          </Link>
        </Subtitle>
      </div>
      <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      <Button
        onClick={() => {
          router.back();
        }}
        color="orange"
        variant="secondary"
      >
        {t("notAuthorized.goBack")}
      </Button>
    </div>
  );
}
