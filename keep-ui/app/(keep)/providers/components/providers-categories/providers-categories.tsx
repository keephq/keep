import { TProviderCategory } from "@/shared/api/providers";
import { Badge } from "@tremor/react";
import { useFilterContext } from "../../filter-context";

export const ProvidersCategories = () => {
  const { providersSelectedCategories, setProvidersSelectedCategories } =
    useFilterContext();

  const categories: TProviderCategory[] = [
    "AI",
    "Monitoring",
    "Incident Management",
    "Cloud Infrastructure",
    "Ticketing",
    "Developer Tools",
    "Database",
    "Identity and Access Management",
    "Security",
    "Collaboration",
    "CRM",
    "Queues",
    "Orchestration",
    "Coming Soon",
    "Others",
  ];

  const toggleCategory = (category: TProviderCategory) => {
    setProvidersSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  return (
    <div className="w-full flex flex-wrap justify-start gap-2 mt-2.5">
      {categories.map((category) => (
        <Badge
          color={
            providersSelectedCategories.includes(category) ? "orange" : "slate"
          }
          className={`rounded-full ${
            providersSelectedCategories.includes(category)
              ? "shadow-inner"
              : "hover:shadow-inner"
          } cursor-pointer`}
          key={category}
          onClick={() => toggleCategory(category)}
        >
          {category}
        </Badge>
      ))}
    </div>
  );
};
