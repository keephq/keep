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
import { KeepLogo } from "@/components/navbar/KeepLogo";
import "./Navbar.css";

export default async function NavbarInner() {
  const session = await auth();
  return (
    <div className="flex h-full relative">
      <Menu session={session}>
        <div className="flex flex-col h-full overflow-hidden">
          {/* Logo section with tenant switcher */}
          <div className="sidebar-logo-section flex justify-center py-3">
            <KeepLogo session={session} />
          </div>

          {/* Search section styled like Datadog */}
          <div className="sidebar-search-section px-3 mb-4">
            <Search session={session} />
          </div>

          {/* Main navigation links */}
          <div className="flex-1 overflow-auto scrollable-menu-shadow">
            <div className="px-2 py-1 space-y-6">
              <IncidentsLinks session={session} />
              <AlertsLinks session={session} />
              <NoiseReductionLinks session={session} />
              <DashboardLinks />
            </div>
          </div>

          {/* User info footer */}
          <div className="sidebar-footer border-t border-gray-300 dark:border-gray-700 mt-auto">
            <UserInfo session={session} />
          </div>
        </div>
      </Menu>

      {/* Position the minimize button directly adjacent to the menu */}
      <div className="minimize-button-container">
        <MinimizeMenuButton />
      </div>

      <SetSentryUser session={session} />
    </div>
  );
}
