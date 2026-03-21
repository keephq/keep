import { useI18n } from "@/i18n/hooks/useI18n";
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
  const { t } = useI18n();

  const handleSave = async () => {
    try {
      const result = await api.post("/topology/service", {
        ...formData,
        tags: formData.tags
          ?.split(",")
          .map((tag) => tag.trim()) // Trim whitespace from each tag
          .filter((tag) => tag !== ""),
      });
      toast.success(t("topology.addNode.success"), { position: "top-right" });
    } catch (error) {
      toast.error(`${t("topology.addNode.failed")}: ${error}`, { position: "top-right" });
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
      toast.success(t("topology.addNode.updateSuccess"), { position: "top-right" });
    } catch (error) {
      toast.error(`${t("topology.addNode.updateFailed")}: ${error}`, {
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
              {t("topology.nodeForm.service")}<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="service"
              name="service"
              placeholder={t("topology.nodeForm.placeholders.service")}
              value={formData.service}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="display_name">
              {t("topology.nodeForm.displayName")}<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="display_name"
              name="display_name"
              placeholder={t("topology.nodeForm.placeholders.displayName")}
              value={formData.display_name}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="description">{t("topology.nodeForm.description")}</label>
            <TextInput
              id="description"
              name="description"
              placeholder={t("topology.nodeForm.placeholders.description")}
              value={formData.description || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="repository">{t("topology.nodeForm.repository")}</label>
            <TextInput
              id="repository"
              name="repository"
              placeholder={t("topology.nodeForm.placeholders.repository")}
              value={formData.repository || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="tags">{t("topology.nodeForm.tags")}</label>
            <TextInput
              id="tags"
              name="tags"
              placeholder={t("topology.nodeForm.placeholders.tags")}
              value={formData.tags || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="team">{t("topology.nodeForm.team")}</label>
            <TextInput
              id="team"
              name="team"
              placeholder={t("topology.nodeForm.placeholders.team")}
              value={formData.team || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="email">{t("topology.nodeForm.email")}</label>
            <TextInput
              id="email"
              name="email"
              placeholder={t("topology.nodeForm.placeholders.email")}
              value={formData.email || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="slack">{t("topology.nodeForm.slack")}</label>
            <TextInput
              id="slack"
              name="slack"
              placeholder={t("topology.nodeForm.placeholders.slack")}
              value={formData.slack || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="ip_address">{t("topology.nodeForm.ipAddress")}</label>
            <TextInput
              id="ip_address"
              name="ip_address"
              placeholder={t("topology.nodeForm.placeholders.ipAddress")}
              value={formData.ip_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="mac_address">{t("topology.nodeForm.macAddress")}</label>
            <TextInput
              id="mac_address"
              name="mac_address"
              placeholder={t("topology.nodeForm.placeholders.macAddress")}
              value={formData.mac_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="category">{t("topology.nodeForm.category")}</label>
            <TextInput
              id="category"
              name="category"
              placeholder={t("topology.nodeForm.placeholders.category")}
              value={formData.category || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="manufacturer">{t("topology.nodeForm.manufacturer")}</label>
            <TextInput
              id="manufacturer"
              name="manufacturer"
              placeholder={t("topology.nodeForm.placeholders.manufacturer")}
              value={formData.manufacturer || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="namespace">{t("topology.nodeForm.namespace")}</label>
            <TextInput
              id="namespace"
              name="namespace"
              placeholder={t("topology.nodeForm.placeholders.namespace")}
              value={formData.namespace || ""}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>
      <div className="sticky bottom-0 p-4 border-t border-gray-200 bg-white flex justify-end gap-2">
        {editData ? (
          <Button onClick={handleUpdate} color="orange" variant="primary">
            {t("common.actions.update")}
          </Button>
        ) : (
          <Button
            onClick={handleSave}
            color="orange"
            variant="primary"
            disabled={!handleSaveValidation()}
          >
            {t("common.actions.save")}
          </Button>
        )}
        <Button onClick={handleClosePanel} color="orange" variant="secondary">
          {t("common.actions.close")}
        </Button>
      </div>
    </SidePanel>
  );
}
