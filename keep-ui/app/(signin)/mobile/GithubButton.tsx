// GithubButton.tsx - Client Component
"use client";

import { Button } from "@tremor/react";
import { Github } from "lucide-react";

export function GithubButton() {
  return (
    <Button
      icon={Github}
      size="lg"
      className="mt-4"
      onClick={() => window.open("https://github.com/keephq/keep", "_blank")}
    >
      Star us on GitHub
    </Button>
  );
}
