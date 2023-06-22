"use client";

import { Command } from 'cmdk'
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GitHubLogoIcon, FileTextIcon, TwitterLogoIcon } from '@radix-ui/react-icons'

import '../styles/linear.scss';


export function CMDK() {
 const [open, setOpen] = useState(false)
 const router = useRouter();

  // Toggle the menu when ⌘K is pressed
  useEffect(() => {
    const down = (e: any) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((open) => !open)
      }
    }

    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [])
  return (
    <div className="linear">
      <Command.Dialog open={open} onOpenChange={setOpen}>
        <div cmdk-linear-badge="">Keep Command Palette</div>
        <Command.Input autoFocus placeholder="Type a command or search..." />
        <Command.Group heading="Navigate">
            <Command.List>
            <Command.Empty>No results found.</Command.Empty>
            {navigationItems.map(({ icon, label, shortcut, navigate }) => {
                return (
                    <Command.Item key={label} value={label} onSelect={() => {
                        setOpen((open) => !open);
                        router.push(navigate!);
                    }}>
                    {icon}
                    {label}
                    <div cmdk-linear-shortcuts="">
                    {shortcut.map((key) => {
                        return <kbd key={key}>{key}</kbd>
                    })}
                    </div>
                </Command.Item>
                )
            })}
            </Command.List>
        </Command.Group>
        <Command.Group heading="External sources">
            <Command.List>
            {externalItems.map(({ icon, label, shortcut, navigate }) => {
                return (
                    <Command.Item key={label} value={label} onSelect={() => {
                        setOpen((open) => !open);
                        window.open(navigate, "_blank");
                    }}>
                    {icon}
                    {label}
                    <div cmdk-linear-shortcuts="">
                    {shortcut.map((key) => {
                        return <kbd key={key}>{key}</kbd>
                    })}
                    </div>
                </Command.Item>
                )
            })}
            </Command.List>
        </Command.Group>
      </Command.Dialog>
    </div>
  )
}

const navigationItems = [
  {
    icon: <GoToConsoleIcon />,
    label: 'Go to alert console',
    shortcut: ['G'],
    navigate: '/alerts'
  },
  {
    icon: <ConnectIntegrationIcon />,
    label: 'Go to the providers page',
    shortcut: ['P'],
    navigate: '/providers'
  },
  {
    icon: <GoToDashboardIcon />,
    label: 'Go to dashboard',
    shortcut: ['D'],
    navigate: '/dashboard'
  }
]

const externalItems = [
        {
        icon: <FileTextIcon />,
        label: 'Keep Docs',
        shortcut: ['⇧', 'D'],
        navigate: 'https://docs.keephq.dev'
      },
      {
        icon: <GitHubLogoIcon />,
        label: 'Keep Source code',
        shortcut: ['⇧', 'C'],
        navigate: 'https://github.com/keephq/keep'
      },
      {
        icon: <TwitterLogoIcon />,
        label: 'Keep Twitter',
        shortcut: ['⇧', 'T'],
        navigate: 'https://twitter.com/keepalerting'
      }
]

function ConnectIntegrationIcon() {
  return (
    <svg fill="#000000" width="800px" height="800px" viewBox="0 0 1920 1920" xmlns="http://www.w3.org/2000/svg">
    <path d="M1581.235 734.118c0 217.976-177.317 395.294-395.294 395.294H960.06c-217.977 0-395.294-177.318-395.294-395.294V564.706h1016.47v169.412Zm225.883-282.353h-338.824V0h-112.941v451.765H790.647V0H677.706v451.765H338.882v112.94h112.942v169.413c0 280.207 228.028 508.235 508.235 508.235h56.47v395.294c0 93.402-76.009 169.412-169.411 169.412-93.403 0-169.412-76.01-169.412-169.412 0-155.633-126.72-282.353-282.353-282.353S113 1482.014 113 1637.647V1920h112.941v-282.353c0-93.402 76.01-169.412 169.412-169.412s169.412 76.01 169.412 169.412c0 155.633 126.72 282.353 282.353 282.353 155.746 0 282.353-126.72 282.353-282.353v-395.294h56.47c280.207 0 508.235-228.028 508.235-508.235V564.706h112.942V451.765Z" fill-rule="evenodd"/>
</svg>
  )
}

function GoToConsoleIcon() {
  return (
    <svg width="800px" height="800px" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M5 6l2.702 2.5L5 11zm0 12l2.702-2.5L5 13zm5-9h10V8H10zm0 7h7v-1h-7zM1 3h22v18H1zm1 17h20V4H2z"/><path fill="none" d="M0 0h24v24H0z"/></svg>
  )
}

function CreateAlertIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="#000000" width="800px" height="800px" viewBox="0 0 24 24"><path d="M10.01 21.01c0 1.1.89 1.99 1.99 1.99s1.99-.89 1.99-1.99h-3.98zm8.87-4.19V11c0-3.25-2.25-5.97-5.29-6.69v-.72C13.59 2.71 12.88 2 12 2s-1.59.71-1.59 1.59v.72C7.37 5.03 5.12 7.75 5.12 11v5.82L3 18.94V20h18v-1.06l-2.12-2.12zM16 13.01h-3v3h-2v-3H8V11h3V8h2v3h3v2.01z"/></svg>
  )
}

function GoToDashboardIcon() {
  return (
    <svg fill="#000000" width="800px" height="800px" viewBox="0 0 1920 1920" xmlns="http://www.w3.org/2000/svg">
     <path d="M833.935 1063.327c28.913 170.315 64.038 348.198 83.464 384.79 27.557 51.84 92.047 71.944 144 44.387 51.84-27.558 71.717-92.273 44.16-144.113-19.426-36.593-146.937-165.46-271.624-285.064Zm-43.821-196.405c61.553 56.923 370.899 344.81 415.285 428.612 56.696 106.842 15.811 239.887-91.144 296.697-32.64 17.28-67.765 25.411-102.325 25.411-78.72 0-154.955-42.353-194.371-116.555-44.386-83.802-109.102-501.346-121.638-584.245-3.501-23.717 8.245-47.21 29.365-58.277 21.346-11.294 47.096-8.02 64.828 8.357ZM960.045 281.99c529.355 0 960 430.757 960 960 0 77.139-8.922 153.148-26.654 225.882l-10.39 43.144h-524.386v-112.942h434.258c9.487-50.71 14.231-103.115 14.231-156.084 0-467.125-380.047-847.06-847.059-847.06-467.125 0-847.059 379.935-847.059 847.06 0 52.97 4.744 105.374 14.118 156.084h487.454v112.942H36.977l-10.39-43.144C8.966 1395.137.044 1319.128.044 1241.99c0-529.243 430.645-960 960-960Zm542.547 390.686 79.85 79.85-112.716 112.715-79.85-79.85 112.716-112.715Zm-1085.184 0L530.123 785.39l-79.85 79.85L337.56 752.524l79.849-79.85Zm599.063-201.363v159.473H903.529V471.312h112.942Z" fill-rule="evenodd"/>
    </svg>
  )
}
