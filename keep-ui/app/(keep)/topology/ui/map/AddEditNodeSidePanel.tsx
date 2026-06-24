import SidePanel from "@/components/SidePanel";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Button, TextInput } from "@tremor/react";
import React, { useState, ChangeEvent } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { TopologyService } from "../../model";
import { useTranslations } from "next-intl";

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
  const t = useTranslations("topology.addEditNode");
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
      toast.success(t("serviceAddedSuccessfully"), { position: "top-right" });
    } catch (error) {
      toast.error(t("addError", { error: String(error) }), { position: "top-right" });
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
      toast.success(t("serviceUpdatedSuccessfully"), { position: "top-right" });
    } catch (error) {
      toast.error(t("updateError", { error: String(error) }), {
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
              {t("service")}<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="service"
              name="service"
              placeholder={t("enterService")}
              value={formData.service}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="display_name">
              {t("displayName")}<sup className="text-red-500">*</sup>
            </label>
            <TextInput
              id="display_name"
              name="display_name"
              placeholder={t("enterDisplayName")}
              value={formData.display_name}
              onChange={handleChange}
              required
            />
          </div>
          <div>
            <label htmlFor="description">{t("description")}</label>
            <TextInput
              id="description"
              name="description"
              placeholder={t("enterDescription")}
              value={formData.description || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="repository">{t("repository")}</label>
            <TextInput
              id="repository"
              name="repository"
              placeholder={t("enterRepository")}
              value={formData.repository || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="tags">{t("tags")}</label>
            <TextInput
              id="tags"
              name="tags"
              placeholder={t("enterTags")}
              value={formData.tags || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="team">{t("team")}</label>
            <TextInput
              id="team"
              name="team"
              placeholder={t("enterTeam")}
              value={formData.team || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="email">{t("email")}</label>
            <TextInput
              id="email"
              name="email"
              placeholder={t("enterEmail")}
              value={formData.email || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="slack">{t("slack")}</label>
            <TextInput
              id="slack"
              name="slack"
              placeholder={t("enterSlack")}
              value={formData.slack || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="ip_address">{t("ipAddress")}</label>
            <TextInput
              id="ip_address"
              name="ip_address"
              placeholder={t("enterIpAddress")}
              value={formData.ip_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="mac_address">{t("macAddress")}</label>
            <TextInput
              id="mac_address"
              name="mac_address"
              placeholder={t("enterMacAddress")}
              value={formData.mac_address || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="category">{t("category")}</label>
            <TextInput
              id="category"
              name="category"
              placeholder={t("enterCategory")}
              value={formData.category || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="manufacturer">{t("manufacturer")}</label>
            <TextInput
              id="manufacturer"
              name="manufacturer"
              placeholder={t("enterManufacturer")}
              value={formData.manufacturer || ""}
              onChange={handleChange}
            />
          </div>
          <div>
            <label htmlFor="namespace">{t("namespace")}</label>
            <TextInput
              id="namespace"
              name="namespace"
              placeholder={t("enterNamespace")}
              value={formData.namespace || ""}
              onChange={handleChange}
            />
          </div>
        </div>
      </div>
      <div className="sticky bottom-0 p-4 border-t border-gray-200 bg-white flex justify-end gap-2">
        {editData ? (
          <Button onClick={handleUpdate} color="orange" variant="primary">
            {t("update")}
          </Button>
        ) : (
          <Button
            onClick={handleSave}
            color="orange"
            variant="primary"
            disabled={!handleSaveValidation()}
          >
            {t("save")}
          </Button>
        )}
        <Button onClick={handleClosePanel} color="orange" variant="secondary">
          {t("close")}
        </Button>
      </div>
    </SidePanel>
  );
}
