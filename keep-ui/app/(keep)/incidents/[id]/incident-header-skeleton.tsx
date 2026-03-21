"use client";

import { Icon, Subtitle } from "@tremor/react";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import React from "react";
import { useTranslations } from "next-intl";

export function IncidentHeaderSkeleton() {
  const t = useTranslations("incidents");
  return (
    <header className="flex flex-col gap-4">
      <Subtitle className="text-sm">
        <Link href="/incidents">{t("allIncidents")}</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> {t("labels.incidentDetails")}
      </Subtitle>
    </header>
  );
}
