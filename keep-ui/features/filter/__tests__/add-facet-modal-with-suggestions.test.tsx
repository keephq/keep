import { render, screen, fireEvent } from "@testing-library/react";
import { AddFacetModalWithSuggestions } from "../add-facet-modal-with-suggestions";
import { useFacetPotentialFields } from "../hooks";

jest.mock("../hooks");
jest.mock("@/app/(keep)/loading", () => ({
  __esModule: true,
  default: () => null,
}));

describe("AddFacetModalWithSuggestions", () => {
  beforeEach(() => {
    (useFacetPotentialFields as jest.Mock).mockReturnValue({
      data: ["Application", "severity"],
    });
    render(
      <AddFacetModalWithSuggestions
        entityName="alert"
        isOpen={true}
        onClose={jest.fn()}
        onAddFacet={jest.fn()}
      />
    );
  });

  const search = (value: string) =>
    fireEvent.change(screen.getByPlaceholderText("Search columns..."), {
      target: { value },
    });

  it("lists every suggestion when the search is empty", () => {
    expect(
      screen.getByRole("button", { name: "Application" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "severity" })
    ).toBeInTheDocument();
  });

  it("matches a lowercase search against an uppercase property path", () => {
    search("application");

    expect(
      screen.getByRole("button", { name: "Application" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "severity" })
    ).not.toBeInTheDocument();
  });

  it("matches an uppercase search against a lowercase property path", () => {
    search("SEVERITY");

    expect(
      screen.getByRole("button", { name: "severity" })
    ).toBeInTheDocument();
  });

  it("shows no suggestions when nothing matches", () => {
    search("zzz");

    expect(
      screen.queryByRole("button", { name: "Application" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "severity" })
    ).not.toBeInTheDocument();
  });
});
