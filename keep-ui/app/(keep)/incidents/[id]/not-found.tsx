"use client";

import { Link } from "@/components/ui";
import { Title, Button, Subtitle } from "@tremor/react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

export default function NotFound() {
  const t = useTranslations("incidents.messages");
  const router = useRouter();
  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-10rem)]">
      <Title>{t("notFound")}</Title>
      <Subtitle>
        {t("notFoundHelp")}{" "}
        <Link
          href="https://slack.keephq.dev/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Slack
        </Link>
      </Subtitle>
      <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      <Button
        onClick={() => {
          router.push("/incidents");
        }}
        color="orange"
        variant="secondary"
      >
        {t("goAllIncidents")}
      </Button>
    </div>
  );
}
