import { useCallback, useEffect, useRef, useState } from "react";
import Modal from "@/components/ui/Modal";
import { Button, Textarea } from "@tremor/react";
import QueryBuilder, {
  defaultOperators,
  Field,
  formatQuery,
  Operator,
  RuleGroupType,
} from "react-querybuilder";
import { parseCEL } from "react-querybuilder/parseCEL";
import { parseSQL } from "react-querybuilder/parseSQL";
import "react-querybuilder/dist/query-builder.scss";
import { Table } from "@tanstack/react-table";
import { FiExternalLink, FiSave } from "react-icons/fi";
import { AlertDto } from "@/entities/alerts/model";
import { TrashIcon } from "@heroicons/react/24/outline";
import { TbDatabaseImport } from "react-icons/tb";
import { components, GroupBase, MenuListProps } from "react-select";
import { Select } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import { IoSearchOutline } from "react-icons/io5";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "react-toastify";
import { CornerDownLeft } from "lucide-react";
import { STATIC_PRESETS_NAMES } from "@/entities/presets/model/constants";
import { Preset } from "@/entities/presets/model/types";
import { usePresetActions } from "@/entities/presets/model/usePresetActions";
import CelInput from "@/features/cel-input/cel-input";
import { useFacetPotentialFields } from "@/features/filter";
import { useCelState } from "@/features/cel-input/use-cel-state";

const staticOptions = [
  { value: 'severity > "info"', label: 'severity > "info"' },
  { value: 'status=="firing"', label: 'status == "firing"' },
  { value: 'source=="grafana"', label: 'source == "grafana"' },
  { value: 'message.contains("CPU")', label: 'message.contains("CPU")' },
];

const CustomOption = (props: any) => {
  return (
    <components.Option {...props}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <IoSearchOutline style={{ marginRight: "8px" }} />
        {props.children}
      </div>
    </components.Option>
  );
};

const kbdStyle = {
  background: "#eee",
  borderRadius: "3px",
  padding: "2px 4px",
  margin: "0 2px",
  fontWeight: "bold",
};

// Define an interface for the custom props
interface CustomMenuListProps
  extends MenuListProps<any, boolean, GroupBase<any>> {
  docsUrl: string;
}

// Custom MenuList with a static line at the end
const CustomMenuList = (props: CustomMenuListProps) => {
  const { docsUrl, ...menuListProps } = props;

  return (
    <components.MenuList {...menuListProps}>
      {props.children}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px",
          background: "lightgray",
          color: "black",
          fontSize: "0.9em",
          borderTop: "1px solid #ddd",
        }}
      >
        <span>
          Wildcard: <kbd style={kbdStyle}>source.contains(&quot;&quot;)</kbd>
        </span>
        <span>
          OR: <kbd style={kbdStyle}> || </kbd>
        </span>
        <span>
          AND: <kbd style={kbdStyle}> && </kbd>
        </span>
        <span>
          <kbd style={kbdStyle}>Enter</kbd> to update query
        </span>
        <a
          href={`${docsUrl}/overview/cel`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            textDecoration: "none",
            color: "black",
            display: "flex",
            alignItems: "center",
          }}
        >
          See Syntax Documentation{" "}
          <FiExternalLink style={{ marginLeft: "5px" }} />
        </a>
      </div>
    </components.MenuList>
  );
};

const customComponents = {
  Control: () => null, // This hides the input field control
  DropdownIndicator: null, // Optionally, hides the dropdown indicator if desired
  IndicatorSeparator: null,
  Option: CustomOption,
  MenuList: CustomMenuList,
};

const getOperators = (id: string): Operator[] => {
  if (id === "source") {
    return [
      { name: "contains", label: "contains" },
      { name: "null", label: "null" },
    ];
  }

  return defaultOperators;
};

type AlertsRulesBuilderProps = {
  table?: Table<AlertDto>;
  selectedPreset?: Preset;
  defaultQuery: string | undefined;
  setIsModalOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  setPresetCEL?: React.Dispatch<React.SetStateAction<string>>;
  updateOutputCEL?: React.Dispatch<React.SetStateAction<string>>;
  onCelChanges?: (cel: string) => void;
  showSqlImport?: boolean;
  customFields?: Field[];
  showSave?: boolean;
  minimal?: boolean;
  showToast?: boolean;
  shouldSetQueryParam?: boolean;
};

const SQL_QUERY_PLACEHOLDER = `SELECT *
FROM alerts
WHERE severity = 'critical' and status = 'firing'`;

