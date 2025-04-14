import React, { useState, useEffect } from "react";
import Modal from "@/components/ui/Modal";
import {
  Button,
  Text,
  TextInput,
  Select,
  SelectItem,
  Title,
  Divider,
  Card,
  TabGroup,
  TabList,
  Tab,
} from "@tremor/react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import Papa from "papaparse";
import { TopologyPreview } from "./TopologyPreview";

interface ImportTopologyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface CSVFieldMapping {
  service: string;
  displayName: string;
  environment: string;
  description: string;
  dependsOn: string;
  application: string;
  protocol: string;
}

// Default CSV mappings
const DEFAULT_CSV_MAPPING: CSVFieldMapping = {
  service: "service",
  displayName: "display_name",
  environment: "environment",
  description: "description",
  dependsOn: "depends_on",
  application: "application",
  protocol: "protocol",
};

export const ImportTopologyModal: React.FC<ImportTopologyModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [topologyName, setTopologyName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [fileType, setFileType] = useState<"yaml" | "csv">("yaml");
  const [csvData, setCsvData] = useState<any[]>([]);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvFieldMapping, setCsvFieldMapping] =
    useState<CSVFieldMapping>(DEFAULT_CSV_MAPPING);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewTab, setPreviewTab] = useState(0);

  const api = useApi();

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setTopologyName("");
      setFileType("yaml");
      setCsvData([]);
      setCsvHeaders([]);
      setCsvFieldMapping(DEFAULT_CSV_MAPPING);
      setShowPreview(false);
      setPreviewData(null);
      setPreviewTab(0);
    }
  }, [isOpen]);

  // Set the topology name from filename when a file is selected
  useEffect(() => {
    if (file && !topologyName) {
      // Extract filename without extension
      const fileName = file.name.split(".")[0];
      setTopologyName(fileName);
    }
  }, [file, topologyName]);

  // Auto-detect file type based on extension
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      const selectedFile = event.target.files[0];
      setFile(selectedFile);

      // Auto-detect file type
      const fileName = selectedFile.name.toLowerCase();
      if (fileName.endsWith(".csv")) {
        setFileType("csv");
        parseCSV(selectedFile);
      } else {
        setFileType("yaml");
      }
    }
  };

  // Parse CSV to get headers and sample data
  const parseCSV = (file: File) => {
    Papa.parse(file, {
      header: true,
      preview: 10, // Parse just first 10 rows for preview
      complete: (results) => {
        if (results.data && results.data.length > 0) {
          setCsvData(results.data as any[]);
          if (results.meta.fields) {
            setCsvHeaders(results.meta.fields);

            // Try to auto-map common field names
            const newMapping = { ...DEFAULT_CSV_MAPPING };
            const fields = results.meta.fields;

            // Try to match field names with common variations
            const fieldMappingPatterns = {
              service: [
                "service",
                "name",
                "service_name",
                "servicename",
                "source",
                "source_service",
              ],
              displayName: ["display_name", "displayname", "display", "label"],
              environment: ["environment", "env", "environmentname"],
              description: ["description", "desc", "details"],
              dependsOn: [
                "depends_on",
                "dependson",
                "dependencies",
                "depends",
                "target",
                "target_service",
                "destination",
              ],
              application: [
                "application",
                "app",
                "application_name",
                "appname",
              ],
              protocol: ["protocol", "connection_type", "connection"],
            };

            Object.entries(fieldMappingPatterns).forEach(([key, patterns]) => {
              const matchedField = fields.find((field) =>
                patterns.includes(field.toLowerCase())
              );
              if (matchedField) {
                newMapping[key as keyof CSVFieldMapping] = matchedField;
              } else if (key === "service" || key === "dependsOn") {
                // If we couldn't auto-detect these required fields, make them empty to force user to select
                newMapping[key as keyof CSVFieldMapping] = "";
              }
            });

            setCsvFieldMapping(newMapping);
          }
        }
      },
      error: (error) => {
        showErrorToast(new Error(error.message), "CSV parsing error");
      },
    });
  };

  const handleFieldMappingChange = (
    field: keyof CSVFieldMapping,
    value: string
  ) => {
    setCsvFieldMapping((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const generatePreview = async () => {
    if (!file) return;

    try {
      setIsUploading(true);

      if (fileType === "csv") {
        // Make sure required fields are mapped
        if (!csvFieldMapping.service || !csvFieldMapping.dependsOn) {
          showErrorToast(
            new Error("Service and Dependencies fields must be mapped"),
            "Missing required fields"
          );
          setIsUploading(false);
          return;
        }

        // For CSV, we'll generate a preview of how the data will be transformed
        const result = await new Promise<any>((resolve, reject) => {
          Papa.parse(file, {
            header: true,
            complete: (results) => {
              try {
                // Transform CSV data to the expected topology format
                const servicesMap = new Map<string, any>();
                const applicationsMap = new Map<string, Set<string>>();
                const dependencies: any[] = [];

                results.data.forEach((row: any, index) => {
                  const sourceService = row[csvFieldMapping.service];
                  const targetService = row[csvFieldMapping.dependsOn];

                  if (!sourceService || !targetService) return; // Skip rows with missing data

                  // Create or update source service
                  if (!servicesMap.has(sourceService)) {
                    servicesMap.set(sourceService, {
                      service: sourceService,
                      display_name:
                        row[csvFieldMapping.displayName] || sourceService,
                      environment:
                        row[csvFieldMapping.environment] || "production",
                      description: row[csvFieldMapping.description] || "",
                      id: `src-${index}`, // Temporary ID for preview
                      is_manual: true,
                    });
                  }

                  // Create or update target service
                  if (!servicesMap.has(targetService)) {
                    servicesMap.set(targetService, {
                      service: targetService,
                      display_name: targetService, // No display name for target by default
                      environment: "production", // Default environment
                      description: "", // No description for target by default
                      id: `tgt-${index}`, // Temporary ID for preview
                      is_manual: true,
                    });
                  }

                  // Add dependency
                  dependencies.push({
                    service_id: servicesMap.get(sourceService).id,
                    depends_on_service_id: servicesMap.get(targetService).id,
                    service_name: sourceService,
                    depends_on_service_name: targetService,
                    protocol: row[csvFieldMapping.protocol] || "HTTP", // Default protocol
                  });

                  // Handle application assignment if present
                  if (
                    csvFieldMapping.application &&
                    row[csvFieldMapping.application]
                  ) {
                    const apps = row[csvFieldMapping.application]
                      .split(",")
                      .map((a: string) => a.trim());
                    apps.forEach((app: string) => {
                      if (app) {
                        if (!applicationsMap.has(app)) {
                          applicationsMap.set(app, new Set());
                        }
                        applicationsMap.get(app)?.add(sourceService);
                        // Also add target service to the application
                        applicationsMap.get(app)?.add(targetService);
                      }
                    });
                  }
                });

                // Convert services map to array
                const services = Array.from(servicesMap.values());

                // Create service ID lookup map
                const serviceIdMap = new Map<string, string>();
                services.forEach((svc) => {
                  serviceIdMap.set(svc.service, svc.id);
                });

                // Convert applications map to array
                const applications = Array.from(applicationsMap.entries()).map(
                  ([name, servicesSet], index) => ({
                    id: `app-${index + 1}`,
                    name,
                    description: `Application ${name}`,
                    services: Array.from(servicesSet)
                      .map((serviceName) => {
                        return serviceIdMap.get(serviceName);
                      })
                      .filter(Boolean),
                  })
                );

                resolve({
                  services,
                  applications,
                  dependencies,
                });
              } catch (error) {
                reject(error);
              }
            },
            error: reject,
          });
        });

        setPreviewData(result);
        setShowPreview(true);
      } else {
        // For YAML, we'll just show a message since we can't parse YAML in the browser
        setPreviewData({
          message:
            "YAML preview is not available. The file will be parsed on the server.",
        });
        setShowPreview(true);
      }
    } catch (error) {
      showErrorToast(error, "Error generating preview");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      showErrorToast(
        new Error("Please select a file to upload"),
        "No file selected"
      );
      return;
    }

    // For CSV format, validate required fields
    if (fileType === "csv") {
      if (!csvFieldMapping.service) {
        showErrorToast(
          new Error("Source Service field must be mapped"),
          "Missing required field"
        );
        return;
      }

      if (!csvFieldMapping.dependsOn) {
        showErrorToast(
          new Error("Target Service field must be mapped"),
          "Missing required field"
        );
        return;
      }
    }

    setIsUploading(true);

    const formData = new FormData();
    formData.set("file", file);

    if (topologyName.trim()) {
      formData.set("name", topologyName.trim());
    }

    // Add format information and field mappings for CSV
    if (fileType === "csv") {
      formData.set("format", "csv");
      formData.set("mapping", JSON.stringify(csvFieldMapping));
    } else {
      formData.set("format", "yaml");
    }

    try {
      await api.request("/topology/import", {
        method: "POST",
        body: formData,
      });

      showSuccessToast("Topology imported successfully!");
      setFile(null);
      setTopologyName("");
      onSuccess();
      onClose();
    } catch (error) {
      showErrorToast(error, "Error uploading file");
    } finally {
      setIsUploading(false);
    }
  };

  const renderCSVMapping = () => (
    <div className="space-y-4 mt-4">
      <Title className="text-base">CSV Field Mapping</Title>
      <Text className="text-sm">
        Map CSV columns to topology attributes. Each row should represent a
        dependency between services.
      </Text>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Source Service <span className="text-red-500">*</span>
          </label>
          <Select
            value={csvFieldMapping.service}
            onValueChange={(value) =>
              handleFieldMappingChange("service", value)
            }
            required={true}
            placeholder="Select a field"
            error={
              !csvFieldMapping.service ? "This field is required" : undefined
            }
          >
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text
            className={`text-xs ${
              !csvFieldMapping.service ? "text-red-500" : "text-gray-500"
            } mt-1`}
          >
            Required - Service that depends on another service
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Target Service <span className="text-red-500">*</span>
          </label>
          <Select
            value={csvFieldMapping.dependsOn}
            onValueChange={(value) =>
              handleFieldMappingChange("dependsOn", value)
            }
            required={true}
            placeholder="Select a field"
            error={
              !csvFieldMapping.dependsOn ? "This field is required" : undefined
            }
          >
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text
            className={`text-xs ${
              !csvFieldMapping.dependsOn ? "text-red-500" : "text-gray-500"
            } mt-1`}
          >
            Required - Service that the source service depends on
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Display Name
          </label>
          <Select
            value={csvFieldMapping.displayName}
            onValueChange={(value) =>
              handleFieldMappingChange("displayName", value)
            }
          >
            <SelectItem value="">None</SelectItem>
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text className="text-xs text-gray-500 mt-1">
            Optional - Human-readable name for the source service
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Protocol
          </label>
          <Select
            value={csvFieldMapping.protocol}
            onValueChange={(value) =>
              handleFieldMappingChange("protocol", value)
            }
          >
            <SelectItem value="">None</SelectItem>
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text className="text-xs text-gray-500 mt-1">
            Optional - Communication protocol between services (HTTP, HTTPS,
            etc.)
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Environment
          </label>
          <Select
            value={csvFieldMapping.environment}
            onValueChange={(value) =>
              handleFieldMappingChange("environment", value)
            }
          >
            <SelectItem value="">None</SelectItem>
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text className="text-xs text-gray-500 mt-1">
            Optional - Environment name (production, staging, etc.)
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <Select
            value={csvFieldMapping.description}
            onValueChange={(value) =>
              handleFieldMappingChange("description", value)
            }
          >
            <SelectItem value="">None</SelectItem>
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text className="text-xs text-gray-500 mt-1">
            Optional - Service description
          </Text>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Application
          </label>
          <Select
            value={csvFieldMapping.application}
            onValueChange={(value) =>
              handleFieldMappingChange("application", value)
            }
          >
            <SelectItem value="">None</SelectItem>
            {csvHeaders.map((header) => (
              <SelectItem key={header} value={header}>
                {header}
              </SelectItem>
            ))}
          </Select>
          <Text className="text-xs text-gray-500 mt-1">
            Optional - Comma-separated list of applications these services
            belong to
          </Text>
        </div>
      </div>

      {csvData.length > 0 && (
        <div className="mt-4">
          <Title className="text-base">CSV Preview</Title>
          <div className="overflow-x-auto max-h-48 mt-2 border border-gray-200 rounded-md">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {csvHeaders.map((header) => (
                    <th
                      key={header}
                      className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {csvData.slice(0, 5).map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {csvHeaders.map((header) => (
                      <td
                        key={`${rowIndex}-${header}`}
                        className="px-3 py-2 text-xs text-gray-500"
                      >
                        {String(row[header] || "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Text className="text-xs text-gray-500 mt-1">
            Showing first 5 rows of {csvData.length} total rows
          </Text>
        </div>
      )}
    </div>
  );

  const renderPreview = () => {
    if (!previewData) return null;

    if (fileType === "yaml") {
      return (
        <Card className="p-4 mt-4">
          <Title className="text-base">YAML Preview</Title>
          <Text className="text-sm">
            YAML files will be processed on the server. Preview not available.
          </Text>
        </Card>
      );
    }

    return (
      <Card className="p-4 mt-4">
        <Title className="text-base">Preview</Title>
        <div className="mt-4">
          <TopologyPreview
            services={previewData.services || []}
            dependencies={previewData.dependencies || []}
            className="h-64 w-full border border-gray-200 rounded-md"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <div className="bg-gray-100 p-2 rounded text-xs">
              <span className="font-medium">Services:</span>{" "}
              {previewData.services?.length || 0}
            </div>
            <div className="bg-gray-100 p-2 rounded text-xs">
              <span className="font-medium">Dependencies:</span>{" "}
              {previewData.dependencies?.length || 0}
            </div>
            <div className="bg-gray-100 p-2 rounded text-xs">
              <span className="font-medium">Applications:</span>{" "}
              {previewData.applications?.length || 0}
            </div>
          </div>
        </div>
      </Card>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Import Topology"
      description="Import topology data from a file"
      className="max-w-4xl"
    >
      <div className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* File selection and name */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="topologyName"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Topology Name (optional)
              </label>
              <TextInput
                id="topologyName"
                placeholder="Enter a name for this topology"
                value={topologyName}
                onChange={(e) => setTopologyName(e.target.value)}
              />
            </div>

            <div>
              <label
                htmlFor="fileInput"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Topology File
              </label>
              <div className="flex items-center space-x-2">
                <input
                  type="file"
                  id="fileInput"
                  onChange={handleFileChange}
                  accept=".yaml,.json,.csv"
                  className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-semibold
                    file:bg-gray-100 file:text-gray-700
                    hover:file:bg-gray-200"
                />
              </div>
              {file && (
                <Text className="mt-2 text-sm text-gray-500">
                  Selected file: {file.name} ({(file.size / 1024).toFixed(1)}{" "}
                  KB)
                </Text>
              )}
            </div>
          </div>

          {/* File format selector */}
          {file && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                File Format
              </label>
              <div className="flex space-x-4">
                <label className="inline-flex items-center">
                  <input
                    type="radio"
                    className="form-radio text-orange-600"
                    checked={fileType === "yaml"}
                    onChange={() => setFileType("yaml")}
                  />
                  <span className="ml-2">YAML</span>
                </label>
                <label className="inline-flex items-center">
                  <input
                    type="radio"
                    className="form-radio text-orange-600"
                    checked={fileType === "csv"}
                    onChange={() => setFileType("csv")}
                  />
                  <span className="ml-2">CSV</span>
                </label>
              </div>
            </div>
          )}

          {/* CSV field mapping */}
          {file &&
            fileType === "csv" &&
            csvHeaders.length > 0 &&
            renderCSVMapping()}

          {/* Preview button */}
          {file && (
            <div className="flex justify-center mt-4">
              <Button
                color="gray"
                variant="secondary"
                onClick={generatePreview}
                disabled={isUploading}
              >
                {showPreview ? "Refresh Preview" : "Generate Preview"}
              </Button>
            </div>
          )}

          {/* Data preview */}
          {showPreview && renderPreview()}

          <Divider />

          {/* Action buttons */}
          <div className="flex justify-end space-x-2 pt-4">
            <Button
              color="gray"
              variant="secondary"
              onClick={onClose}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              color="orange"
              variant="primary"
              disabled={!file || isUploading}
              loading={isUploading}
            >
              Import
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
