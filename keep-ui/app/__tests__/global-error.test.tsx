import { fireEvent, render, screen } from "@testing-library/react";
import * as Sentry from "@sentry/nextjs";
import GlobalError from "../global-error";

jest.unmock("next-auth/react");
jest.unmock("@/shared/lib/hooks/useApi");
jest.unmock("@/utils/hooks/useConfig");
jest.mock("@sentry/nextjs", () => ({ captureException: jest.fn() }));

it("renders the original error and retries without layout providers", () => {
  const error = Object.assign(new Error("Unable to load the session"), {
    digest: "error-reference",
  });
  const reset = jest.fn();

  render(<GlobalError error={error} reset={reset} />, { container: document });

  expect(screen.getByText(error.message)).toBeInTheDocument();
  expect(screen.getByText("Error reference: error-reference")).toBeInTheDocument();
  expect(Sentry.captureException).toHaveBeenCalledWith(error);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(reset).toHaveBeenCalledTimes(1);
});
