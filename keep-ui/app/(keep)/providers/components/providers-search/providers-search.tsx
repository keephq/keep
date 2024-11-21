import { FC, ChangeEvent } from "react";
import { TextInput } from "@tremor/react";
import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { useFilterContext } from "../../filter-context";

export const ProvidersSearch: FC = () => {
  const { providersSearchString, setProvidersSearchString } =
    useFilterContext();

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setProvidersSearchString(e.target.value);
  };

  return (
    <TextInput
      id="search-providers"
      icon={MagnifyingGlassIcon}
      placeholder="Filter providers..."
      value={providersSearchString}
      onChange={handleChange}
    />
  );
};
