import { AiOutlineAlert } from "react-icons/ai";
import { getServerSession } from "next-auth";
import { Search } from "components/navbar/Search";
import { ConfigureLinks } from "components/navbar/ConfigureLinks";
import { AnalyzeLinks } from "components/navbar/AnalyzeLinks";
import { LearnLinks } from "components/navbar/LearnLinks";
import { UserInfo } from "components/navbar/UserInfo";
import InitPostHog from "components/navbar/init-posthog";

// noc navigation incldues only alerts
const nocNavigation = [
  { name: "Alerts", href: "/alerts", icon: AiOutlineAlert },
];

export default async function NavbarInner() {
  const session = await getServerSession();

  const isNOCRole = session?.userRole === "noc";

  return (
    <>
      <InitPostHog />
      <aside className="bg-gray-50 col-span-1 border-r border-gray-300 h-full">
        <nav className="flex flex-col h-full">
          <div className="flex-1 h-full">
            <Search />
            <div className="pt-6 px-2 space-y-9">
              <ConfigureLinks isNOCRole={isNOCRole} />
              <AnalyzeLinks />
              <LearnLinks />
            </div>
          </div>

          <UserInfo />
        </nav>
      </aside>
    </>
  );
}
