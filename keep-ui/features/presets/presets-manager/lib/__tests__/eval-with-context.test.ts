import { AlertDto } from "@/entities/alerts/model";
import { evalWithContext } from "../eval-with-context";

// sanitizeCELIntoJS rewrites the CEL `contains` operator to JS `includes`
// before the expression is evaluated. It used to do so with an unanchored
// /contains/g, which also rewrote the inside of quoted search strings and any
// identifier that merely contained those letters. Nothing threw: the preset
// saved and filtered, just against something the user never typed.
const alert = {
  id: "1",
  name: "test",
  description: "this contains errors",
  severity: "critical",
  status: "firing",
  source: ["prometheus"],
} as unknown as AlertDto;

describe("evalWithContext - contains", () => {
  it("matches on a plain substring", () => {
    expect(evalWithContext(alert, 'description.contains("errors")')).toBe(true);
  });

  it("does not match a substring that is absent", () => {
    expect(evalWithContext(alert, 'description.contains("timeout")')).toBe(
      false
    );
  });

  // The search term is the operator's own name. Rewriting the operator must
  // not rewrite what the user is searching for.
  it("searches for the literal word 'contains'", () => {
    expect(evalWithContext(alert, 'description.contains("contains")')).toBe(
      true
    );
  });

  it("does not match 'includes' when the user searched for 'contains'", () => {
    const other = { ...alert, description: "this includes errors" } as AlertDto;
    expect(evalWithContext(other, 'description.contains("contains")')).toBe(
      false
    );
  });

  it("keeps the search term intact inside a longer phrase", () => {
    expect(
      evalWithContext(alert, 'description.contains("this contains errors")')
    ).toBe(true);
  });

  it("still rewrites several contains calls in one expression", () => {
    expect(
      evalWithContext(
        alert,
        'description.contains("this") && description.contains("errors")'
      )
    ).toBe(true);
  });
});

describe("evalWithContext - identifiers holding the operator name", () => {
  // A field whose name merely contains those letters was renamed to one that
  // does not exist, so the comparison silently evaluated against undefined.
  const labelled = {
    ...alert,
    contains_pii: "true",
  } as unknown as AlertDto;

  it("does not rename a field whose name starts with the operator name", () => {
    expect(evalWithContext(labelled, 'contains_pii == "true"')).toBe(true);
  });

  it("reports a genuine mismatch on such a field", () => {
    expect(evalWithContext(labelled, 'contains_pii == "false"')).toBe(false);
  });
});
