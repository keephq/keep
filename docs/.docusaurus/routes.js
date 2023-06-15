import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/markdown-page',
    component: ComponentCreator('/markdown-page', 'aa7'),
    exact: true
  },
  {
    path: '/',
    component: ComponentCreator('/', '1e3'),
    routes: [
      {
        path: '/',
        component: ComponentCreator('/', 'b46'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/conditions',
        component: ComponentCreator('/category/conditions', '53e'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/documentation',
        component: ComponentCreator('/category/documentation', '00f'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/examples',
        component: ComponentCreator('/category/examples', '0d8'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/functions',
        component: ComponentCreator('/category/functions', '3eb'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/providers',
        component: ComponentCreator('/category/providers', '400'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/syntax',
        component: ComponentCreator('/category/syntax', 'b66'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/category/throttles',
        component: ComponentCreator('/category/throttles', 'f32'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/conditions/assert',
        component: ComponentCreator('/conditions/assert', 'd42'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/conditions/stddev',
        component: ComponentCreator('/conditions/stddev', '49f'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/conditions/threshold',
        component: ComponentCreator('/conditions/threshold', '589'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/conditions/what-is-a-condition',
        component: ComponentCreator('/conditions/what-is-a-condition', '6e8'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/deployment',
        component: ComponentCreator('/deployment', 'dcd'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/examples/multistep-alert-example',
        component: ComponentCreator('/examples/multistep-alert-example', 'd41'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/all',
        component: ComponentCreator('/functions/all', 'e1e'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/datetime_compare',
        component: ComponentCreator('/functions/datetime_compare', 'c44'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/diff',
        component: ComponentCreator('/functions/diff', '71c'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/first',
        component: ComponentCreator('/functions/first', 'f69'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/len',
        component: ComponentCreator('/functions/len', '84e'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/split',
        component: ComponentCreator('/functions/split', '32f'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/to_utc',
        component: ComponentCreator('/functions/to_utc', '681'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/utcnow',
        component: ComponentCreator('/functions/utcnow', '0dc'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/functions/what-is-a-function',
        component: ComponentCreator('/functions/what-is-a-function', 'c88'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/cloudwatch-logs',
        component: ComponentCreator('/providers/documentation/cloudwatch-logs', '112'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/cloudwatch-metrics',
        component: ComponentCreator('/providers/documentation/cloudwatch-metrics', '854'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/console',
        component: ComponentCreator('/providers/documentation/console', '5af'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/discord',
        component: ComponentCreator('/providers/documentation/discord', '97e'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/elastic',
        component: ComponentCreator('/providers/documentation/elastic', 'c80'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/http',
        component: ComponentCreator('/providers/documentation/http', '817'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/mock',
        component: ComponentCreator('/providers/documentation/mock', '4c4'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/mysql',
        component: ComponentCreator('/providers/documentation/mysql', '5b8'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/new-relic',
        component: ComponentCreator('/providers/documentation/new-relic', 'e44'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/opsgenie',
        component: ComponentCreator('/providers/documentation/opsgenie', '017'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/pagerduty',
        component: ComponentCreator('/providers/documentation/pagerduty', 'eae'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/postgresql',
        component: ComponentCreator('/providers/documentation/postgresql', '489'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/pushover',
        component: ComponentCreator('/providers/documentation/pushover', '6fa'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/sentry',
        component: ComponentCreator('/providers/documentation/sentry', '10d'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/slack',
        component: ComponentCreator('/providers/documentation/slack', 'f1b'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/snowflake',
        component: ComponentCreator('/providers/documentation/snowflake', '64d'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/ssh',
        component: ComponentCreator('/providers/documentation/ssh', '5bb'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/teams',
        component: ComponentCreator('/providers/documentation/teams', '443'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/telegram',
        component: ComponentCreator('/providers/documentation/telegram', '584'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/template',
        component: ComponentCreator('/providers/documentation/template', 'ee6'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/documentation/zenduty',
        component: ComponentCreator('/providers/documentation/zenduty', '6a7'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/getting-started',
        component: ComponentCreator('/providers/getting-started', 'a7d'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/new-provider',
        component: ComponentCreator('/providers/new-provider', 'a4c'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/providers/what-is-a-provider',
        component: ComponentCreator('/providers/what-is-a-provider', 'e1c'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/quick-start',
        component: ComponentCreator('/quick-start', '519'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/syntax/context',
        component: ComponentCreator('/syntax/context', '5e0'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/syntax/foreach',
        component: ComponentCreator('/syntax/foreach', '326'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/syntax/state',
        component: ComponentCreator('/syntax/state', '75f'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/syntax/syntax',
        component: ComponentCreator('/syntax/syntax', 'aa5'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/throttles/one-until-resolved',
        component: ComponentCreator('/throttles/one-until-resolved', '4ba'),
        exact: true,
        sidebar: "tutorialSidebar"
      },
      {
        path: '/throttles/what-is-throttle',
        component: ComponentCreator('/throttles/what-is-throttle', '7e2'),
        exact: true,
        sidebar: "tutorialSidebar"
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
