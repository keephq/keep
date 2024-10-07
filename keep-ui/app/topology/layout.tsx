import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";

export default function Layout({ children }: { children: any }) {
  return <TopologySearchProvider>{children}</TopologySearchProvider>;
}
