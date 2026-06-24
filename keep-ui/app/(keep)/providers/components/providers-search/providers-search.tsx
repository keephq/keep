import { FC, ChangeEvent } from "react";
import { TextInput } from "@tremor/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { useFilterContext } from "../../filter-context";
import { useTranslations } from "next-intl";

export const ProvidersSearch: FC = () => {
  const t = useTranslations("providers");
  const { providersSearchString, setProvidersSearchString } =
    useFilterContext();

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setProvidersSearchString(e.target.value);
  };

  return (
    <TextInput
      id="search-providers"
      icon={MagnifyingGlassIcon}
      placeholder={t("filterProviders")}
      className="w-full"
      value={providersSearchString}
      onChange={handleChange}
    />
  );
};
