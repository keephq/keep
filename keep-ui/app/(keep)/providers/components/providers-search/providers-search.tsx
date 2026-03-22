import { useI18n } from "@/i18n/hooks/useI18n";
import { FC, ChangeEvent } from "react";
import { TextInput } from "@tremor/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { useFilterContext } from "../../filter-context";

export const ProvidersSearch: FC = () => {
  const { t } = useI18n();
  const { providersSearchString, setProvidersSearchString } =
    useFilterContext();

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setProvidersSearchString(e.target.value);
  };

  return (
    <TextInput
      id="search-providers"
      icon={MagnifyingGlassIcon}
      placeholder={t("providers.filterProviders")}
      className="w-full"
      value={providersSearchString}
      onChange={handleChange}
    />
  );
};
