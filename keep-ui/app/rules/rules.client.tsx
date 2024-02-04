'use client';
import React, { useState, useEffect, useMemo } from "react";
import { Card, Flex, Title, Subtitle, TextInput, Button, Table, TableCell, TableBody, TableRow, TableHead, TableHeaderCell, Icon, AreaChart, Text } from "@tremor/react";
import Select from 'react-select';
import CreatableSelect from 'react-select/creatable';
import QueryBuilder, { add, remove, RuleGroupTypeAny, RuleGroupType, ValidationMap, Field, formatQuery, defaultOperators, parseCEL, QueryValidator, findPath} from 'react-querybuilder';
// import 'react-querybuilder/dist/query-builder.scss';
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import './query-builder.scss';
import { FaRegTrashAlt } from "react-icons/fa";
import { FaQuestionCircle } from 'react-icons/fa';

interface Distribution {
  [group: string]: {
    [timestamp: string]: number;
  };
}

interface CombinedData {
  [timestamp: string]: {
    date: any; // Assuming getDate returns a string
    [group_id: string]: number; // Adjust the type according to your actual data structure
  };
}

const customValidator: QueryValidator = (query: RuleGroupTypeAny): ValidationMap => {
  const validationMap: ValidationMap = {};

  const checkRules = (rules: any) => {
    rules.forEach((rule: any) => {
      if (rule.rules) {
        // If it's a group, recursively check its rules
        checkRules(rule.rules);
      } else {
        // Check if the rule value is empty and update the validation map
        validationMap[rule.id] = {
          valid: rule.value !== '',
          reasons: rule.value === '' ? ['Value cannot be empty'] : []
        };
      }
    });
  };

  checkRules(query.rules);
  return validationMap;
};

const CustomValueEditor = (props: any) => {
  const { value, handleOnChange, operator, rule, validationErrors } = props;

  // Define an array of operators that do not require the input
  const operatorsWithoutInput = ["null", "notNull"]; // Add more as needed

  // Check if the selected operator is in the operatorsWithoutInput array
  const isInputHidden = operatorsWithoutInput.includes(operator);

  const handleOnChangeInternal = (value: string) => {
    // Clear the validation error for the rule when the user edits the value
    handleOnChange(value);
    delete props.validationErrors[`rule_${rule.id}`];
  }
  // Determine if the current rule has a validation error
  const isValid = !validationErrors || !validationErrors[`rule_${rule.id}`];
  const errorMessage = isValid ? "" : validationErrors[`rule_${rule.id}`];

  return (
    <>
      <div className={`relative ${!isValid ? 'pt-6' : ''}`}>
        {!isInputHidden && (
          <TextInput
            className="w-auto"
            error={!isValid}
            errorMessage={errorMessage}
            type="text"
            value={value}
            onChange={(e) => handleOnChangeInternal(e.target.value)}
          />
        )}
    </div>
    </>
  );
};


const CustomCombinatorSelector = (props: any) => {
  const { options, value, handleOnChange, level, path } = props;

  if(level === 0){
    return null;
  }

  return (
      <Title>
        Alert Group {path[0] + 1}
      </Title>
  );
}

const CustomOperatorSelector = (props: any) => {
  const { options, value, handleOnChange } = props;

  // Convert options to the format expected by react-select
  const reactSelectOptions = options.map((option: any) => ({
    label: option.label,
    value: option.name,
  }));

  return (
    <Select
      isClearable={false}
      value={reactSelectOptions.find((option: any) => option.value === value)}
      onChange={(selectedOption) => handleOnChange(selectedOption.value)}
      options={reactSelectOptions}
      styles={{
        control: (provided) => ({
          ...provided,
          width: '150px',
        }),
      }}
    />
  );
};