const constructCELRules = (preset?: Preset) => {
  // Check if selectedPreset is defined and has options
  if (preset && preset.options) {
    // New version: single "CEL" key
    const celOption = preset.options.find((option) => option.label === "CEL");
    if (celOption) {
      return celOption.value;
    }
    // Older version: Concatenate multiple fields
    else {
      return preset.options
        .map((option) => {
          // Assuming the older format is exactly "x='y'" (x equals y)
          // We split the string by '=', then trim and quote the value part
          let [key, value] = option.value.split("=");
          // Trim spaces and single quotes (if any) from the value
          value = value.trim().replace(/^'(.*)'$/, "$1");
          // Return the correctly formatted CEL expression
          return `${key.trim()}=="${value}"`;
        })
        .join(" && ");
    }
  }
  return ""; // Default to empty string if no preset or options are found
};

export const AlertsRulesBuilder = ({
  table,
  selectedPreset,
  defaultQuery = "",
  setIsModalOpen,
  setPresetCEL,
  updateOutputCEL,
  customFields,
  showSqlImport = true,
  showSave = true,
  minimal = false,
  showToast = false,
  shouldSetQueryParam = true,
  onCelChanges,
}: AlertsRulesBuilderProps) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: config } = useConfig();

  const { deletePreset } = usePresetActions();

  const { data: alertFields } = useFacetPotentialFields("alerts");

  const [isGUIOpen, setIsGUIOpen] = useState(false);
  const [isImportSQLOpen, setImportSQLOpen] = useState(false);
  const [sqlQuery, setSQLQuery] = useState("");

  // Prioritize URL query parameter over preset CEL rules
  const urlCel = searchParams.get("cel");
  const presetCel = constructCELRules(selectedPreset);
  const initialCel = urlCel || presetCel;

  const [appliedCel, setAppliedCel] = useCelState({
    enableQueryParams: shouldSetQueryParam,
    defaultCel: initialCel,
  });
  const [celRules, setCELRules] = useState(appliedCel);

  const parsedCELRulesToQuery = parseCEL(celRules);

  const isDynamic =
    selectedPreset && !STATIC_PRESETS_NAMES.includes(selectedPreset.name);

  const action = isDynamic ? "update" : "create";

  const [query, setQuery] = useState<RuleGroupType>(parsedCELRulesToQuery);
  const [isValidCEL, setIsValidCEL] = useState(true);
  const [sqlError, setSqlError] = useState<string | null>(null);

  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const isFirstRender = useRef(true);

  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleClearInput = useCallback(() => {
    setCELRules("");
    setAppliedCel("");
    onCelChanges && onCelChanges("");
    table?.resetGlobalFilter();
    setIsValidCEL(true);
  }, [table]);

  const toggleSuggestions = () => {
    setShowSuggestions(!showSuggestions);
  };

  const handleSelectChange = (selectedOption: any) => {
    setCELRules(selectedOption.value);
    toggleSuggestions();
  };

  useEffect(() => {
    function handleClickOutside(event: any) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Adjust the height of the textarea based on its content
  const adjustTextAreaHeight = () => {
    const textArea = textAreaRef.current;
    if (textArea) {
      textArea.style.height = "auto";
      textArea.style.height = `${textArea.scrollHeight}px`;
    }
  };
  // Adjust the height whenever the content changes
  useEffect(() => {
    adjustTextAreaHeight();
  }, [celRules]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault(); // Prevents the default action of Enter key in a form
      // close the menu
      setShowSuggestions(false);
      if (isValidCEL) {
        setAppliedCel(celRules);
        if (showToast)
          toast.success("Condition applied", { position: "top-right" });
      }
    }
  };

  useEffect(() => {
    updateOutputCEL?.(appliedCel);
    onCelChanges?.(appliedCel);
  }, [appliedCel, updateOutputCEL]);

  const onGenerateQuery = () => {
    setCELRules(formatQuery(query, "cel"));
    setIsGUIOpen(false);
  };

  const fields: Field[] = table
    ? table
        .getAllColumns()
        .filter(({ getIsPinned }) => getIsPinned() === false)
        .map(({ id, columnDef }) => ({
          name: id,
          label: columnDef.header as string,
          operators: getOperators(id),
        }))
    : customFields
      ? customFields
      : [];

  const onImportSQL = () => {
    setImportSQLOpen(true);
  };

  const convertSQLToCEL = (sql: string): string | null => {
    try {
      const query = parseSQL(sql);
      // Validate the parsed query
      if (!query || !query.rules || query.rules.length === 0) {
        throw new Error("Invalid SQL query: No rules generated.");
      }
      const formattedCel = formatQuery(query, "cel");
      return formatQuery(parseCEL(formattedCel), "cel");
    } catch (error) {
      // If the caught error is an instance of Error, use its message
      if (error instanceof Error) {
        setSqlError(error.message);
      } else {
        setSqlError("An unknown error occurred while parsing SQL.");
      }
      return null;
    }
  };

  const onImportSQLSubmit = () => {
    const convertedCEL = convertSQLToCEL(sqlQuery);
    if (convertedCEL) {
      setCELRules(convertedCEL); // Set the converted CEL as the new CEL rules
      setImportSQLOpen(false); // Close the modal
      setSqlError(null); // Clear any previous errors
    }
  };

  const openSaveModal = (celExpression: string) => {
    setPresetCEL?.(celExpression);
    setIsModalOpen?.(true);
  };

  function getSaveFilterTooltipText(): string {
    if (!isValidCEL) {
      return "You can only save a valid CEL expression.";
    }

    return action === "update"
      ? "Edit preset"
      : "Save current filter as a preset";
  }

  return (
    <>
      <div className="flex flex-col gap-y-2 w-full justify-end">
        {/* Docs */}
        <div className="flex flex-wrap items-start gap-x-2">
          <div className="flex flex-1 min-w-0 gap-2 items-center relative">
            {/* Textarea and error message container */}
            <div className="flex-grow relative" ref={wrapperRef}>
              <div className="relative">
                <CelInput
                  id="alerts-cel-input"
                  placeholder='Use CEL to filter your alerts e.g. source.contains("kibana").'
                  value={celRules}
                  fieldsForSuggestions={alertFields}
                  onValueChange={setCELRules}
                  onIsValidChange={setIsValidCEL}
                  onClearValue={handleClearInput}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setShowSuggestions(true)}
                />
              </div>
              {showSuggestions && (
                <div className="absolute z-10 w-full">
                  <Select
                    options={staticOptions}
                    onChange={handleSelectChange}
                    menuIsOpen={true}
                    components={
                      minimal
                        ? undefined
                        : {
                            ...customComponents,
                            MenuList: (props) => (
                              <CustomMenuList
                                {...props}
                                docsUrl={
                                  config?.KEEP_DOCS_URL ||
                                  "https://docs.keephq.dev"
                                }
                              />
                            ),
                          }
                    }
                    onBlur={() => setShowSuggestions(false)}
                  />
                </div>
              )}
              {!isValidCEL && (
                <div className="text-red-500 text-sm relative top-1">
                  Invalid Common Expression Logic expression.
                </div>
              )}
              <div className="flex items-center justify-end pt-1 px-2">
                <span className="text-xs text-gray-400">
                  <CornerDownLeft className="h-3 w-3 mr-1 inline-block" />
                  Enter to apply
                </span>
              </div>
            </div>
          </div>

          {/* Buttons next to the Textarea */}
          {showSave && (
            <Button
              data-testid="save-preset-button"
              icon={FiSave}
              color="orange"
              variant="secondary"
              size="sm"
              disabled={!celRules.length || !isValidCEL}
              onClick={() => openSaveModal(celRules)}
              tooltip={getSaveFilterTooltipText()}
            ></Button>
          )}
          {showSqlImport && (
            <Button
              color="orange"
              variant="secondary"
              type="button"
              onClick={onImportSQL}
              icon={TbDatabaseImport}
              size="sm"
              tooltip="Import from SQL"
            ></Button>
          )}
          {isDynamic && (
            <Button
              icon={TrashIcon}
              variant="secondary"
              color="red"
              title="Delete preset"
              onClick={() =>
                deletePreset(selectedPreset!.id!, selectedPreset!.name).then(
                  () => {
                    router.push("/alerts/feed");
                  }
                )
              }
            ></Button>
          )}
        </div>
      </div>
      {/* Import SQL */}
      <Modal
        isOpen={isImportSQLOpen}
        onClose={() => {
          setImportSQLOpen(false);
          setSqlError(null);
        }} // Clear the error when closing the modal
        title="Import from SQL"
      >
        <div className="space-y-4 pt-4">
          <Textarea
            className="min-h-[8em] h-auto" // This sets a minimum height and allows it to auto-adjust
            placeholder={SQL_QUERY_PLACEHOLDER}
            onValueChange={setSQLQuery}
          />
          {sqlError && (
            <div className="text-red-500 text-sm mb-2">Error: {sqlError}</div>
          )}
          <div className="flex justify-end">
            <Button
              color="orange"
              onClick={onImportSQLSubmit}
              disabled={!(sqlQuery.length > 0)}
            >
              Convert to CEL
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isGUIOpen}
        onClose={() => setIsGUIOpen(false)}
        className="w-[50%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
        title="Query Builder"
      >
        <div className="space-y-2 pt-4">
          <div className="max-h-96 overflow-auto">
            <QueryBuilder
              query={query}
              onQueryChange={(newQuery) => setQuery(newQuery)}
              fields={fields}
              addRuleToNewGroups
              showCombinatorsBetweenRules={false}
            />
          </div>
          <div className="inline-flex justify-end">
            <Button
              color="orange"
              onClick={onGenerateQuery}
              disabled={!query.rules.length}
            >
              Generate Query
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
