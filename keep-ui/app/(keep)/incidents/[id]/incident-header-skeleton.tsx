"use client";

import { Icon, Subtitle } from "@tremor/react";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import React from "react";

export function IncidentHeaderSkeleton() {
  return (
    <header className="flex flex-col gap-4">
      <Subtitle className="text-sm">
        <Link href="/incidents">All Incidents</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Incident Details
      </Subtitle>
    </header>
  );
}
