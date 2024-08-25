'use client';
import React, { useState, useEffect } from 'react';
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
import { useSession } from "next-auth/react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useConfig } from "utils/hooks/useConfig";
import { AuthenticationType } from "utils/authenticationType";

import Loading from "app/loading";
import { EmptyStateTable } from "@/components/ui/EmptyStateTable";
import UsersTab from "./auth/users-tab";
import GroupsTab from "./auth/groups-tab";
import RolesTab from "./auth/roles-tab";
import APIKeysTab from "./auth/api-key-tab";
import SSOTab from "./auth/sso-tab";
import WebhookSettings from "./webhook-settings";
import SmtpSettings from "./smtp-settings";

import { UsersTable } from "./auth/users-table";
import { GroupsTable } from "./auth/groups-table";
import { RolesTable } from "./auth/roles-table";
import { SSOTable } from "./auth/sso-table";
import { APIKeysTable } from "./auth/api-key-table";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams()!;
  const pathname = usePathname();
  const { data: configData } = useConfig();

  const [selectedTab, setSelectedTab] = useState<string>(
    searchParams?.get("selectedTab") || "users"
  );
  const [selectedUserSubTab, setSelectedUserSubTab] = useState<string>(
    searchParams?.get("userSubTab") || "users"
  );
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [userSubTabIndex, setUserSubTabIndex] = useState<number>(0);

  const authType = configData?.AUTH_TYPE as AuthenticationType;
  const isNoAuth = authType === AuthenticationType.NO_AUTH;

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
        : 0;
    const userSubTabIndex =
      newUserSubTab === "users"
        ? 0
        : newUserSubTab === "groups"
        ? 1
        : newUserSubTab === "roles"
        ? 2
        : newUserSubTab === "api-keys"
        ? 3
        : newUserSubTab === "sso"
        ? 4
        : 0;
    setTabIndex(tabIndex);
    setUserSubTabIndex(userSubTabIndex);
    setSelectedTab(newSelectedTab);
    setSelectedUserSubTab(newUserSubTab);
  }, [searchParams]);

  const handleTabChange = (tab: string) => {
    router.replace(`${pathname}?selectedTab=${tab}`);
    setSelectedTab(tab);
  };

  const handleUserSubTabChange = (subTab: string) => {
    router.replace(`${pathname}?selectedTab=users&userSubTab=${subTab}`);
    setSelectedUserSubTab(subTab);
  };

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  const renderUserSubTabContent = (subTabName: string) => {
    if (isNoAuth) {
      switch (subTabName) {
        case "users":
          const mockUsers = [
            { email: "john@example.com", name: "John Doe", role: "Admin", groups: [{ name: "Admins" }], last_login: new Date().toISOString() },
            { email: "jane@example.com", name: "Jane Smith", role: "User", groups: [{ name: "Users" }], last_login: new Date().toISOString() },
          ];
          return (
            <EmptyStateTable
              subject="Users management"
              icon={UsersIcon}
              onClickDocumentation={() => console.log("View documentation clicked for Users management")}
            >
              <UsersTable users={mockUsers} currentUserEmail={session?.user?.email} authType={authType} isDisabled={true} />
            </EmptyStateTable>
          );
        case "groups":
          const mockGroups = [
            { id: "1", name: "Admins", members: ["john@example.com", "doe@example.com", "keep@example.com", "noc@example.com"], roles: ["Admin"] },
            { id: "2", name: "Operators", members: ["john@example.com", "doe@example.com", "keep@example.com", "noc@example.com"], roles: ["Operator"] },
            { id: "3", name: "NOC", members: ["jane@example.com"], roles: ["NOC"] },
            { id: "4", name: "Managers", members: ["boss1@example.com", "boss2@example.com"], roles: ["Viewer"] },
          ];
          return (
            <EmptyStateTable
              icon={UserGroupIcon}
              subject="Groups management"
              onClickDocumentation={() => console.log("View documentation clicked for Groups management")}
            >
              <GroupsTable groups={mockGroups} onRowClick={() => {}} onDeleteGroup={() => {}} isDisabled={true} />
            </EmptyStateTable>
          );
        case "roles":
          const mockRoles = [
            { id: "1", name: "Admin", description: "Full access", scopes: ["*"], predefined: true },
            { id: "2", name: "User", description: "Limited access", scopes: ["read:*"], predefined: false },
          ];
          return (
            <EmptyStateTable
              icon={ShieldCheckIcon}
              subject="Roles management"
              onClickDocumentation={() => console.log("View documentation clicked for Roles management")}
            >
              <RolesTable roles={mockRoles} onRowClick={() => {}} onDeleteRole={() => {}} isDisabled={true} />
            </EmptyStateTable>
          );
          case "api-keys":
            const mockApiKeys = [
              {
                reference_id: "AdminKey",
                secret: "sk_test_abcdefghijklmnopqrstuvwxyz123456",
                role: "Admin",
                created_by: "john@example.com",
                created_at: "2023-05-01T12:00:00Z",
                last_used: "2023-06-15T15:30:00Z"
              },
              {
                reference_id: "ViewerKey",
                secret: "sk_test_zyxwvutsrqponmlkjihgfedcba654321",
                role: "Viewer",
                created_by: "jane@example.com",
                created_at: "2023-06-01T09:00:00Z",
                last_used: "2023-06-20T10:45:00Z"
              },
            ];
            return (
              <EmptyStateTable
                icon={KeyIcon}
                subject="API Keys management"
                onClickDocumentation={() => console.log("View documentation clicked for API Keys management")}
              >
                <APIKeysTable
                  apiKeys={mockApiKeys}
                  onRegenerate={() => {}}
                  onDelete={() => {}}
                  isDisabled={true}
                />
              </EmptyStateTable>
            );
        case "sso":
          const mockSSOProviders = [
            { id: "1", name: "Google", connected: true },
            { id: "2", name: "Microsoft", connected: false },
          ];
          return (
            <EmptyStateTable
              icon={MdOutlineSecurity}
              subject="SSO management"
              onClickDocumentation={() => console.log("View documentation clicked for SSO management")}
            >
              <SSOTable providers={mockSSOProviders} onConnect={() => {}} onDisconnect={() => {}} isDisabled={true} />
            </EmptyStateTable>
          );
        default:
          return null;
      }
    }

    // If not NO_AUTH, render normal content
    switch (subTabName) {
      case "users":
        return <UsersTab accessToken={session?.accessToken!} currentUser={session?.user} selectedTab={selectedUserSubTab} />;
      case "groups":
        return <GroupsTab accessToken={session?.accessToken!} />;
      case "roles":
        return <RolesTab accessToken={session?.accessToken!} />;
      case "api-keys":
        return <APIKeysTab accessToken={session?.accessToken!} />;
      case "sso":
        return <SSOTab accessToken={session?.accessToken!} selectedTab={selectedUserSubTab} />;
      default:
        return null;
    }
  };

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
                <Tab icon={MdOutlineSecurity} onClick={() => handleUserSubTabChange("sso")}>
                  SSO
                </Tab>
              </TabList>
              <TabPanels className="flex-grow overflow-hidden">
                <TabPanel className="h-full mt-6">
                  {renderUserSubTabContent("users")}
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  {renderUserSubTabContent("groups")}
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  {renderUserSubTabContent("roles")}
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  {renderUserSubTabContent("api-keys")}
                </TabPanel>
                <TabPanel className="h-full mt-6">
                  {renderUserSubTabContent("sso")}
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
