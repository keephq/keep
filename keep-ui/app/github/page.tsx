"use client";
import Image from "next/image";

export const dynamic = "force-dynamic";

function InstallButton() {
  return (
    <div className="sticky rounded-2xl w-11/12 sm:w-[581px] h-40 sm:h-[80px] p-0.5 z-10 bottom-10 left-0 right-0 mx-auto">
      <div className="rounded-[14px] w-full h-full bg-gray-50 border border-gray-200 flex flex-col sm:flex-row items-center justify-center sm:justify-between space-y-3 sm:space-y-0 px-5">
        <p className="text-black text-[13px] font-mono w-[304px] h-10 flex items-center justify-center p-3">
          To start with Keep, first install GitHub Bot.
        </p>
        <a
          className="text-white text-[13px] font-mono bg-blue-500 hover:bg-blue-700 transition-all rounded-md w-[220px] h-10 flex items-center justify-center whitespace-nowrap"
          href="https://github.com/apps/keephq/installations/new"
          target="_blank"
          rel="noreferrer"
        >
          Start Installation
          <Image
            src="/keep.svg"
            alt="Keep"
            width={24}
            height={24}
            className="inline-block ml-2"
          />
        </a>
      </div>
    </div>
  );
}

export default function GitHubPage() {
  return (
    <main className="flex flex-col items-center justify-center h-screen pb-20">
      <InstallButton />
    </main>
  );
}
