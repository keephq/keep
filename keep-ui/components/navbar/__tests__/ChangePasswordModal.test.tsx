import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChangePasswordModal } from "../ChangePasswordModal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showSuccessToast } from "@/shared/ui";
import { KeepApiError } from "@/shared/api";

jest.mock("@/shared/lib/hooks/useApi");
jest.mock("@/shared/ui", () => ({
  showSuccessToast: jest.fn(),
}));

describe("ChangePasswordModal", () => {
  const mockPut = jest.fn();
  const mockOnClose = jest.fn();

  beforeEach(() => {
    (useApi as jest.Mock).mockReturnValue({ put: mockPut });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  const fillForm = (current: string, next: string, confirm: string) => {
    fireEvent.change(
      screen.getByPlaceholderText("Enter your current password"),
      { target: { value: current } }
    );
    fireEvent.change(screen.getByPlaceholderText("Enter a new password"), {
      target: { value: next },
    });
    fireEvent.change(screen.getByPlaceholderText("Re-enter the new password"), {
      target: { value: confirm },
    });
  };

  it("submits the password change and closes on success", async () => {
    mockPut.mockResolvedValue({ status: "OK" });
    render(<ChangePasswordModal isOpen={true} onClose={mockOnClose} />);

    fillForm("oldpass", "newpass", "newpass");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() => {
      expect(mockPut).toHaveBeenCalledWith("/auth/users/me/password", {
        current_password: "oldpass",
        new_password: "newpass",
      });
    });
    expect(showSuccessToast).toHaveBeenCalledWith(
      "Password changed successfully"
    );
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("shows an error when passwords do not match", async () => {
    render(<ChangePasswordModal isOpen={true} onClose={mockOnClose} />);

    fillForm("oldpass", "newpass", "different");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("New password and confirmation do not match")
      ).toBeInTheDocument();
    });
    expect(mockPut).not.toHaveBeenCalled();
  });

  it("shows an error when the new password equals the current one", async () => {
    render(<ChangePasswordModal isOpen={true} onClose={mockOnClose} />);

    fillForm("samepass", "samepass", "samepass");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "New password must be different from the current password"
        )
      ).toBeInTheDocument();
    });
    expect(mockPut).not.toHaveBeenCalled();
  });

  it("surfaces the API error message on failure", async () => {
    mockPut.mockRejectedValue(
      new KeepApiError(
        "Current password is incorrect",
        "/auth/users/me/password",
        "Current password is incorrect",
        undefined,
        403
      )
    );
    render(<ChangePasswordModal isOpen={true} onClose={mockOnClose} />);

    fillForm("wrongpass", "newpass", "newpass");
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Current password is incorrect")
      ).toBeInTheDocument();
    });
    expect(mockOnClose).not.toHaveBeenCalled();
  });
});
