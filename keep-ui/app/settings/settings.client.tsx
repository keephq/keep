"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon,
  UsersIcon,
  ShieldCheckIcon,
  LockClosedIcon,
} from "@heroicons/react/24/outline";
import { MdOutlineSecurity } from "react-icons/md";
import WebhookSettings from "./webhook-settings";
import { useSession } from "next-auth/react";
import Loading from "app/loading";
import SmtpSettings from "./smtp-settings";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import UsersTab from "./auth/users-tab";
import GroupsTab from "./auth/groups-tab";
import RolesTab from "./auth/roles-tab";
import APIKeysTab from "./auth//api-key-tab";
import SSOTab from "./auth/sso-tab";
import PermissionsTab from "./auth/permissions-tab";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams()!;
  const pathname = usePathname();
  const [selectedTab, setSelectedTab] = useState<string>(
    searchParams?.get("selectedTab") || "users"
  );
  const [selectedUserSubTab, setSelectedUserSubTab] = useState<string>(
    searchParams?.get("userSubTab") || "users"
  );
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [userSubTabIndex, setUserSubTabIndex] = useState<number>(0);

  const handleTabChange = useCallback(
    (tab: string) => {
      if (tab !== selectedTab) {
        router.replace(`${pathname}?selectedTab=${tab}`);
        setSelectedTab(tab);
      }
    },
    [pathname, router, selectedTab]
  );

  const handleUserSubTabChange = useCallback(
    (subTab: string) => {
      if (subTab !== selectedUserSubTab) {
        router.replace(`${pathname}?selectedTab=users&userSubTab=${subTab}`);
        setSelectedUserSubTab(subTab);
      }
    },
    [pathname, router, selectedUserSubTab]
  );

  useEffect(() => {
    const newSelectedTab = searchParams?.get("selectedTab") || "users";
    const newUserSubTab = searchParams?.get("userSubTab") || "users";
    const tabIndex =
      newSelectedTab === "users"
        ? 0
        : newSelectedTab === "webhook"
        ? 1
        : newSelectedTab === "smtp"
        ? 2
        : 3;
    const userSubTabIndex =
      newUserSubTab === "users"
        ? 0
        : newUserSubTab === "groups"
        ? 1
        : newUserSubTab === "roles"
        ? 2
        : newUserSubTab === "api-keys"
        ? 3
        // : newUserSubTab === "permissions"
        // ? 4
        : 4;
    setTabIndex(tabIndex);
    setUserSubTabIndex(userSubTabIndex);
    setSelectedTab(newSelectedTab);
    setSelectedUserSubTab(newUserSubTab);
  }, [searchParams]);

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  return (
    <div className="flex flex-col h-full">
      <TabGroup index={tabIndex} className="flex-grow flex flex-col">
        <TabList color="orange">
          <Tab icon={UserGroupIcon} onClick={() => handleTabChange("users")}>
            Users and Access
          </Tab>
          <Tab icon={GlobeAltIcon} onClick={() => handleTabChange("webhook")}>
            Webhook
          </Tab>
          <Tab icon={EnvelopeIcon} onClick={() => handleTabChange("smtp")}>
            SMTP
          </Tab>
        </TabList>
        <TabPanels className="flex-grow overflow-hidden">
          <TabPanel className="h-full">
            <TabGroup index={userSubTabIndex} className="h-full flex flex-col">
              <TabList color="orange">
                <Tab icon={UsersIcon} onClick={() => handleUserSubTabChange("users")}>
                  Users
                </Tab>
                <Tab icon={UserGroupIcon} onClick={() => handleUserSubTabChange("groups")}>
                  Groups
                </Tab>
                <Tab icon={ShieldCheckIcon} onClick={() => handleUserSubTabChange("roles")}>
                  Roles
                </Tab>
                <Tab icon={KeyIcon} onClick={() => handleUserSubTabChange("api-keys")}>
                  API Keys
                </Tab>
                {/* <Tab icon={LockClosedIcon} onClick={() => handleUserSubTabChange("permissions")}>
                  Permissions
                </Tab> */}
                <Tab icon={MdOutlineSecurity} onClick={() => handleUserSubTabChange("sso")}>
                  SSO
                </Tab>
              </TabList>
              <TabPanels className="flex-grow overflow-hidden">
                <TabPanel className="h-full mt-6">
                  <UsersTab accessToken={session?.accessToken!} currentUser={session?.user} />
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  <GroupsTab accessToken={session?.accessToken!} />
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  <RolesTab accessToken={session?.accessToken!} />
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  <APIKeysTab accessToken={session?.accessToken!} />
                </TabPanel>
                {/* <TabPanel className="h-full mt-6">
                  <PermissionsTab accessToken={session?.accessToken!} />
                </TabPanel> */}
                <TabPanel className="h-full mt-6">
                  <SSOTab accessToken={session?.accessToken!} />
                </TabPanel>
              </TabPanels>
            </TabGroup>
          </TabPanel>
          <TabPanel className="h-full">
            <WebhookSettings
              accessToken={session?.accessToken!}
              selectedTab={selectedTab}
            />
          </TabPanel>
          <TabPanel className="h-full">
            <SmtpSettings
              accessToken={session?.accessToken!}
              selectedTab={selectedTab}
            />
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
}