const CustomAddGroupAction = (props: any) => {
  if(props.level > 0){
    return null;
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block'}}>
    <Button onClick={props.handleOnClick} color="orange">
      Add Alerts Group
    </Button>
    <Icon
      className="rules-tooltip"
      icon={FaQuestionCircle}
      tooltip="Any Rule consists of one or more Alert Groups. Each alert group is evaluated separately and the results are combined using AND combinator. For example, if you want to group alerts that has a severity of 'critical' and another alert with a source of 'Kibana', you would create a rule with two alert groups. The first alert group would have a rule with severity = 'critical' and the second alert group would have a rule with source = 'kibana'."
      variant="simple"
      size="md"
      color="stone"
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        transform: 'translate(50%, -50%)',
        zIndex:9999
      }}
    />
  </div>

  );
};

const CustomAddRuleAction = (props: any) => {
  const { label, handleOnClick, addRule } = props;

  if (props.level === 0) {
    return null;
  }

  const handleAddRuleClick = () => {
    addRule(props);
  };

  const availableFields = props.schema.fields.filter((fld: any) =>
      !props.rules.some((rule: any) => rule.field === fld.name)
    );

  return (
    <div className="relative inline-block">
      <Button onClick={handleAddRuleClick} color="orange" disabled={availableFields.length === 0} className="text-white bg-orange-500 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed">
          Add Condition
        </Button>
        <Icon
          className="rules-tooltip absolute translate-x-1/2 -translate-y-1/2 top-0 right-0 z-50"
          icon={FaQuestionCircle}
          tooltip="Any group consists of one or more Conditions. Each condition is evaluated separately and the results are combined using AND combinator. For example, if you want to create a group that has a severity of 'critical' and source of 'kibana', you would create two conditions. The first condition would be severity = 'critical' and the second condition would be source = 'kibana'."
          variant="simple"
          size="md"
          color="stone"
        />
    </div>

  );
};




interface Rule {
  id: string;
  name: string;
  definition: string;
  definition_cel: string;
  timeframe: number;
  created_by: string;
  creation_time: string;
  updated_by: string;
  update_time: string;
  distribution?: { [group: string]: { [timestamp: string]: number } };
}

type ExpandedRowsType = {
  [key: string]: boolean;
};

const defaultQuery = {
  combinator: 'and',
  rules: [
    {
      combinator: 'and', // or 'or' depending on your logic
      rules: [
        { field: 'source', operator: '=', value: '' }
      ],
    },
    {
      combinator: 'and', // or 'or' depending on your logic
      rules: [
        { field: 'source', operator: '=', value: '' },
      ],
    }
  ],
}

