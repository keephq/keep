import Maintenance from "./maintenance"; // Adjust the import based on the folder structure

export default function Page() {
  return <Maintenance />;
}

export const metadata = {
  title: "Keep - Maintenance Rules Management",
  description:
    "Manage maintenance windows to ignore alerts during scheduled downtimes.",
};
