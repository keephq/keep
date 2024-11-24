"use client";

import * as Frigade from "@frigade/react";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
export const FrigadeProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const { data: session } = useSession();
  return (
    <Frigade.Provider
      apiKey="api_public_6BKR7bUv0YZ5dqnjLGeHpRWCHaDWeb5cVobG3A9YkW0gOgafOEBvtJGZgvhp8PGb"
      userId={
        session?.user.email === "keep"
          ? undefined
          : (session?.user.email ?? session?.user.name)
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
