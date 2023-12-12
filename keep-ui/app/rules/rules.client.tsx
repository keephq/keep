'use client';
import React, { useState, useEffect } from "react";
import { Card, Flex, Title, Subtitle, TextInput, Select, SelectItem, Button, Table, TableCell, TableBody, TableRow, TableHead, TableHeaderCell } from "@tremor/react";
import QueryBuilder, { defaultValidator, RuleGroupType, RuleType, Field, formatQuery, defaultOperators, ActionElement} from 'react-querybuilder';
// import 'react-querybuilder/dist/query-builder.scss';
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import Loading from "../loading";
import './query-builder.scss';

const getOperators = (fieldName: string) => {
  const field = fields.find(fld => fld.name === fieldName);

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

// Todo: validation
// Todo: dynamic
const fields: Field[] = [
  { name: 'source', label: 'source', datatype: 'text'},
  { name: 'severity', label: 'severity', datatype: 'text' },
  { name: 'service', label: 'service', datatype: 'text' },
];

const CustomValueEditor = (props: any) => {
  const { value, handleOnChange, operator } = props;

  // Define an array of operators that do not require the input
  const operatorsWithoutInput = [ "null", "notNull"]; // Add more as needed

  // Check if the selected operator is in the operatorsWithoutInput array
  const isInputHidden = operatorsWithoutInput.includes(operator);

  return (
    <>
      {!isInputHidden && (
        <TextInput
          type="text"
          value={value}
          onChange={(e) => handleOnChange(e.target.value)}
          // Add your Tremor TextInput component props here
        />
      )}
    </>
  );
};

const CustomCmbinatorSelector = (props: any) => {
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
  return (
    <Select
      className="w-auto"
      enableClear={false}
      value={value}
      onChange={(e) => handleOnChange(e)} // Update the selected field
      // Pass the options as children to the Select component
    >
      {options.map((option: any) => (
        <SelectItem key={option.name} value={option.name}>
          {option.label}
        </SelectItem>
      ))}
    </Select>
  );
};

const CustomFieldSelector = (props: any) => {
  const { options, value, handleOnChange, path, currentQuery } = props;

  // Assuming path[0] is the group index and path[1] is the rule index
  // let currentGroup = currentQuery.rules[path[0]];
  // let isRuleNew = path[1] === currentGroup.rules.length - 1 && currentGroup.rules[path[1]].value === '';

  // Get other rules in the same group, excluding the current rule if it's not new
  //let otherRules = currentGroup ? currentGroup.rules.filter((index: any) =>
  //  isRuleNew || index !== path[1]) : [];

  // Filter out options that are already used in other rules of the current group,
  // unless the current rule is new
  //const filteredOptions = options.filter((option: unknown) =>
  //  !otherRules.some((rule: unknown) =>
  //    typeof rule === 'object' && (rule as any).field === (option as any).name
  //  )
  //);

  let filteredOptions = options;
  return (
    <Select
      className="w-auto"
      enableClear={false}
      value={value}
      onChange={(e) => handleOnChange(e)} // Update the selected field
      // Pass the options as children to the Select component
    >
      {filteredOptions.map((option: any) => (
        <SelectItem key={option.name} value={option.name}>
          {option.label}
        </SelectItem>
      ))}
    </Select>
  );
};

const CustomAddGroupAction = (props: any) => {
  if(props.level > 0){
    return null;
  }

  return (
    <Button onClick={props.handleOnClick} color="orange">
      New Group
    </Button>
  );
};

const CustomAddRuleAction = (props: any) => {
  const { label, handleOnClick } = props;

  if (props.level === 0) {
    return null;
  }

  return (
    <Button onClick={handleOnClick} color="orange">
      New Condition
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


export default function Page() {
  // Use the extended type for the query state
  const [query, setQuery] = useState<RuleGroupType>({
    combinator: 'and',
    rules: [
      {
        combinator: 'and', // or 'or' depending on your logic
        rules: [
          { field: 'source', operator: '=', value: 'sentry' }
        ],
      },
      {
        combinator: 'and', // or 'or' depending on your logic
        rules: [
          { field: 'source', operator: '=', value: 'grafana' },
          { field: 'severity', operator: '=', value: 'critical' }
        ],
      }
    ],
  });
  const [formData, setFormData] = useState({
    ruleName: "Rule Name",
    timeframe: 600,
    timeframeUnit: "Seconds",
  });
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>(
    {}
  );
  const { data: session, status } = useSession();
  const [rules, setRules] = useState<Rule[]>([]);


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


  const saveRule = () => {
    const errors: Record<string, string> = {};

    if (!formData.ruleName) {
      errors.ruleName = "Rule Name is required";
    }

    if (!formData.timeframe.toString().trim()) {
      errors.timeframe = "Timeframe is required and must be a number";
    } else if (!isNumber(formData.timeframe.toString().trim())) {
      errors.timeframe = "Timeframe must be a number";
    }

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
        // Handle the response data here
        console.log("Server Response:", data);
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

  return (
      <Card  className="mt-10 p-4 md:p-10 mx-auto">
          <Card>
            <Title>Rule Builder</Title>
            <Subtitle>define the rules that will create your dynamic alerts</Subtitle>
            <Flex style={{ maxWidth: '50%' }}>
              <TextInput
                  className={`mt-4 mr-2 ${
                    validationErrors.ruleName ? "border-red-500" : ""
                  }`}
                  placeholder="Rule Name"
                  value={formData.ruleName}
                  onChange={(e) => handleFieldChange("ruleName", e.target.value)}
                />
              </Flex>
              <Flex style={{ maxWidth: '50%' }}>
                <TextInput
                  className={`mt-4 mr-2 ${
                    validationErrors.timeframe ? "border-red-500" : ""
                  }`}
                  placeholder="Timeframe"
                  value={formData.timeframe.toString()}
                  onChange={(e) =>
                    handleFieldChange("timeframe", e.target.value)
                  }
                />
                <Select
                  className="mt-4 mr-2"
                  defaultValue={formData.timeframeUnit}
                  onValueChange={(value: string) => handleFieldChange("timeframeUnit", value)}
                >
                  <SelectItem value="Seconds">Seconds</SelectItem>
                  <SelectItem value="Minutes">Minutes</SelectItem>
                  <SelectItem value="Hours">Hours</SelectItem>
                  <SelectItem value="Days">Days</SelectItem>
                </Select>
              </Flex>

              <QueryBuilder
              fields={fields} query={query} getOperators={getOperators} onQueryChange={q => setQuery(q)}
              addRuleToNewGroups
              controlElements={{
                valueEditor: CustomValueEditor,
                fieldSelector: (props) => <CustomFieldSelector {...props} currentQuery={query} />,
                operatorSelector: CustomOperatorSelector,
                combinatorSelector: CustomCmbinatorSelector,
                addGroupAction: CustomAddGroupAction,
                addRuleAction: CustomAddRuleAction,
              }}
              validator={defaultValidator}
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
            <Button className="mt-4 mr-2" color="orange" onClick={saveRule}>
              Save Rule
            </Button>
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
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
          </Card>
      </Card>
  );
}
