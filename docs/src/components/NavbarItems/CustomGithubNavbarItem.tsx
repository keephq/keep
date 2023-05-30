import React from "react";
import GitHubButton from "react-github-btn";

export default function CustomGithubNavbarItem(props: {
  repository: string;
}): JSX.Element | null {
  return (
    <div >
      <GitHubButton
        href="https://github.com/keephq/keep"
        data-color-scheme="no-preference: dark; light: dark_dimmed; dark: dark;"
        data-size="large"
        data-show-count="true"
        aria-label="Star keephq/keep on GitHub"
      >
        Star
      </GitHubButton>
    </div>
  );
}
