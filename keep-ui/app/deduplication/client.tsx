"use client";

import { useDeduplicationRules } from "utils/hooks/useDeduplicationRules";
import { DeduplicationPlaceholder } from "./DeduplicationPlaceholder";
import { DeduplicationTable } from "./DeduplicationTable";
import Loading from "app/loading";

export const Client = () => {

    const { data: deduplicationRules = [], isLoading } = useDeduplicationRules();

    if (isLoading) {
        return <Loading />;
    }

    if (deduplicationRules.length === 0) {
        return <DeduplicationPlaceholder />;
      }

    return <DeduplicationTable deduplicationRules={deduplicationRules} />;
};
