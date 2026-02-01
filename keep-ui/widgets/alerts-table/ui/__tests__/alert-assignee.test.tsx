import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AlertAssignee from "../alert-assignee";
import { useUsers } from "@/entities/users/model/useUsers";
import { User } from "@/app/(keep)/settings/models";

// Mock the useUsers hook
jest.mock("@/entities/users/model/useUsers");

// Mock the NameInitialsAvatar component
jest.mock("react-name-initials-avatar", () => ({
  NameInitialsAvatar: ({ name, bgColor, textColor, size }: any) => (
    <div
      data-testid="name-initials-avatar"
      data-name={name}
      data-bg-color={bgColor}
      data-text-color={textColor}
      data-size={size}
    >
      {name}
    </div>
  ),
}));

const mockUseUsers = useUsers as jest.MockedFunction<typeof useUsers>;

describe("AlertAssignee", () => {
  const createMockUser = (overrides: Partial<User> = {}): User => ({
    name: "John Doe",
    email: "john.doe@example.com",
    role: "admin",
    picture: "https://example.com/avatar.jpg",
    created_at: "2023-01-01T00:00:00Z",
    last_login: "2023-12-01T00:00:00Z",
    ldap: false,
    groups: [],
    ...overrides,
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should return null when no assignee is provided", () => {
    mockUseUsers.mockReturnValue({
      data: [],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    const { container } = render(<AlertAssignee assignee={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("should return null when assignee is empty string", () => {
    mockUseUsers.mockReturnValue({
      data: [],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    const { container } = render(<AlertAssignee assignee="" />);
    expect(container.firstChild).toBeNull();
  });

  it("should show fallback UI when users haven't loaded yet", () => {
    mockUseUsers.mockReturnValue({
      data: [], // Empty array simulates loading state
      error: undefined,
      isLoading: true,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="test.user@example.com" />);

    // Should show the first letter of the email in uppercase
    expect(screen.getByText("T")).toBeInTheDocument();
    
    // Should show the full email as text
    expect(screen.getByText("test.user@example.com")).toBeInTheDocument();
    
    // Should have the correct title attribute
    expect(screen.getByTitle("test.user@example.com")).toBeInTheDocument();
  });

  it("should display user image when user is found and has picture", () => {
    const mockUser = createMockUser({
      email: "john.doe@example.com",
      name: "John Doe",
      picture: "https://example.com/john.jpg",
    });

    mockUseUsers.mockReturnValue({
      data: [mockUser],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="john.doe@example.com" />);

    const image = screen.getByRole("img");
    expect(image).toHaveAttribute("src", "https://example.com/john.jpg");
    expect(image).toHaveAttribute("alt", "john.doe@example.com profile picture");
    expect(image).toHaveAttribute("title", "john.doe@example.com");
  });

  it("should use generated avatar URL when user is found but has no picture", () => {
    const mockUser = createMockUser({
      email: "jane.doe@example.com",
      name: "Jane Doe",
      picture: undefined,
    });

    mockUseUsers.mockReturnValue({
      data: [mockUser],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="jane.doe@example.com" />);

    const image = screen.getByRole("img");
    expect(image).toHaveAttribute(
      "src",
      "https://ui-avatars.com/api/?name=Jane Doe&background=random"
    );
  });

  it("should use assignee email as fallback when user is not found", () => {
    mockUseUsers.mockReturnValue({
      data: [createMockUser({ email: "other.user@example.com" })],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="unknown.user@example.com" />);

    const image = screen.getByRole("img");
    expect(image).toHaveAttribute(
      "src",
      "https://ui-avatars.com/api/?name=unknown.user@example.com&background=random"
    );
  });

  it("should fall back to NameInitialsAvatar on image load error", () => {
    const mockUser = createMockUser({
      email: "john.doe@example.com",
      name: "John Doe",
      picture: "https://example.com/broken-image.jpg",
    });

    mockUseUsers.mockReturnValue({
      data: [mockUser],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="john.doe@example.com" />);

    const image = screen.getByRole("img");
    
    // Simulate image load error
    fireEvent.error(image);

    // Should now show the NameInitialsAvatar component
    expect(screen.getByTestId("name-initials-avatar")).toBeInTheDocument();
    expect(screen.getByTestId("name-initials-avatar")).toHaveAttribute(
      "data-name",
      "John Doe"
    );
    expect(screen.getByTestId("name-initials-avatar")).toHaveAttribute(
      "data-bg-color",
      "orange"
    );
    expect(screen.getByTestId("name-initials-avatar")).toHaveAttribute(
      "data-text-color",
      "white"
    );
    expect(screen.getByTestId("name-initials-avatar")).toHaveAttribute(
      "data-size",
      "32px"
    );

    // Original image should no longer be in the document
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("should use user name for NameInitialsAvatar when image fails and user is found", () => {
    const mockUser = createMockUser({
      email: "john.doe@example.com",
      name: "John Doe",
    });

    mockUseUsers.mockReturnValue({
      data: [mockUser],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="john.doe@example.com" />);

    const image = screen.getByRole("img");
    fireEvent.error(image);

    const avatar = screen.getByTestId("name-initials-avatar");
    expect(avatar).toHaveAttribute("data-name", "John Doe");
  });

  it("should use assignee email for NameInitialsAvatar when image fails and user is not found", () => {
    // Need to have at least one user in the array to trigger image rendering instead of fallback
    const otherUser = createMockUser({ email: "other@example.com" });
    
    mockUseUsers.mockReturnValue({
      data: [otherUser], // User exists but not the one we're looking for
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="unknown@example.com" />);

    const image = screen.getByRole("img");
    fireEvent.error(image);

    const avatar = screen.getByTestId("name-initials-avatar");
    expect(avatar).toHaveAttribute("data-name", "unknown@example.com");
  });

  it("should handle users array with multiple users correctly", () => {
    const users = [
      createMockUser({ email: "user1@example.com", name: "User One", picture: undefined }),
      createMockUser({ email: "user2@example.com", name: "User Two", picture: undefined }),
      createMockUser({ email: "user3@example.com", name: "User Three", picture: undefined }),
    ];

    mockUseUsers.mockReturnValue({
      data: users,
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="user2@example.com" />);

    const image = screen.getByRole("img");
    expect(image).toHaveAttribute(
      "src",
      "https://ui-avatars.com/api/?name=User Two&background=random"
    );
  });

  it("should handle special characters in assignee email", () => {
    // Need to have at least one user to avoid fallback UI
    const otherUser = createMockUser({ email: "other@example.com", picture: undefined });
    
    mockUseUsers.mockReturnValue({
      data: [otherUser],
      error: undefined,
      isLoading: false,
      isValidating: false,
      mutate: jest.fn(),
    });

    render(<AlertAssignee assignee="user+test@example.com" />);

    const image = screen.getByRole("img");
    expect(image).toHaveAttribute(
      "src",
      "https://ui-avatars.com/api/?name=user+test@example.com&background=random"
    );
  });
});
