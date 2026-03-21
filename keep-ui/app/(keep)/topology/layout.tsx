import { useI18n } from "@/i18n/hooks/useI18n";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";

export default function Layout({ children }: { children: any }) {
  return <TopologySearchProvider>{children}</TopologySearchProvider>;
}
