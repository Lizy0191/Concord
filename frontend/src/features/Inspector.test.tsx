import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "../../tests/fixtures/inspector.json";
import { api, type Workspace } from "../api/client";
import { Inspector } from "./Inspector";

type Scalar = string | number | boolean | null;
const record = <T extends Scalar>(
  values: object,
  isValue: (value: unknown) => value is T,
): Record<string, T> =>
  Object.fromEntries(
    Object.entries(values).filter((entry): entry is [string, T] =>
      isValue(entry[1]),
    ),
  );
const booleanRecord = (values: object) =>
  record(values, (value): value is boolean => typeof value === "boolean");
const scalarRecord = (values: object) =>
  record(
    values,
    (value): value is Scalar =>
      value === null || ["string", "number", "boolean"].includes(typeof value),
  );
const waiting = {
  ...fixture.waiting,
  state: {
    ...fixture.waiting.state,
    work_packages: fixture.waiting.state.work_packages.map((workPackage) => ({
      ...workPackage,
      materials: booleanRecord(workPackage.materials),
      equipment: booleanRecord(workPackage.equipment),
    })),
  },
  audit: fixture.waiting.audit.map((entry) => ({
    ...entry,
    detail: scalarRecord(entry.detail),
  })),
} as Workspace;
const proposal = waiting.proposals.find(
  (item) => item.work_package_id === "WP-200",
)!;
const perform = async (operation: () => Promise<unknown>) => {
  await operation();
};
const props = { selected: "WP-200", selectedConstraint: "", perform };
const approved = { ...waiting, approvals: [fixture.approval] } as Workspace;

afterEach(() => vi.restoreAllMocks());

describe("evidence-backed action controls", () => {
  it("requires exact R4 confirmation and never offers unapproved execution", () => {
    render(<Inspector {...props} workspace={waiting} />);
    expect(
      screen.getByRole("button", { name: "Execute & re-check" }),
    ).toBeDisabled();
    const approve = screen.getByRole("button", { name: "Approve R4" });
    expect(approve).toBeDisabled();
    fireEvent.change(screen.getByLabelText("R4 confirmation"), {
      target: { value: "approve r4" },
    });
    expect(approve).toBeDisabled();
    fireEvent.change(screen.getByLabelText("R4 confirmation"), {
      target: { value: "APPROVE R4" },
    });
    expect(approve).toBeEnabled();
  });

  it("sends strong confirmation only for the selected proposal", () => {
    const request = vi
      .spyOn(api, "approve")
      .mockResolvedValue(fixture.approval as Workspace["approvals"][number]);
    render(<Inspector {...props} workspace={waiting} />);
    fireEvent.change(screen.getByLabelText("R4 confirmation"), {
      target: { value: "APPROVE R4" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve R4" }));
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith(proposal.id, true, "APPROVE R4");
  });

  it("clears typed consent when a new proposal replaces the old one", () => {
    const { rerender } = render(<Inspector {...props} workspace={waiting} />);
    fireEvent.change(screen.getByLabelText("R4 confirmation"), {
      target: { value: "APPROVE R4" },
    });
    const next = {
      ...waiting,
      proposals: waiting.proposals.map((item) => ({
        ...item,
        id: item.id + "-replacement",
      })),
    };
    rerender(<Inspector {...props} workspace={next} />);
    expect(screen.getByLabelText("R4 confirmation")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Approve R4" })).toBeDisabled();
  });

  it("allows execution only after approval", () => {
    const request = vi.spyOn(api, "execute").mockResolvedValue({
      run_id: proposal.run_id,
      operation_id: proposal.operation_id,
      queued: true,
    });
    render(<Inspector {...props} workspace={approved} />);
    expect(screen.getByRole("button", { name: "Approved" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Execute & re-check" }));
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith(proposal.id);
  });

  it.each([
    { stale: true, busy: false },
    { stale: false, busy: true },
  ])("prevents stale or overlapping mutations: %j", ({ stale, busy }) => {
    render(
      <Inspector {...props} workspace={{ ...approved, stale }} busy={busy} />,
    );
    expect(screen.getByRole("button", { name: "Approved" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Execute & re-check" }),
    ).toBeDisabled();
  });

  it("renders evidence as text rather than executing document markup", () => {
    const text = "<script>window.unsafe = true</script>";
    const workspace = structuredClone(waiting);
    workspace.analysis!.evidence.forEach((item) => {
      item.fact = text;
    });
    const { container } = render(
      <Inspector {...props} workspace={workspace} />,
    );
    expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    expect(container.querySelector("script")).toBeNull();
  });
});

it.each(["CANCELLED", "EXPIRED", "FAILED", "COMPLETED"] as const)(
  "cannot dispatch a proposal whose owning run is %s",
  (status) => {
    const owner = { ...approved.run!, status };
    render(
      <Inspector {...props} workspace={{ ...approved, analysis_run: owner }} />,
    );
    expect(
      screen.getByRole("button", { name: "Execute & re-check" }),
    ).toBeDisabled();
  },
);

it("uses the analysis owner rather than an unrelated completed upload", () => {
  render(
    <Inspector
      {...props}
      workspace={{
        ...approved,
        analysis_run: { ...approved.run!, status: "WAITING_APPROVAL" },
        run: {
          ...approved.run!,
          id: "upload-run",
          category: "document_parse",
          status: "COMPLETED",
        },
      }}
    />,
  );
  expect(
    screen.getByRole("button", { name: "Execute & re-check" }),
  ).toBeEnabled();
});
