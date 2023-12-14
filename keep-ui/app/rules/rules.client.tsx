'use client';
import React, { useState, useEffect, useMemo } from "react";
import { Card, Flex, Title, Subtitle, TextInput, Button, Table, TableCell, TableBody, TableRow, TableHead, TableHeaderCell } from "@tremor/react";
import Select from 'react-select';
import CreatableSelect from 'react-select/creatable';
import QueryBuilder, { add, remove, RuleGroupTypeAny, RuleGroupType, ValidationMap, Field, formatQuery, defaultOperators, parseCEL, QueryValidator, findPath} from 'react-querybuilder';
// import 'react-querybuilder/dist/query-builder.scss';
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import './query-builder.scss';
import { FaRegTrashAlt } from "react-icons/fa";
import { MdEdit } from "react-icons/md";


const customValidator: QueryValidator = (query: RuleGroupTypeAny): ValidationMap => {
  const validationMap: ValidationMap = {};

  const checkRules = (rules) => {
    rules.forEach(rule => {
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
      {!isInputHidden && (
        <TextInput
          error={!isValid}
          errorMessage={errorMessage}
          type="text"
          value={value}
          onChange={(e) => handleOnChangeInternal(e.target.value)}
        />
      )}
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

const CustomOperatorSelector = (props) => {
  const { options, value, handleOnChange } = props;

  // Convert options to the format expected by react-select
  const reactSelectOptions = options.map((option) => ({
    label: option.label,
    value: option.name,
  }));

  return (
    <Select
      className="w-auto"
      isClearable={false}
      value={reactSelectOptions.find((option) => option.value === value)}
      onChange={(selectedOption) => handleOnChange(selectedOption.value)} // Update the selected field
      options={reactSelectOptions}
      styles={{
        control: (provided) => ({
          ...provided,
          width: '200px',
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
    <Button onClick={props.handleOnClick} color="orange">
      Add Alerts Group
    </Button>
  );
};

const CustomAddRuleAction = (props) => {
  const { label, handleOnClick, addRule } = props;

  if (props.level === 0) {
    return null;
  }

  const handleAddRuleClick = () => {
    addRule(props);
  };

  const availableFields = props.schema.fields.filter((fld) =>
      !props.rules.some((rule) => rule.field === fld.name)
    );

  return (
    <Button onClick={handleAddRuleClick} color="orange" disabled={availableFields.length === 0 ? true: false}>
      Add Condition
    </Button>
  );
};




interface Rule {
  id: number;
  name: string;
  definition: string;
  definition_cel: string;
  timeframe: number;
  created_by: string;
  creation_time: string;
  updated_by: string;
  update_time: string

}

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


  const { data: session, status } = useSession();
  const [rules, setRules] = useState<Rule[]>([]);
  const [editMode, setEditMode] = useState(false);

  const valueEditor = useMemo(() => {
    return (props) => <CustomValueEditor {...props} validationErrors={validationErrors}/>;
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

    // Assuming path[0] is the group index and path[1] is the rule index
    let currentGroup = currentQuery.rules[path[0]];
    let isRuleNew = path[1] === currentGroup.rules.length - 1 && currentGroup.rules[path[1]].value === '';
    let currentRule = currentGroup.rules[path[1]];
    // Get other rules in the same group, excluding the current rule if it's not new
    let otherRules = currentGroup ? currentGroup.rules.filter((index: any) =>
       isRuleNew || index !== path[1]) : [];

    // Filter out options that are already used in other rules of the current group,
    // unless the current rule is new
    const filteredOptions = options.filter((option: unknown) =>
      !otherRules.some((rule: unknown) =>
        typeof rule === 'object' && (rule as any).field === (option as any).name
      )
    );

    // if the rule is not new, add the current field to the filtered options
    filteredOptions.unshift(fields.find((fld) => fld.name === currentRule.field));


    const reactSelectOptions = filteredOptions.map((option) => ({
      label: option.label,
      value: option.name,
    }));

    const handleCreate = (option: any) => {
      // Create a new field and add it to the list of fields
      const newField = { name: option, label: option, value: option, datatype: 'text' };
      setFields((prevFields) => [...prevFields, newField]);
      // Update the selected field
      handleOnChange(option);
    }


    return (
      <CreatableSelect
        className="w-auto"
        isClearable={false}
        onCreateOption={handleCreate}
        value={reactSelectOptions.find((option) => option.value === currentRule.field)}
        onChange={(selectedOption) => handleOnChange(selectedOption.value)}
        options={reactSelectOptions}
        styles={{
          control: (provided) => ({
            ...provided,
            width: '200px',
          }),
        }}
      />
    );
  };

  const addRule = (props) => {
    // when adding a new Rule, add the rule with the first field that is not already used in the group
    // the available fields are under props.schema.fields and the used fields are under props.rules
    const availableFields = props.schema.fields.filter((fld) =>
      !props.rules.some((rule) => rule.field === fld.name)
    );
    setQuery(add(query, { field: availableFields[0].name, operator: '=', value: '' }, props.path));
  }


  const saveRule = () => {
    const errors: Record<string, string> = {};

    // Validate form data
    if (!formData.ruleName) {
      errors.ruleName = "Rule Name is required";
    }

    if (!formData.timeframe.toString().trim()) {
      errors.timeframe = "Timeframe is required and must be a number";
    } else if (!isNumber(formData.timeframe.toString().trim())) {
      errors.timeframe = "Timeframe must be a number";
    }

    // Validate the query itself
    const currentValidationState = customValidator(query);

    // Include rule-specific validation errors
    for (const [ruleId, validation] of Object.entries(currentValidationState)) {
      if (!validation.valid) {
        // Assuming validation.reasons is an array of string messages
        errors[`rule_${ruleId}`] = validation.reasons.join(', ');
      }
    }

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
    const query = parseCEL(rule.definition_cel);
    setQuery(query);
    setFormData({
      ruleName: rule.name,
      timeframe: rule.timeframe,
      timeframeUnit: "Seconds",
      });
      setEditMode(true);
    }

  const handleDelete = (id: number) => {
    const confirmed = confirm(
      `Are you sure you want to delete this rule?`
    );
    if (confirmed) {
      const apiUrl = getApiURL();

      fetch(`${apiUrl}/rules/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        }})
        .then((response) => response.json())
        .then((data) => {
          // Delete Ok, remove from rules
          const newRules = rules.filter((rule) => rule.id !== id);
          setRules(newRules);
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


  const CustomRemoveRuleAction = (props) => {
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

  return (
      <Card  className="mt-10 p-4 md:p-10 mx-auto">
          <Card>
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
                <Flex style={{ maxWidth: '50%' }} className="items-center gap-4"> {/* Adjust gap as needed */}
                  <TextInput
                    error={formData.timeframe.toString() === '' || !isTimeframeNumeric}
                    errorMessage={getTimeframeErrorMessage()}
                    placeholder="Timeframe"
                    value={formData.timeframe.toString()}
                    onChange={(e) => handleFieldChange("timeframe", e.target.value)}
                  />
                    <Select
                        value={{ value: formData.timeframeUnit, label: formData.timeframeUnit }}
                        onChange={(selectedOption) => handleFieldChange("timeframeUnit", selectedOption.value)}
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
                ruleGroup: 'rounded-lg bg-orange-300 bg-opacity-10 mt-4 !important',
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
                <Button className="mt-2" color="orange" onClick={saveRule}>
                  {editMode ? "Update Rule" : "Create Rule"}
                </Button>
                {editMode &&
                  <Button className="mt-2 ml-2" color="orange" onClick={() => {setEditMode(false); setQuery(defaultQuery); setFormData({
                    ruleName: "New Rule",
                    timeframe: 600,
                    timeframeUnit: "Seconds",
                  });}}>
                    Cancel
                  </Button>
                }
              </div>
          </Card>
          <Card className="mt-8">
            <Title>Rules</Title>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Rule Name</TableHeaderCell>
                    <TableHeaderCell>Definition</TableHeaderCell>
                    <TableHeaderCell>Timeframe</TableHeaderCell>
                    <TableHeaderCell>Created By</TableHeaderCell>
                    <TableHeaderCell>Creation Time</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rules && rules.map((rule) => (
                    <TableRow key={rule.id}>
                      <TableCell>{rule.name}</TableCell>
                      <TableCell>{rule.definition_cel}</TableCell>
                      <TableCell>{rule.timeframe} Seconds</TableCell>
                      <TableCell>{rule.created_by}</TableCell>
                      <TableCell>{rule.creation_time}</TableCell>
                      <TableCell>
                        <Button className="mr-1" color="orange" icon={FaRegTrashAlt} size="xs" onClick={() => handleDelete(rule.id)} title="Delete">

                        </Button>
                        <Button  color="orange" icon={MdEdit} size="xs" onClick={() => handleEdit(rule)} title="Edit">

                        </Button>
                    </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
          </Card>
      </Card>
  );
}
