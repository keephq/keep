import SidePanel from "@/components/SidePanel";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Button, TextInput } from "@tremor/react";
import React, { useState, ChangeEvent } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { TopologyService } from "../../model";

interface AddNodeSidePanelProps {
  isOpen: boolean;
  handleClose: () => void;
  editData?: TopologyServiceFormProps;
  topologyMutator: KeyedMutator<TopologyService[]>;
}

export type TopologyServiceFormProps = {
  id?: string;
  repository?: string;
  tags?: string;
  service: string;
  display_name: string;
  description?: string;
  team?: string;
  email?: string;
  slack?: string;
  ip_address?: string;
  mac_address?: string;
  category?: string;
  manufacturer?: string;
  namespace?: string;
};

export function AddEditNodeSidePanel({
  isOpen,
  handleClose,
  editData,
  topologyMutator,
}: AddNodeSidePanelProps) {
  const api = useApi();

  const handleSave = async () => {
    try {
      const result = await api.post("/topology/service", {
        ...formData,
        tags: formData.tags
          ?.split(",")
          .map((tag) => tag.trim()) // Trim whitespace from each tag
          .filter((tag) => tag !== ""),
      });
      toast.success(`Service added successfully`, { position: "top-right" });
    } catch (error) {
      toast.error(`Failed to add service: ${error}`, { position: "top-right" });
    }
    topologyMutator();
    handleClosePanel();
  };

  const handleUpdate = async () => {
    try {
      const result = await api.put("/topology/service", {
        ...formData,
        tags: formData.tags
          ?.split(",")
          .map((tag) => tag.trim()) // Trim whitespace from each tag
          .filter((tag) => tag !== ""),
        id: formData.id,
      });
      toast.success(`Service updated successfully`, { position: "top-right" });
    } catch (error) {
      toast.error(`Failed to update service: ${error}`, {
        position: "top-right",
      });
    }
    topologyMutator();
    handleClosePanel();
  };

  const handleClosePanel = () => {
    setFormData({ ...defaultFormData });
    handleClose();
  };

  const defaultFormData: TopologyServiceFormProps = {
    repository: undefined,
    tags: undefined,
    service: "",
    display_name: "",
    description: undefined,
    team: undefined,
    email: undefined,
    slack: undefined,
    ip_address: undefined,
    mac_address: undefined,
    category: undefined,
    manufacturer: undefined,
    namespace: undefined,
  };

  const [formData, setFormData] = useState<TopologyServiceFormProps>(
    editData ?? {
      ...defaultFormData,
    }
  );

  const handleSaveValidation = () => {
    return formData.display_name.length > 0 && formData.service.length > 0;
  };

  // Function to handle input changes
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prevState) => ({
      ...prevState,
      [name]: value,
    }));
  };

  return (
    <SidePanel isOpen={isOpen} onClose={handleClose} panelWidth={"w-1/3"}>
      <div className="h-full overflow-y-auto gap-y-3 pr-3">
        <div className="flex flex-col gap-y-3">
          <div>
            <label htmlFor="service">
              Service<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="service"
              name="service"
              placeholder="Enter service here..."
              value={formData.service}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="display_name">
              Display Name<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="display_name"
              name="display_name"
              placeholder="Enter display name here..."
              value={formData.display_name}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="description">Description</label>
            <TextInput
              id="description"
              name="description"
              placeholder="Enter description here..."
              value={formData.description || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="repository">Repository</label>
            <TextInput
              id="repository"
              name="repository"
              placeholder="Enter repository here..."
              value={formData.repository || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="tags">Tags</label>
            <TextInput
              id="tags"
              name="tags"
              placeholder="Enter tags here (comma-separated)..."
              value={formData.tags || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="team">Team</label>
            <TextInput
              id="team"
              name="team"
              placeholder="Enter team here..."
              value={formData.team || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="email">Email</label>
            <TextInput
              id="email"
              name="email"
              placeholder="Enter email here..."
              value={formData.email || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="slack">Slack</label>
            <TextInput
              id="slack"
              name="slack"
              placeholder="Enter Slack channel here..."
              value={formData.slack || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="ip_address">IP Address</label>
            <TextInput
              id="ip_address"
              name="ip_address"
              placeholder="Enter IP address here..."
              value={formData.ip_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="mac_address">MAC Address</label>
            <TextInput
              id="mac_address"
              name="mac_address"
              placeholder="Enter MAC address here..."
              value={formData.mac_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="category">Category</label>
            <TextInput
              id="category"
              name="category"
              placeholder="Enter category here..."
              value={formData.category || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="manufacturer">Manufacturer</label>
            <TextInput
              id="manufacturer"
              name="manufacturer"
              placeholder="Enter manufacturer here..."
              value={formData.manufacturer || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="namespace">Namespace</label>
            <TextInput
              id="namespace"
              name="namespace"
              placeholder="Enter namespace here..."
              value={formData.namespace || ""}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>
      <div className="sticky bottom-0 p-4 border-t border-gray-200 bg-white flex justify-end gap-2">
        {editData ? (
          <Button onClick={handleUpdate} color="orange" variant="primary">
            Update
          </Button>
        ) : (
          <Button
            onClick={handleSave}
            color="orange"
            variant="primary"
            disabled={!handleSaveValidation()}
          >
            Save
          </Button>
        )}
        <Button onClick={handleClosePanel} color="orange" variant="secondary">
          Close
        </Button>
      </div>
    </SidePanel>
  );
}
