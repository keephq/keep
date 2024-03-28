import { getServerSession } from "next-auth";
import { Search } from "components/navbar/Search";
import { NoiseReductionLinks } from "components/navbar/NoiseReductionLinks";
import { AlertsLinks } from "components/navbar/AlertsLinks";
import { UserInfo } from "components/navbar/UserInfo";
import { InitPostHog } from "components/navbar/InitPostHog";
import { Menu } from "components/navbar/Menu";
import { MinimizeMenuButton } from "components/navbar/MinimizeMenuButton";
import { authOptions } from "pages/api/auth/[...nextauth]";

export default async function NavbarInner() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <InitPostHog />
      <Menu>
        <Search />
        <div className="pt-6 space-y-4 flex-1 overflow-auto">
          <AlertsLinks session={session} />
          <NoiseReductionLinks session={session} />
        </div>
        <UserInfo session={session} />
      </Menu>
      <MinimizeMenuButton />
    </>
  );
}
