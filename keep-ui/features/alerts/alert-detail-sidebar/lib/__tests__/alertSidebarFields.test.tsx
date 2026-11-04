import React from "react";
import { render, screen } from "@testing-library/react";
import { AlertDto } from "@/entities/alerts/model";
import {
  alertSidebarFieldsConfig,
  getCustomFields,
  getEnabledFields,
} from "../alertSidebarFields";

// FormattedContent pulls in react-markdown, which ships ESM only.
jest.mock("@/shared/ui/FormattedContent/FormattedContent", () => ({
  FormattedContent: () => null,
}));

const makeAlert = (labels?: AlertDto["labels"]) =>
  ({
    fingerprint: "3d503d92ea9f4c0c",
    name: "Backup Job History (Backup & Replication) (Warning)",
    source: ["grafana"],
    labels,
  }) as AlertDto;

describe("alert sidebar labels field", () => {
  it("is a built-in sidebar field rather than a custom field path", () => {
    expect(getEnabledFields(["service", "labels"])).toEqual([
      "service",
      "labels",
    ]);
    expect(getCustomFields(["labels", "labels.JobName"])).toEqual([
      "labels.JobName",
    ]);
  });

  it("renders each label as a key=value badge", () => {
    const alert = makeAlert({
      JobName: "Cluster nach Qnap2",
      customer: "senst",
      priority: 2,
    });

    expect(alertSidebarFieldsConfig.labels.shouldRender(alert)).toBe(true);
    render(<>{alertSidebarFieldsConfig.labels.render({ alert })}</>);

    expect(screen.getByText("Labels")).toBeInTheDocument();
    expect(screen.getByText("JobName=Cluster nach Qnap2")).toBeInTheDocument();
    expect(screen.getByText("customer=senst")).toBeInTheDocument();
    expect(screen.getByText("priority=2")).toBeInTheDocument();
  });

  it("is not rendered when the alert has no labels", () => {
    expect(alertSidebarFieldsConfig.labels.shouldRender(makeAlert())).toBe(
      false
    );
    expect(alertSidebarFieldsConfig.labels.shouldRender(makeAlert(null))).toBe(
      false
    );
    expect(alertSidebarFieldsConfig.labels.shouldRender(makeAlert({}))).toBe(
      false
    );
  });
});
