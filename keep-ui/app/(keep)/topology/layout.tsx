import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";

export default function Layout({ children }: { children: any }) {
  return <TopologySearchProvider>{children}</TopologySearchProvider>;
}
