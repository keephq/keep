"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon,
  UsersIcon,
  UserIcon,
  ShieldCheckIcon,
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
        : newUserSubTab === "api-keys"
        ? 1
        : newUserSubTab === "groups"
        ? 2
        : newUserSubTab === "roles"
        ? 3
        : 4;
    setTabIndex(tabIndex);
    setUserSubTabIndex(userSubTabIndex);
    setSelectedTab(newSelectedTab);
    setSelectedUserSubTab(newUserSubTab);
  }, [searchParams]);

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  return (
    <TabGroup index={tabIndex}>
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
      <TabPanels>
        <TabPanel>
          <TabGroup index={userSubTabIndex}>
            <TabList color="orange">
              <Tab icon={UsersIcon} onClick={() => handleUserSubTabChange("users")}>
                Users
              </Tab>
              <Tab icon={KeyIcon} onClick={() => handleUserSubTabChange("api-keys")}>
                API Keys
              </Tab>
              <Tab icon={UserGroupIcon} onClick={() => handleUserSubTabChange("groups")}>
                Groups
              </Tab>
              <Tab icon={ShieldCheckIcon} onClick={() => handleUserSubTabChange("roles")}>
                Roles
              </Tab>
              <Tab icon={MdOutlineSecurity} onClick={() => handleUserSubTabChange("sso")}>
                SSO
              </Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <UsersTab accessToken={session?.accessToken!} currentUser={session?.user} />
              </TabPanel>
              <TabPanel>
                <APIKeysTab accessToken={session?.accessToken!} />
              </TabPanel>
              <TabPanel>
                <GroupsTab accessToken={session?.accessToken!} />
              </TabPanel>
              <TabPanel>
                <RolesTab accessToken={session?.accessToken!} />
              </TabPanel>
              <TabPanel>
                <SSOTab accessToken={session?.accessToken!} />
              </TabPanel>
            </TabPanels>
          </TabGroup>
        </TabPanel>
        <TabPanel>
          <WebhookSettings
            accessToken={session?.accessToken!}
            selectedTab={selectedTab}
          />
        </TabPanel>
        <TabPanel>
          <SmtpSettings
            accessToken={session?.accessToken!}
            selectedTab={selectedTab}
          />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
