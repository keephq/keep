import type { FC } from "react";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import { TagIcon } from "@heroicons/react/20/solid";
import { useFilterContext, PROVIDER_LABELS } from "../../filter-context";
import type { TProviderLabels } from "@/shared/api/providers";
import { useTranslations } from "next-intl";

export const ProvidersFilterByLabel: FC = (props) => {
  const t = useTranslations("providers");
  const { setProvidersSelectedTags, providersSelectedTags } =
    useFilterContext();

  const headerSelect = (value: string[]) => {
    setProvidersSelectedTags(value as TProviderLabels[]);
  };

  const options = Object.entries(PROVIDER_LABELS);

  return (
    <MultiSelect
      onValueChange={headerSelect}
      value={providersSelectedTags}
      placeholder={t("allLabels")}
      className="w-64 ml-2.5"
      icon={TagIcon}
    >
      {options.map(([value, label]) => (
        <MultiSelectItem key={value} value={value}>
          {label}
        </MultiSelectItem>
      ))}
    </MultiSelect>
  );
};
