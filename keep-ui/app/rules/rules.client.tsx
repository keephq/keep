'use client';
import React, { useState } from "react";
import { Card, Flex, Title, Subtitle, TextInput, Select, SelectItem, Button} from "@tremor/react";
import QueryBuilder, { RuleGroupType, RuleType, Field, formatQuery, defaultOperators, ActionElement} from 'react-querybuilder';
// import 'react-querybuilder/dist/query-builder.scss';
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
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

const fields: Field[] = [
  { name: 'source', label: 'source', datatype: 'text'},
  { name: 'severity', label: 'severity', datatype: 'text' },
];

const CustomValueEditor = (props) => {
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

const CustomFieldSelector = (props) => {
  const { options, value, handleOnChange } = props;

  return (
    <Select
      className="w-auto"
      enableClear={false}
      value={value}
      onChange={(e) => handleOnChange(e)} // Update the selected field
      // Pass the options as children to the Select component
    >
      {options.map((option) => (
        <SelectItem key={option.name} value={option.name}>
          {option.label}
        </SelectItem>
      ))}
    </Select>
  );
};

const CustomAddGroupAction = (props) => {
  const { label, handleOnClick } = props;

  if(props.level > 0){
    return null;
  }
  return (
    <Button onClick={handleOnClick} color="orange">
      New Group
    </Button>
  );
};

const CustomAddRuleAction = (props) => {
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
  const [ruleName, setRuleName] = useState<string>('Rule Name');
  const [timeframe, setTimeframe] = useState<number>(600);
  const [timeframeUnit, setTimeframeUnit] = useState<string>('Seconds');

  const { data: session, status } = useSession();

  const testRule = () => {
    // Send the query to the server and handle the response here
    const sqlQuery = formatQuery(query, 'parameterized_named');
    const celQuery = formatQuery(query, 'cel');
    const apiUrl = getApiURL();
    const timeframeInSeconds = timeframeUnit === 'Seconds' ? timeframe : timeframeUnit === 'Minutes' ? timeframe * 60 : timeframeUnit === 'Hours' ? timeframe * 3600 : timeframe * 86400;
    fetch(`${apiUrl}/rules`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session!.accessToken}`,
      },
      body: JSON.stringify({ sqlQuery, ruleName: ruleName, celQuery, timeframeInSeconds}),
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

  return (
      <Card  className="mt-10 p-4 md:p-10 mx-auto">
          <Card>
            <Title>Rule Builder</Title>
            <Subtitle>define the rules that will create your dynamic alerts</Subtitle>
            <Flex>
                <TextInput className="mt-4 mr-2" placeholder="Rule Name"  defaultValue="Rule Name" onChange={(e) => setRuleName(e.target.value)} />
                <Flex>
                  <TextInput className="mt-4 mr-2" placeholder="Timeframe"  onChange={(e) => setRuleName(e.target.value)} />
                  <Select
                    className="mt-4 mr-2"
                    defaultValue="Minutes"
                    onValueChange={(value: string) => setTimeframeUnit(value)}
                  >
                    <SelectItem value="Seconds">Seconds</SelectItem>
                    <SelectItem value="Minutes">Minutes</SelectItem>
                    <SelectItem value="Hours">Hours</SelectItem>
                    <SelectItem value="Days">Days</SelectItem>
                  </Select>
                </Flex>
            </Flex>
              <QueryBuilder
              fields={fields} query={query} getOperators={getOperators} onQueryChange={q => setQuery(q)}

              controlElements={{
                valueEditor: CustomValueEditor,
                fieldSelector: CustomFieldSelector,
                operatorSelector: CustomFieldSelector,
                combinatorSelector: CustomFieldSelector,
                addGroupAction: CustomAddGroupAction,
                addRuleAction: CustomAddRuleAction,
              }}
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
            <Button className="mt-4 mr-2" color="orange" onClick={testRule}>
              Test Rule
            </Button>
            <Button className="mt-4 mr-2" color="orange" onClick={() => console.log(JSON.stringify(query))}>Save Rule</Button>
          </Card>
          <Card className="mt-8">
            <Flex>
              <Title>Rules</Title>
              {/* Add your table of rules here */}
            </Flex>
          </Card>
      </Card>
  );
}
