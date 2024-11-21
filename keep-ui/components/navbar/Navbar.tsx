import { auth } from "@/auth";
import { Search } from "@/components/navbar/Search";
import { NoiseReductionLinks } from "@/components/navbar/NoiseReductionLinks";
import { AlertsLinks } from "@/components/navbar/AlertsLinks";
import { UserInfo } from "@/components/navbar/UserInfo";
import { Menu } from "@/components/navbar/Menu";
import { MinimizeMenuButton } from "@/components/navbar/MinimizeMenuButton";
import { DashboardLinks } from "@/components/navbar/DashboardLinks";
import { IncidentsLinks } from "@/components/navbar/IncidentLinks";
import { SetSentryUser } from "./SetSentryUser";
import "./Navbar.css";

export default async function NavbarInner() {
  const session = await auth();
  return (
    <>
      <Menu>
        <Search />
        <div className="pt-6 space-y-4 flex-1 overflow-auto scrollable-menu-shadow">
          <IncidentsLinks session={session} />
          <AlertsLinks session={session} />
          <NoiseReductionLinks session={session} />
          <DashboardLinks session={session} />
        </div>
        <UserInfo session={session} />
      </Menu>
      <MinimizeMenuButton />
      <SetSentryUser session={session} />
    </>
  );
}
