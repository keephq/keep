import { useI18n } from "@/i18n/hooks/useI18n";
import type { FC } from "react";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import { TagIcon } from "@heroicons/react/20/solid";
import { useFilterContext, PROVIDER_LABELS } from "../../filter-context";
import type { TProviderLabels } from "@/shared/api/providers";

export const ProvidersFilterByLabel: FC = (props) => {
  const { t } = useI18n();
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
      placeholder={t("providers.allLabels")}
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
