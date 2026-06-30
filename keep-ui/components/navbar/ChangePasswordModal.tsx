"use client";

import { useState } from "react";
import { Button, TextInput, Subtitle, Callout } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { showSuccessToast } from "@/shared/ui";

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ChangePasswordModal = ({
  isOpen,
  onClose,
}: ChangePasswordModalProps) => {
  const api = useApi();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const resetForm = () => {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setError(null);
    setIsSubmitting(false);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentPassword) {
      setError("Current password is required");
      return;
    }
    if (!newPassword) {
      setError("New password is required");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match");
      return;
    }
    if (newPassword === currentPassword) {
      setError("New password must be different from the current password");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.put("/auth/users/me/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      showSuccessToast("Password changed successfully");
      handleClose();
    } catch (err) {
      if (err instanceof KeepApiError) {
        setError(err.message || "Failed to change password");
      } else {
        setError("An unexpected error occurred");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Change Password"
      className="w-[400px]"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <Subtitle>Current Password</Subtitle>
          <TextInput
            type="password"
            placeholder="Enter your current password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <div>
          <Subtitle>New Password</Subtitle>
          <TextInput
            type="password"
            placeholder="Enter a new password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        <div>
          <Subtitle>Confirm New Password</Subtitle>
          <TextInput
            type="password"
            placeholder="Re-enter the new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
        {error && (
          <Callout title="Error" color="rose">
            {error}
          </Callout>
        )}
        <div className="flex justify-end gap-2 mt-2">
          <Button
            type="button"
            variant="secondary"
            color="orange"
            className="border border-orange-500 text-orange-500"
            onClick={handleClose}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            color="orange"
            disabled={isSubmitting}
            loading={isSubmitting}
          >
            {isSubmitting ? "Saving..." : "Change Password"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