export default function Page() {
  // Use the extended type for the query state
  const [query, setQuery] = useState<RuleGroupType>(defaultQuery);
  const [formData, setFormData] = useState({
    ruleName: "Rule Name",
    timeframe: 600,
    timeframeUnit: "Seconds",
  });
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>(
    {}
  );
  const [fields, setFields] = useState<Field[]>([
    { name: 'source', label: 'source', datatype: 'text'},
    { name: 'severity', label: 'severity', datatype: 'text'},
    { name: 'service', label: 'service', datatype: 'text'},
  ]);
  const [expandedRows, setExpandedRows] = useState<ExpandedRowsType>({});
  const [activeRow, setActiveRow] = useState<string | null>(null);

  const { data: session, status } = useSession();
  const [rules, setRules] = useState<Rule[]>([]);
  const [editMode, setEditMode] = useState(false);
  const [loadingRules, setLoadingRules] = useState(true);

  const valueEditor = useMemo(() => {
    const Component = (props: any) => <CustomValueEditor {...props} validationErrors={validationErrors}/>;
    Component.displayName = 'ValueEditor'; // Assign a display name to the component
    return Component;
}, [validationErrors]);


  useEffect(() => {
    // Fetch rules data from the /rules API
    if (!session) return;

    const apiUrl = getApiURL();
    fetch(`${apiUrl}/rules`, {
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
      },
    })
      .then((response) => response.json())
      .then((data) => {
        setRules(data);
        setLoadingRules(false);
      })
      .catch((error) => {
        console.error("Error fetching rules:", error);
      });
  }, [session]);

  if (status === "loading") return <Loading />;

  const isNumber = (value: string) => {
    return !isNaN(Number(value));
  };

  const getOperators = (fieldName: string) => {
    const field = fields.find(fld => fld.name === fieldName);
    // if the field is not found - it means it added dynamically and we support only text for now anyway
    // todo: in the future getOperators should wait for setFields hook to finish
    if(!field){
      return [
        ...defaultOperators.filter(op =>
          [
            '=',
            'contains',
            'beginsWith',
            'endsWith',
            'doesNotContain',
            'doesNotBeginWith',
            'doesNotEndWith',
            'null',
            'notNull',
            'in',
            'notIn',
          ].includes(op.name)
        ),
      ];
    }

    switch (field!.datatype) {
      case 'text':
        return [
          ...defaultOperators.filter(op =>
            [
              '=',
              'contains',
              'beginsWith',
              'endsWith',
              'doesNotContain',
              'doesNotBeginWith',
              'doesNotEndWith',
              'null',
              'notNull',
              'in',
              'notIn',
            ].includes(op.name)
          ),
        ];
      case 'number':
        return [
          ...defaultOperators.filter(op => ['=', '!='].includes(op.name)),
          { name: '<', label: 'less than' },
          { name: '<=', label: 'less than or equal to' },
          { name: '>', label: 'greater than' },
          { name: '>=', label: 'greater than or equal to' },
          ...defaultOperators.filter(op => ['null', 'notNull'].includes(op.name)),
        ];
      case 'date':
        return [
          { name: '=', label: 'on' },
          { name: '!=', label: 'not on' },
          { name: '<', label: 'before' },
          { name: '<=', label: 'on or before' },
          { name: '>', label: 'after' },
          { name: '>=', label: 'on or after' },
          ...defaultOperators.filter(op => ['null', 'notNull'].includes(op.name)),
        ];
    }
    return defaultOperators;
  };

  const CustomFieldSelector = (props: any) => {
    const { options, value, handleOnChange, path, currentQuery, setFields } = props;
    let groupIndex = 0;
    let ruleIndex = 0;
    let currentGroup = currentQuery.rules[groupIndex];
    // if its a rule with one group
    if(path.length === 1){
      ruleIndex = path[0];
      currentGroup = currentQuery;
    }
    else{
      // Assuming path[0] is the group index and path[1] is the rule index
      ruleIndex = path[1];
      groupIndex = path[0];
      currentGroup = currentQuery.rules[groupIndex];
    }
    let isRuleNew = ruleIndex === currentGroup.rules.length - 1 && currentGroup.rules[ruleIndex].value === '';
    let currentRule = currentGroup.rules[ruleIndex];
    // Get other rules in the same group, excluding the current rule if it's not new
    let otherRules = currentGroup ? currentGroup.rules.filter((index: any) =>
       isRuleNew || index !== ruleIndex) : [];

    // Filter out options that are already used in other rules of the current group,
    // unless the current rule is new
    const filteredOptions = options.filter((option: unknown) =>
      !otherRules.some((rule: unknown) =>
        typeof rule === 'object' && (rule as any).field === (option as any).name
      )
    );

    // if the rule is not new, add the current field to the filtered options
    const field = fields.find((fld) => fld.name === currentRule.field);
    // if its a fields that was added dynamically, add it to the fields list
    if(!field){
      const newField = { name: currentRule.field, label: currentRule.field, value: currentRule.field, datatype: 'text' };
      setFields((prevFields: any) => [...prevFields, newField]);
      filteredOptions.unshift(newField);
    }
    else{
      filteredOptions.unshift(field);
    }


    const reactSelectOptions = filteredOptions.map((option: any) => ({
      label: option.label,
      value: option.name,
    }));

    const handleCreate = (option: any) => {
      // Create a new field and add it to the list of fields
      const newField = { name: option, label: option, value: option, datatype: 'text' };
      setFields((prevFields: any) => [...prevFields, newField]);
      // Update the selected field
      handleOnChange(option);
    }


    return (
      <CreatableSelect
        placeholder="Select attribute or start typing to create a new one"
        isClearable={false}
        onCreateOption={handleCreate}
        value={reactSelectOptions.find((option: any) => option.value === currentRule.field)}
        onChange={(selectedOption) => handleOnChange(selectedOption.value)}
        options={reactSelectOptions}
        styles={{
          control: (provided) => ({
            ...provided,
            width: '150px',
          }),
        }}
      />
    );
  };

  const addRule = (props: any) => {
    // when adding a new Rule, add the rule with the first field that is not already used in the group
    // the available fields are under props.schema.fields and the used fields are under props.rules
    const availableFields = props.schema.fields.filter((fld: any) =>
      !props.rules.some((rule: any) => rule.field === fld.name)
    );
    setQuery(add(query, { field: availableFields[0].name, operator: '=', value: '' }, props.path));
  }

  const validateFormData = (formData: any, query: any) => {
    const errors: Record<string, string> = {};

    if (!formData.ruleName) {
      errors.ruleName = "Rule Name is required";
    }

    if (!formData.timeframe.toString().trim()) {
      errors.timeframe = "Timeframe is required and must be a number";
    } else if (!isNumber(formData.timeframe.toString().trim())) {
      errors.timeframe = "Timeframe must be a number";
    }

    const currentValidationState = customValidator(query);
    for (const [ruleId, validation] of Object.entries(currentValidationState)) {
      if (!validation.valid) {
        errors[`rule_${ruleId}`] = validation.reasons.join(', ');
      }
    }

    return errors;
  };

  const saveRule = () => {
    const errors = validateFormData(formData, query);

    // Check if there are any errors
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    // Reset validation errors
    setValidationErrors({});

    // Send the query to the server and handle the response here
    const sqlQuery = formatQuery(query, 'parameterized_named');
    const celQuery = formatQuery(query, 'cel');
    const apiUrl = getApiURL();
    const timeframeInSeconds = formData.timeframeUnit === 'Seconds' ? formData.timeframe : formData.timeframeUnit === 'Minutes' ? formData.timeframe * 60 : formData.timeframeUnit === 'Hours' ? formData.timeframe * 3600 : formData.timeframe * 86400;
    fetch(`${apiUrl}/rules`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session!.accessToken}`,
      },
      body: JSON.stringify({ sqlQuery, ruleName: formData.ruleName, celQuery, timeframeInSeconds}),
    })
      .then((response) => response.json())
      .then((data) => {
        // Update the rules list
        setRules((prevRules) => [...prevRules, data]);
        // Reset the form
        setFormData({
          ruleName: "New Rule",
          timeframe: 600,
          timeframeUnit: "Seconds",
        });
        // Reset the query
        setQuery(defaultQuery);
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  };

  const updateRule = () => {

    const errors = validateFormData(formData, query);

    // Check if there are any errors
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    // Reset validation errors
    setValidationErrors({});

    // Send the query to the server and handle the response here
    const sqlQuery = formatQuery(query, 'parameterized_named');
    const celQuery = formatQuery(query, 'cel');
    const apiUrl = getApiURL();
    const timeframeInSeconds = formData.timeframeUnit === 'Seconds' ? formData.timeframe : formData.timeframeUnit === 'Minutes' ? formData.timeframe * 60 : formData.timeframeUnit === 'Hours' ? formData.timeframe * 3600 : formData.timeframe * 86400;
    if(activeRow === null){
      return;
    }
    fetch(`${apiUrl}/rules/${activeRow}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session!.accessToken}`,
      },
      body: JSON.stringify({ sqlQuery, ruleName: formData.ruleName, celQuery, timeframeInSeconds}),
    })
      .then((response) => response.json())
      .then((data) => {
        // Reset the form
        setFormData({
          ruleName: "New Rule",
          timeframe: 600,
          timeframeUnit: "Seconds",
        });
        // Reset the query
        setQuery(defaultQuery);
        setActiveRow(null);
        setEditMode(false);
        setRules((prevRules) => {
          const newRules = [...prevRules];
          const index = newRules.findIndex((rule) => rule.id === activeRow);
          newRules[index] = data;
          return newRules;
        })})
      .catch((error) => {
        console.error("Error:", error);
      });
  }


  const handleFieldChange = (fieldName: string, value: string) => {
    setFormData({
      ...formData,
      [fieldName]: value,
    });

    // Clear the validation error for the field when the user edits it
    setValidationErrors((prevErrors) => {
      const newErrors = { ...prevErrors };
      delete newErrors[fieldName];
      return newErrors;
    });
  }

  const isTimeframeNumeric = !isNaN(parseFloat(formData.timeframe.toString())) && isFinite(formData.timeframe);

  const getTimeframeErrorMessage = () => {
    if (formData.timeframe.toString() === '' || formData.timeframe === undefined) {
      return "Timeframe is required";
    } else if (!isTimeframeNumeric) {
      return "Timeframe should be a number";
    }
    return ""; // No error
  };


  const handleEdit = (rule: Rule) => {
    let query = parseCEL(rule.definition_cel);
    // if the query has only one rule or there is only one group, wrap it with a group
    if(query.rules.length === 1 || !("rules" in query.rules[0])){
      query = {
        combinator: 'and',
        rules: [query]
      }
    }
    setQuery(query);
    setFormData({
      ruleName: rule.name,
      timeframe: rule.timeframe,
      timeframeUnit: "Seconds",
      });
      setEditMode(true);
    }

  const handleDelete = () => {
    const confirmed = confirm(
      `Are you sure you want to delete this rule?`
    );
    if (confirmed) {
      const apiUrl = getApiURL();

      fetch(`${apiUrl}/rules/${activeRow}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        }})
        .then((response) => response.json())
        .then((data) => {
          // Delete Ok, remove from rules
          const newRules = rules.filter((rule) => rule.id !== activeRow);
          setRules(newRules);
          setActiveRow(null);
          setEditMode(false);
          setQuery(defaultQuery);
          setFormData({
            ruleName: "New Rule",
            timeframe: 600,
            timeframeUnit: "Seconds",
          });
        })
        .catch((error) => {
          console.error("Error:", error);
        });
    }
  }

  const options = [
    { value: 'Seconds', label: 'Seconds' },
    { value: 'Minutes', label: 'Minutes' },
    { value: 'Hours', label: 'Hours' },
    { value: 'Days', label: 'Days' },
  ];


  const CustomRemoveRuleAction = (props: any) => {
    // if its the only rule in the group, delete the group

    const handleOnClick = (e: any) => {
      // get the group index
      const groupIndex = props.path[0];
      // get the group
      const group = findPath([groupIndex], query) as RuleGroupType;
      // if its the only rule in the group, delete the group
      if (group.rules.length === 1) {
        setQuery(remove(query, [groupIndex]));
      // else, delete the rule
      } else {
        props.handleOnClick(e)
      }
    }

    return (
      <Button icon={FaRegTrashAlt} size="xs" onClick={handleOnClick} color="orange">
      </Button>
    );
  }

  const handleRowClick = (rule: Rule) => {
    // if the user clicks on the same row, collapse it
    if(activeRow === rule.id){
      setActiveRow(null);
      setEditMode(false);
      setQuery(defaultQuery);
      setFormData({
        ruleName: "New Rule",
        timeframe: 600,
        timeframeUnit: "Seconds",
      });
      setExpandedRows(prevExpandedRows => ({
        ...prevExpandedRows,
        [rule.id]: !prevExpandedRows[rule.id]
      }));
      return;

    }
    // if the user clicks on a different row, collapse the previous one and expand the new one
    else{
      setExpandedRows(prevExpandedRows => ({
        ...prevExpandedRows,
        [rule.id]: true
      }));
      setActiveRow(rule.id);
      handleEdit(rule);
    }
    // clean the errors
    setValidationErrors({});
  };

  const canCreateRule = () => {
    // Check if the query has at least one rule
    return query.rules.length > 0;
  }

  /**
  * Converts a timestamp to a formatted date string.
 * @param {string | number} timestamp - The timestamp to convert, can be a string or number.
 * @returns {string} - The formatted date string.
 */
    function getDate(timestamp: string) {
      const date = new Date(timestamp);
      const hours = date.getHours().toString().padStart(2, '0');
      const minutes = date.getMinutes().toString().padStart(2, '0');
      const seconds = date.getSeconds().toString().padStart(2, '0');

      // Format: DD/MM/YYYY HH:MM:SS
      return `${hours}:${minutes}:${seconds}`;
    }


    function flattenDistribution(distribution: Distribution) {
      // Object to hold combined data for each timestamp
      const combinedDataByTimestamp: CombinedData = {};

      for (let group_id in distribution) {
        // Replace 'none' with 'Number of Alerts'
        const groupData = distribution[group_id];
        if (group_id === "none") {
          group_id = "Number of Alerts";
        }

        for (const timestamp in groupData) {
          // Ensure we have an object for this timestamp
          if (!combinedDataByTimestamp[timestamp]) {
            // tell linter ignore
            // eslint-disable-next-line
            // @ts-ignore
            combinedDataByTimestamp[timestamp] = { date: getDate(timestamp) };
          }
          // Add the current group's value to this timestamp's object
          combinedDataByTimestamp[timestamp][group_id] = groupData[timestamp];
        }
      }

      // Convert the combined data object back into an array
      const flatData = Object.values(combinedDataByTimestamp);

      return flatData;
    }




  return (
      <Card  className="mt-10 p-4 md:p-10 mx-auto">
        <Flex style={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'stretch' }}>
          <Card style={{ width: '50%' }}>
            <Title>Rule Builder</Title>
            <Subtitle>Rule name</Subtitle>
            <div style={{ maxWidth: '50%' }}>
              <TextInput
                  error={formData.ruleName? false : true}
                  errorMessage="Error name is required"
                  placeholder="Rule Name"
                  value={formData.ruleName}
                  onChange={(e) => handleFieldChange("ruleName", e.target.value)}
                />
              </div>

              <div className="mt-4 mr-2">
                <Subtitle>Timeframe</Subtitle>
                <Flex style={{ maxWidth: '50%' }} className="items-center gap-4">
                  <TextInput
                    error={formData.timeframe.toString() === '' || !isTimeframeNumeric}
                    errorMessage={getTimeframeErrorMessage()}
                    placeholder="Timeframe"
                    value={formData.timeframe.toString()}
                    onChange={(e) => handleFieldChange("timeframe", e.target.value)}
                  />
                    <Select
                        value={{ value: formData.timeframeUnit, label: formData.timeframeUnit }}
                        onChange={(selectedOption) => {
                          if (selectedOption) {
                            handleFieldChange("timeframeUnit", selectedOption.value);
                          }
                        }}
                        options={options}
                        styles={{
                          control: (provided) => ({
                            ...provided,
                            width: '200px',
                          }),
                        }}
                      />
                </Flex>
              </div>
              <QueryBuilder
              fields={fields} query={query} getOperators={getOperators} onQueryChange={q => setQuery(q)}
              addRuleToNewGroups
              controlElements={{
                valueEditor: valueEditor,
                fieldSelector: (props) => <CustomFieldSelector {...props} currentQuery={query} setFields={setFields} />,
                operatorSelector: CustomOperatorSelector,
                combinatorSelector: CustomCombinatorSelector,
                addGroupAction: CustomAddGroupAction,
                addRuleAction: (props) => <CustomAddRuleAction {...props} addRule={addRule} />,
                removeRuleAction: CustomRemoveRuleAction
              }}
              validator={customValidator}
              controlClassnames={{
                queryBuilder: 'queryBuilder-branches bg-orange-300 !important rounded-lg shadow-xl',
                ruleGroup: 'rounded-lg bg-orange-300 bg-opacity-10 mt-4  !important',
                combinators: 'bg-orange-400 text-white rounded-l-full p-1 shadow',
                addRule: 'bg-orange-400 text-white rounded-none p-1 shadow',
                addGroup: 'bg-orange-400 text-white rounded-r-full p-1 shadow',
                fields: 'bg-white text-orange-400 rounded-l-full p-1 shadow',
                operators: 'bg-white text-orange-400 rounded-none p-1 shadow',
                value: 'bg-white text-orange-400 rounded-r-full p-1 shadow w-32',
                removeGroup: 'p-1 ml-auto',
                removeRule: 'p-1 ml-auto',
              }}
              />
              <div className="text-right">
                {!editMode &&
                  <Button tooltip={canCreateRule()? "": "At least one rule is required"} className="mt-2" color="orange" disabled={!canCreateRule()} onClick={saveRule}>
                    Create Rule
                  </Button>
                }
                {editMode &&
                <div>
                  <Button className="mt-2" color="orange" onClick={() => handleDelete()} title="Delete">
                      Delete Rule
                  </Button>
                  <Button className="mt-2 ml-2" color="orange" onClick={updateRule}>
                    Update Rule
                  </Button>
                  <Button className="mt-2 ml-2" color="orange" onClick={() => {setActiveRow(null); setEditMode(false); setQuery(defaultQuery); setFormData({
                        ruleName: "New Rule",
                        timeframe: 600,
                        timeframeUnit: "Seconds",
                      });}}>
                    Cancel
                  </Button>
                  </div>
                }
              </div>
          </Card>
          <Card style={{ width: '50%',  marginLeft: '1rem'}}>
            {loadingRules ? (<Loading />) : (
                <>
                <Title>Rules</Title>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Rule Name</TableHeaderCell>
                    <TableHeaderCell>Definition</TableHeaderCell>
                    <TableHeaderCell>Created By</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rules && rules.length > 0 ? rules.map((rule) => (
                    <>
                      <TableRow key={rule.id} onClick={() => handleRowClick(rule)} className={`cursor-pointer ${activeRow === rule.id ? 'bg-gray-100' : 'hover:bg-gray-100'}`} >
                        <TableCell className="whitespace-normal break-words">{rule.name}</TableCell>
                        <TableCell className="whitespace-normal break-words">{rule.definition_cel}</TableCell>
                        <TableCell>{rule.created_by}</TableCell>
                      </TableRow>
                      {expandedRows[rule.id] && (
                        <TableRow key={`details-${rule.id}`}>
                          <TableCell colSpan={6}>
                            <div>
                              <Subtitle>Timeframe: {rule.timeframe}</Subtitle>
                              <Subtitle className="mt-1">Created by: {rule.created_by}</Subtitle>
                              <Subtitle className="mt-1">Creation Time: {rule.creation_time}</Subtitle>

                              {rule.updated_by && <Subtitle className="mt-1">Updated by: {rule.updated_by}</Subtitle>}
                              {rule.update_time && <Subtitle className="mt-1">Update Time: {rule.update_time}</Subtitle>}
                              {
                                rule.distribution && Object.keys(rule.distribution).length > 0 ? (
                                  <>
                                    <div className="text-center">
                                      <AreaChart
                                        data={flattenDistribution(rule.distribution)}
                                        index="timestamp"
                                        yAxisWidth={65}
                                        categories={Object.keys(rule.distribution).map(key => key === "none" ? "Number of Alerts" : key)}
                                        enableLegendSlider={true}
                                      />
                                      <div className="mt-2"> {/* Adjust margin-top as needed */}
                                        <Text color="orange" className="inline-block mx-auto">Alerts hits (24 hours)</Text>
                                      </div>
                                    </div>
                                  </>
                                ) : (
                                  <Text className="mt-2" color="red">No alerts matched this rule in the last 24 hours.</Text>
                                )
                              }
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  )) :(
                    <>
                      <TableRow className="italic text-gray-400">
                        <TableCell className="whitespace-normal break-words">Group Grafana and DB alerts</TableCell>
                        <TableCell className="whitespace-normal break-words">(source == &quot;grafana&quot; && severity ==&quot;high&quot;) && (service == &quot;database&quot;)</TableCell>
                        <TableCell>noc@example.com</TableCell>
                      </TableRow>
                      <TableRow>
                          <TableCell colSpan={6}>
                            <div>
                              <Subtitle className="whitespace-normal break-words">A simple example to demonstrate how Rules works.  Begin grouping alerts by creating your first Rule.</Subtitle>
                            </div>
                          </TableCell>
                        </TableRow>
                    </>
                  )}
                </TableBody>
              </Table>
                </>
            )}

            </Card>
          </Flex>
      </Card>
  );
}
