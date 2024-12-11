import { useCallback, useEffect, useRef, useState } from "react";
import Modal from "components/ui/Modal";
import { Button, Textarea } from "@tremor/react";
import QueryBuilder, {
  Field,
  Operator,
  RuleGroupType,
  defaultOperators,
  formatQuery,
  parseCEL,
  parseSQL,
} from "react-querybuilder";
import "react-querybuilder/dist/query-builder.scss";
import { Table } from "@tanstack/react-table";
import {
  AlertDto,
  Preset,
  severityMapping,
  reverseSeverityMapping,
} from "./models";
import { XMarkIcon, TrashIcon } from "@heroicons/react/24/outline";
import { TbDatabaseImport } from "react-icons/tb";
import Select, { components, MenuListProps } from "react-select";

import { IoSearchOutline } from "react-icons/io5";
import { FiExternalLink } from "react-icons/fi";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "react-toastify";
import { CornerDownLeft } from "lucide-react";
import { Link } from "@/components/ui";
import { DocumentTextIcon } from "@heroicons/react/24/outline";

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

// Custom MenuList with a static line at the end
const CustomMenuList = (props: MenuListProps<{}>) => {
  return (
    <components.MenuList {...props}>
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
          borderTop: "1px solid #ddd", // Add a separator if you like
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
          href="https://docs.keephq.dev/overview/presets"
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

// Define the styles for react-select
const customStyles = {
  option: (provided: any, state: any) => ({
    ...provided,
    color: state.isFocused ? "black" : "black",
    backgroundColor: state.isFocused ? "rgba(255, 165, 0, 0.4)" : "white", // Orange with opacity
    cursor: "pointer",
    display: "flex",
    alignItems: "center", // Align items in the center vertically
  }),
  menu: (provided: any) => ({
    ...provided,
    margin: 0, // Remove the margin around the dropdown menu
    borderRadius: "0", // Optional: Align with the border-radius of the Textarea if necessary
  }),
  // You can add more style customizations for other parts of the Select here if needed
};

// Culled from: https://stackoverflow.com/a/54372020/12627235
const getAllMatches = (pattern: RegExp, string: string) =>
  // make sure string is a String, and make sure pattern has the /g flag
  String(string).match(new RegExp(pattern, "g"));

const sanitizeCELIntoJS = (celExpression: string): string => {
  // First, replace "contains" with "includes"
  let jsExpression = celExpression.replace(/contains/g, "includes");

  // Replace severity comparisons with mapped values
  jsExpression = jsExpression.replace(
    /severity\s*([<>]=?|==)\s*(\d+|"[^"]*")/g,
    (match, operator, value) => {
      let severityKey;

      if (/^\d+$/.test(value)) {
        // If the value is a number
        severityKey = severityMapping[Number(value)];
      } else {
        // If the value is a string
        severityKey = value.replace(/"/g, "").toLowerCase(); // Remove quotes from the string value and convert to lowercase
      }

      const severityValue = reverseSeverityMapping[severityKey];

      if (severityValue === undefined) {
        return match; // If no mapping found, return the original match
      }

      // For equality, directly replace with the severity level
      if (operator === "==") {
        return `severity == "${severityKey}"`;
      }

      // For greater than or less than, include multiple levels based on the mapping
      const levels = Object.entries(reverseSeverityMapping);
      let replacement = "";
      if (operator === ">") {
        const filteredLevels = levels
          .filter(([, level]) => level > severityValue)
          .map(([key]) => `severity == "${key}"`);
        replacement = filteredLevels.join(" || ");
      } else if (operator === "<") {
        const filteredLevels = levels
          .filter(([, level]) => level < severityValue)
          .map(([key]) => `severity == "${key}"`);
        replacement = filteredLevels.join(" || ");
      }

      return `(${replacement})`;
    }
  );

  // Convert 'in' syntax to '.includes()'
  jsExpression = jsExpression.replace(
    /(\w+)\s+in\s+\[([^\]]+)\]/g,
    (match, variable, list) => {
      // Split the list by commas, trim spaces, and wrap items in quotes if not already done
      const items = list
        .split(",")
        .map((item: string) => item.trim().replace(/^([^"]*)$/, '"$1"'));
      return `[${items.join(", ")}].includes(${variable})`;
    }
  );

  return jsExpression;
};

// this pattern is far from robust
const variablePattern = /[a-zA-Z$_][0-9a-zA-Z$_]*/;
const jsReservedWords = new Set([
  "break",
  "case",
  "catch",
  "class",
  "const",
  "continue",
  "debugger",
  "default",
  "delete",
  "do",
  "else",
  "export",
  "extends",
  "finally",
  "for",
  "function",
  "if",
  "import",
  "in",
  "instanceof",
  "new",
  "return",
  "super",
  "switch",
  "this",
  "throw",
  "try",
  "typeof",
  "var",
  "void",
  "while",
  "with",
  "yield",
]);

export const evalWithContext = (context: AlertDto, celExpression: string) => {
  try {
    if (celExpression.length === 0) {
      return new Function();
    }

    const jsExpression = sanitizeCELIntoJS(celExpression);
    let variables = (getAllMatches(variablePattern, jsExpression) ?? []).filter(
      (variable) => variable !== "true" && variable !== "false"
    );

    // filter reserved words from variables
    variables = variables.filter((variable) => !jsReservedWords.has(variable));
    const func = new Function(...variables, `return (${jsExpression})`);

    const args = variables.map((arg) =>
      Object.hasOwnProperty.call(context, arg)
        ? context[arg as keyof AlertDto]
        : undefined
    );

    return func(...args);
  } catch (error) {
    return;
  }
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
  deletePreset?: (presetId: string) => Promise<void>;
  setPresetCEL?: React.Dispatch<React.SetStateAction<string>>;
  updateOutputCEL?: React.Dispatch<React.SetStateAction<string>>;
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

export const AlertsRulesBuilder = ({
  table,
  selectedPreset,
  defaultQuery = "",
  setIsModalOpen,
  deletePreset,
  setPresetCEL,
  updateOutputCEL,
  customFields,
  showSqlImport = true,
  showSave = true,
  minimal = false,
  showToast = false,
  shouldSetQueryParam = true,
}: AlertsRulesBuilderProps) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [isGUIOpen, setIsGUIOpen] = useState(false);
  const [isImportSQLOpen, setImportSQLOpen] = useState(false);
  const [sqlQuery, setSQLQuery] = useState("");
  const [celRules, setCELRules] = useState(
    searchParams?.get("cel") || defaultQuery
  );
  const parsedCELRulesToQuery = parseCEL(celRules);

  const setQueryParam = (key: string, value: string) => {
    const current = new URLSearchParams(
      Array.from(searchParams ? searchParams.entries() : [])
    );

    if (value) {
      current.set(key, value);
    }

    // cast to string
    const search = current.toString();
    // or const query = `${'?'.repeat(search.length && 1)}${search}`;
    const query = search ? `?${search}` : "";
    router.push(`${pathname}${query}`);
  };

  const [query, setQuery] = useState<RuleGroupType>(parsedCELRulesToQuery);
  const [isValidCEL, setIsValidCEL] = useState(true);
  const [sqlError, setSqlError] = useState<string | null>(null);

  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const isFirstRender = useRef(true);

  const [showSuggestions, setShowSuggestions] = useState(false);

  const handleClearInput = useCallback(() => {
    setCELRules("");
    table?.resetGlobalFilter();
    setIsValidCEL(true);
  }, [table]);

  const toggleSuggestions = () => {
    setShowSuggestions(!showSuggestions);
  };

  const handleSelectChange = (selectedOption: any) => {
    setCELRules(selectedOption.value);
    toggleSuggestions();
    onApplyFilter();
  };

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

  useEffect(() => {
    if (defaultQuery === "") {
      handleClearInput();
    } else {
      setCELRules(defaultQuery);
    }
  }, [defaultQuery, handleClearInput]);

  useEffect(() => {
    // Use the constructCELRules function to set the initial value of celRules
    const initialCELRules = constructCELRules(selectedPreset);
    if (
      (!selectedPreset || selectedPreset.name === "feed") && // Only applies if no preset is selected or the preset is "feed"
      searchParams?.get("cel") // Check if the cel query is present in the URL and set it as the initial value
    ) {
      setCELRules(searchParams.get("cel") || "");
    } else {
      setCELRules(initialCELRules);
    }
  }, [selectedPreset, searchParams]);

  useEffect(() => {
    // This effect waits for celRules to update and applies the filter only on the initial render
    if (isFirstRender.current && celRules.length > 0) {
      onApplyFilter();
      isFirstRender.current = false;
    } else if (!selectedPreset) {
      isFirstRender.current = false;
    }
    // This effect should only run when celRules updates and on initial render
  }, [celRules]);

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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      e.preventDefault(); // Prevents the default action of Enter key in a form
      // You can now use `target` which is asserted to be an HTMLTextAreaElement

      // check if the CEL is valid by comparing the parsed query with the original CEL
      // remove spaces so that "a && b" is the same as "a&&b"
      const celQuery = formatQuery(parsedCELRulesToQuery, "cel");
      /*
      SHAHAR: this is the old way of checking if the CEL is valid
              I think its over complicated so let's just check if the query is "1 == 1" (which is parse error)
              I'll leave the old code here for reference

      const isValidCEL =
        celQuery.replace(/\s+/g, "") === celRules.replace(/\s+/g, "") ||
        celRules === "";
      */

      // SHAHAR: new way of checking if the CEL is valid
      const isValidCEL = celRules == "" || celQuery !== "1 == 1";
      setIsValidCEL(isValidCEL);

      // close the menu
      setShowSuggestions(false);
      if (isValidCEL) {
        if (shouldSetQueryParam) setQueryParam("cel", celRules);
        onApplyFilter();
        updateOutputCEL?.(celRules);
        if (showToast)
          toast.success("Condition applied", { position: "top-right" });
      }
    }
  };

  const onApplyFilter = () => {
    if (celRules.length === 0) {
      return table?.resetGlobalFilter();
    }

    return table?.setGlobalFilter(celRules);
  };

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

  const onValueChange = (value: string) => {
    setCELRules(value);
    if (value.length === 0) {
      setIsValidCEL(true);
    }
  };

  const validateAndOpenSaveModal = (celExpression: string) => {
    // Use existing validation logic
    const celQuery = formatQuery(parseCEL(celExpression), "cel");
    const isValidCEL =
      celQuery.replace(/\s+/g, "") === celExpression.replace(/\s+/g, "") ||
      celExpression === "";

    if (isValidCEL && celExpression.length) {
      // If CEL is valid and not empty, set the CEL rules for the preset and open the modal
      setPresetCEL?.(celExpression);
      setIsModalOpen?.(true);
    } else {
      // If CEL is invalid or empty, inform the user
      alert("You can only save a valid CEL expression.");
      setIsValidCEL(isValidCEL);
    }
  };

  return (
    <>
      <div className="flex flex-col gap-y-2 w-full justify-end">
        {/* Docs */}
        <div className="flex flex-wrap items-start gap-x-2">
          <div className="flex flex-wrap gap-2 items-center relative flex-grow">
            {/* Textarea and error message container */}
            <div className="flex-grow relative" ref={wrapperRef}>
              <Textarea
                ref={textAreaRef}
                rows={1}
                className="resize-none overflow-hidden w-full pr-9 min-h-[38px]" // Padding for clear button and height to match the button height
                value={celRules}
                onValueChange={onValueChange}
                onKeyDown={handleKeyDown}
                placeholder='Use CEL to filter your alerts e.g. source.contains("kibana").'
                error={!isValidCEL}
                onFocus={() => setShowSuggestions(true)}
              />
              {celRules && (
                <button
                  onClick={handleClearInput}
                  className="absolute top-0 right-0 w-9 h-[38px] flex items-center justify-center text-gray-400 hover:text-gray-600" // Position to the left of the Enter to apply badge
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              )}
              {showSuggestions && (
                <div className="absolute z-10 w-full">
                  <Select
                    options={staticOptions}
                    onChange={handleSelectChange}
                    menuIsOpen={true}
                    components={minimal ? undefined : customComponents}
                    onBlur={() => setShowSuggestions(false)}
                    styles={customStyles}
                  />
                </div>
              )}
              {!isValidCEL && (
                <div className="text-red-500 text-sm absolute bottom-0 left-0 transform translate-y-full">
                  Invalid Common Expression Logic expression.
                </div>
              )}
              <div className="flex items-center justify-between pt-1 px-2">
                <Link
                  href="https://docs.keephq.dev/overview/presets"
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-xs text-tremor-muted"
                  icon={DocumentTextIcon}
                >
                  CEL Documentation
                </Link>
                <span className="text-xs text-gray-400">
                  <CornerDownLeft className="h-3 w-3 mr-1 inline-block" />
                  Enter to apply
                </span>
              </div>
            </div>
          </div>

          {/* Buttons next to the Textarea */}
          {showSqlImport && (
            <Button
              color="orange"
              variant="secondary"
              type="button"
              onClick={onImportSQL}
              icon={TbDatabaseImport}
              size="sm"
              tooltip="Import from SQL"
            >
              Import from SQL
            </Button>
          )}
          {showSave && (
            <Button
              color="orange"
              size="sm"
              disabled={!celRules.length}
              onClick={() => validateAndOpenSaveModal(celRules)}
              tooltip="Save current filter as a preset"
            >
              Save
            </Button>
          )}
          {selectedPreset &&
            selectedPreset.name &&
            selectedPreset?.name !== "deleted" &&
            selectedPreset?.name !== "feed" &&
            selectedPreset?.name !== "dismissed" &&
            deletePreset && (
              <Button
                icon={TrashIcon}
                color="orange"
                title="Delete preset"
                onClick={async () => await deletePreset(selectedPreset!.id!)}
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
        <div className="space-y-4 p-4">
          <Textarea
            className="min-h-[8em] h-auto" // This sets a minimum height and allows it to auto-adjust
            placeholder={SQL_QUERY_PLACEHOLDER}
            onValueChange={setSQLQuery}
          />
          {sqlError && (
            <div className="text-red-500 text-sm mb-2">Error: {sqlError}</div>
          )}
          <Button
            color="orange"
            onClick={onImportSQLSubmit}
            disabled={!(sqlQuery.length > 0)}
          >
            Convert to CEL
          </Button>
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
