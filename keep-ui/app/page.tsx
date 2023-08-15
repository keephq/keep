import ProvidersPage from "./providers/page";

export const metadata = {
  title: "Keep Console",
  description: "Alerting and on-call management for modern engineering teams.",
};

export default async function IndexPage() {
  return (
    <div>
      <ProvidersPage />
    </div>
  );
}
