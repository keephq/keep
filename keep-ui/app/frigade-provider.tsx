"use client";

import * as Frigade from "@frigade/react";
import { useSession } from "next-auth/react";
export const FrigadeProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const { data: session } = useSession();
  return (
    <Frigade.Provider
      apiKey={process.env.NEXT_PUBLIC_FRIGADE_KEY!}
      userId={
        session?.user.email === "keep"
          ? undefined
          : session?.user.email ?? session?.user.name
      }
      theme={{
        colors: {
          primary: {
            surface: "rgb(249 115 22)",
            border: "rgb(249 115 22)",
            hover: { surface: "rgb(234 88 12)" },
          },
        },
      }}
    >
      {children}
    </Frigade.Provider>
  );
};
