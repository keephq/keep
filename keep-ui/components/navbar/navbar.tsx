import { getServerSession } from "next-auth";
import { Search } from "components/navbar/Search";
import { ConfigureLinks } from "components/navbar/ConfigureLinks";
import { AnalyseLinks } from "components/navbar/AnalyseLinks";
import { LearnLinks } from "components/navbar/LearnLinks";
import { UserInfo } from "components/navbar/UserInfo";
import { InitPostHog } from "components/navbar/InitPostHog";

export default async function NavbarInner() {
  const session = await getServerSession();

  return (
    <>
      <InitPostHog />
      <aside className="bg-gray-50 col-span-1 border-r border-gray-300 h-full">
        <nav className="flex flex-col h-full">
          <div className="flex-1 h-full">
            <Search />
            <div className="pt-6 space-y-4">
              <AnalyseLinks />
              <ConfigureLinks session={session} />
              <LearnLinks />
            </div>
          </div>

          <UserInfo session={session} />
        </nav>
      </aside>
    </>
  );
}
