"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Icon, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col h-full gap-4">
      <Subtitle className="text-sm">
        <Link href="/workflows">{t("workflows.breadcrumbs.allWorkflows")}</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> {t("workflows.tabs.builder")}
      </Subtitle>
      <div className="flex-1 h-full">{children}</div>
    </div>
  );
}
