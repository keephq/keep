import { getServerSession } from "next-auth";
import { Search } from "components/navbar/Search";
import { ConfigureLinks } from "components/navbar/ConfigureLinks";
import { AnalyseLinks } from "components/navbar/AnalyseLinks";
import { LearnLinks } from "components/navbar/LearnLinks";
import { UserInfo } from "components/navbar/UserInfo";
import { InitPostHog } from "components/navbar/InitPostHog";
import { Menu } from "components/navbar/Menu";
import { MinimizeMenuButton } from "./MinimizeMenuButton";
import {authOptions} from "pages/api/auth/[...nextauth]";

export default async function NavbarInner() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <InitPostHog />
      <Menu>
        <div className="flex-1 h-full">
          <Search />
          <div className="pt-6 space-y-4">
            <AnalyseLinks />
            <ConfigureLinks session={session} />
            <LearnLinks />
          </div>
        </div>

        <UserInfo session={session} />
      </Menu>
      <MinimizeMenuButton />
    </>
  );
}
