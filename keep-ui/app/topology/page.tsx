import { Title } from "@tremor/react";
import TopologyPage from "./topology";

export default function Page() {
  return (
    <>
      <Title className="mb-5">Service Topology</Title>
      <TopologyPage />
    </>
  );
}

export const metadata = {
  title: "Keep - Service Topology",
  description: "See service topology and information about your services",
};
