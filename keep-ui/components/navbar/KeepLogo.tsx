"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Popover, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { signIn } from "next-auth/react";
import { Session } from "next-auth";
import KeepPng from "../../keeplogobw.png";

interface KeepLogoProps {
  session?: Session | null;
}

export const KeepLogo = ({ session }: KeepLogoProps) => {
  const [isLoading, setIsLoading] = useState(false);

  // Check if tenant switching is available
  const hasTenantSwitcher =
    session &&
    session.user &&
    session.user.tenantIds &&
    session.user.tenantIds.length > 1;

  // Get current tenant logo URL if available
  const currentTenant = session?.user?.tenantIds?.find(
    (tenant) => tenant.tenant_id === session.tenantId
  );
  const tenantLogoUrl = currentTenant?.tenant_logo_url;
  const hasTenantLogo = Boolean(tenantLogoUrl);

  // Tenant switcher function
  const switchTenant = async (tenantId: string) => {
    setIsLoading(true);
    try {
      // Use the tenant-switch provider to change tenants
      let sessionAsJson = JSON.stringify(session);
      const result = await signIn("tenant-switch", {
        redirect: false,
        tenantId,
        sessionAsJson,
      });

      if (result?.error) {
        console.error("Error switching tenant:", result.error);
      } else {
        // new tenant, let's reload the page
        window.location.reload();
      }
    } catch (error) {
      console.error("Error switching tenant:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // If no tenant switching available, just return the logo with a link
  if (!hasTenantSwitcher) {
    return (
      <Link href="/" className="flex items-center">
        <div className="bg-gray-100 dark:bg-gray-800 rounded-md p-2 shadow-sm flex justify-center items-center w-24 h-24">
          <Image
            src={KeepPng}
            alt="Keep Logo"
            width={64}
            height={64}
            className="object-contain"
          />
        </div>
        {hasTenantLogo && (
          <Image
            src={tenantLogoUrl || ""}
            alt={`${currentTenant?.tenant_name || "Tenant"} Logo`}
            width={60}
            height={60}
            className="ml-4 object-cover"
          />
        )}
      </Link>
    );
  }

  // If tenant switching is available, use a popover for the switcher
  return (
    <Popover className="relative">
      {({ open }) => (
        <>
          <Popover.Button
            className="focus:outline-none flex items-center"
            disabled={isLoading}
          >
            <div className="bg-gray-100 dark:bg-gray-800 rounded-md p-2 shadow-sm flex justify-center items-center w-10 h-10">
              <Image
                src={KeepPng}
                alt="Keep Logo"
                width={32}
                height={32}
                className="object-contain"
              />
            </div>
            {hasTenantLogo && (
              <Image
                src={tenantLogoUrl || ""}
                alt={`${currentTenant?.tenant_name || "Tenant"} Logo`}
                width={60}
                height={60}
                className="ml-4 object-cover"
              />
            )}
          </Popover.Button>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-200"
            enterFrom="opacity-0 translate-y-1"
            enterTo="opacity-100 translate-y-0"
            leave="transition ease-in duration-150"
            leaveFrom="opacity-100 translate-y-0"
            leaveTo="opacity-0 translate-y-1"
          >
            <Popover.Panel className="absolute z-10 mt-1 w-48 rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1 divide-y divide-gray-200 dark:divide-gray-700">
                <div className="px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                  Switch Tenant
                </div>
                {session.user.tenantIds?.map((tenant) => (
                  <button
                    key={tenant.tenant_id}
                    className={`block w-full text-left px-4 py-2 text-sm ${
                      tenant.tenant_id === session.tenantId
                        ? "bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300 font-medium"
                        : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    }`}
                    onClick={() => switchTenant(tenant.tenant_id)}
                    disabled={
                      tenant.tenant_id === session.tenantId || isLoading
                    }
                  >
                    {tenant.tenant_name}
                  </button>
                ))}
              </div>
            </Popover.Panel>
          </Transition>
        </>
      )}
    </Popover>
  );
};
