# Providers Overview

Providers are core components of Keep that allows Keep to either query data, send notifications, get alerts from or manage third-party tools.

These third-party tools include, among others, Datadog, Cloudwatch, and Sentry for data querying and/or alert management, and Slack, Resend, Twilio, and PagerDuty for notifications/incidents.

By leveraging Keep Providers, users are able to deeply integrate Keep with the tools they use and trust, providing them with a flexible and powerful way to manage these tools with ease and from a single pane.

## Available Providers

### CI/CD & GitOps
- [Airflow](/docs/providers/documentation/airflow-provider.mdx)
- [ArgoCD](/docs/providers/documentation/argocd-provider.mdx)
- [Flux CD](/docs/providers/documentation/fluxcd-provider.mdx)
- [GitHub](/docs/providers/documentation/github-provider.mdx)
- [Github Workflows](/docs/providers/documentation/github_workflows_provider.mdx)
- [GitLab](/docs/providers/documentation/gitlab-provider.mdx)
- [GitLab Pipelines](/docs/providers/documentation/gitlabpipelines-provider.mdx)
- [LinearB](/docs/providers/documentation/linearb-provider.mdx)

### Infrastructure & Kubernetes
- [Azure AKS](/docs/providers/documentation/aks-provider.mdx)
- [Cilium](/docs/providers/documentation/cilium-provider.mdx)
- [EKS](/docs/providers/documentation/eks-provider.mdx)
- [Google Kubernetes Engine](/docs/providers/documentation/gke-provider.mdx)
- [Kubernetes](/docs/providers/documentation/kubernetes-provider.mdx)
- [NetBox](/docs/providers/documentation/netbox-provider.mdx)
- [Openshift](/docs/providers/documentation/openshift-provider.mdx)

### Monitoring & Observability
- [Azure Monitor](/docs/providers/documentation/azuremonitoring-provider.mdx)
- [CloudWatch](/docs/providers/documentation/cloudwatch-provider.mdx)
- [Dash0](/docs/providers/documentation/dash0-provider.mdx)
- [Datadog](/docs/providers/documentation/datadog-provider.mdx)
- [Dynatrace](/docs/providers/documentation/dynatrace-provider.mdx)
- [Elastic](/docs/providers/documentation/elastic-provider.mdx)
- [GCP Monitoring](/docs/providers/documentation/gcpmonitoring-provider.mdx)
- [Grafana](/docs/providers/documentation/grafana-provider.mdx)
- [Grafana Incident](/docs/providers/documentation/grafana_incident-provider.mdx)
- [Grafana Loki](/docs/providers/documentation/grafana_loki-provider.mdx)
- [Grafana OnCall](/docs/providers/documentation/grafana_oncall-provider.mdx)
- [Graylog](/docs/providers/documentation/graylog-provider.mdx)
- [New Relic](/docs/providers/documentation/newrelic-provider.mdx)
- [OpenObserve](/docs/providers/documentation/openobserve-provider.mdx)
- [Prometheus](/docs/providers/documentation/prometheus-provider.mdx)
- [SignalFX](/docs/providers/documentation/signalfx-provider.mdx)
- [Splunk](/docs/providers/documentation/splunk-provider.mdx)
- [SumoLogic](/docs/providers/documentation/sumologic-provider.mdx)
- [VictoriaLogs](/docs/providers/documentation/victorialogs-provider.mdx)
- [Victoriametrics](/docs/providers/documentation/victoriametrics-provider.mdx)

### Logging & Analytics
- [Axiom](/docs/providers/documentation/axiom-provider.mdx)
- [Coralogix](/docs/providers/documentation/coralogix-provider.mdx)
- [Kibana](/docs/providers/documentation/kibana-provider.mdx)
- [OpenSearch Serverless](/docs/providers/documentation/opensearch_serverless-provider.mdx)
- [Parseable](/docs/providers/documentation/parseable-provider.mdx)
- [PostHog](/docs/providers/documentation/posthog-provider.mdx)

### Incident Management & Alerting
- [Flashduty](/docs/providers/documentation/flashduty-provider.mdx)
- [ilert](/docs/providers/documentation/ilert-provider.mdx)
- [Incident.io](/docs/providers/documentation/incident_io-provider.mdx)
- [Incident Manager](/docs/providers/documentation/incident_manager-provider.mdx)
- [Opsgenie](/docs/providers/documentation/opsgenie-provider.mdx)
- [PagerDuty](/docs/providers/documentation/pagerduty-provider.mdx)
- [Pagertree](/docs/providers/documentation/pagertree-provider.mdx)
- [SIGNL4](/docs/providers/documentation/signl4-provider.mdx)
- [Squadcast](/docs/providers/documentation/squadcast-provider.mdx)
- [Zenduty](/docs/providers/documentation/zenduty-provider.mdx)

### Databases & Data Warehouses
- [BigQuery](/docs/providers/documentation/bigquery-provider.mdx)
- [ClickHouse](/docs/providers/documentation/clickhouse-provider.mdx)
- [Databend](/docs/providers/documentation/databend-provider.mdx)
- [MongoDB](/docs/providers/documentation/mongodb-provider.mdx)
- [MySQL](/docs/providers/documentation/mysql-provider.mdx)
- [PostgreSQL](/docs/providers/documentation/postgresql-provider.mdx)
- [Snowflake](/docs/providers/documentation/snowflake-provider.mdx)

### Messaging & Event Streaming
- [AmazonSQS](/docs/providers/documentation/amazonsqs-provider.mdx)
- [Kafka](/docs/providers/documentation/kafka-provider.mdx)

### AI & LLM Providers
- [Anthropic](/docs/providers/documentation/anthropic-provider.mdx)
- [DeepSeek](/docs/providers/documentation/deepseek-provider.mdx)
- [Gemini](/docs/providers/documentation/gemini-provider.mdx)
- [Grok](/docs/providers/documentation/grok-provider.mdx)
- [LiteLLM](/docs/providers/documentation/litellm-provider.mdx)
- [Llama.cpp](/docs/providers/documentation/llama_cpp-provider.mdx)
- [Ollama](/docs/providers/documentation/ollama-provider.mdx)
- [OpenAI](/docs/providers/documentation/openai-provider.mdx)
- [vLLM](/docs/providers/documentation/vllm-provider.mdx)

### Collaboration & Communication
- [Zoom](/docs/providers/documentation/zoom-provider.mdx)
- [Discord](/docs/providers/documentation/discord-provider.mdx)
- [Google Chat](/docs/providers/documentation/google_chat-provider.mdx)
- [Mattermost](/docs/providers/documentation/mattermost-provider.mdx)
- [Microsoft Teams](/docs/providers/documentation/microsoft_teams-provider.mdx)
- [Slack](/docs/providers/documentation/slack-provider.mdx)
- [Telegram](/docs/providers/documentation/telegram-provider.mdx)
- [Zoom Chat](/docs/providers/documentation/zoom_chat-provider.mdx)

### Project Management & Ticketing
- [Asana](/docs/providers/documentation/asana-provider.mdx)
- [Jira Cloud](/docs/providers/documentation/jira_cloud-provider.mdx)
- [Jira On-Prem](/docs/providers/documentation/jira_on_prem-provider.mdx)
- [Linear](/docs/providers/documentation/linear-provider.mdx)
- [Microsoft Planner](/docs/providers/documentation/microsoft_planner-provider.mdx)
- [Monday](/docs/providers/documentation/monday-provider.mdx)
- [Redmine](/docs/providers/documentation/redmine-provider.mdx)
- [Service Now](/docs/providers/documentation/service_now-provider.mdx)
- [Trello](/docs/providers/documentation/trello-provider.mdx)
- [YouTrack](/docs/providers/documentation/youtrack-provider.mdx)

### Notifications & Email
- [Mailgun](/docs/providers/documentation/mailgun-provider.mdx)
- [Ntfy.sh](/docs/providers/documentation/ntfy_sh-provider.mdx)
- [Pushover](/docs/providers/documentation/pushover-provider.mdx)
- [Resend](/docs/providers/documentation/resend-provider.mdx)
- [SendGrid](/docs/providers/documentation/sendgrid-provider.mdx)
- [SMTP](/docs/providers/documentation/smtp-provider.mdx)
- [Twilio](/docs/providers/documentation/twilio-provider.mdx)
- [Webhook](/docs/providers/documentation/webhook-provider.mdx)
- [Websocket](/docs/providers/documentation/websocket-provider.mdx)

### Network & Infrastructure Monitoring
- [Centreon](/docs/providers/documentation/centreon-provider.mdx)
- [Checkly](/docs/providers/documentation/checkly-provider.mdx)
- [Checkmk](/docs/providers/documentation/checkmk-provider.mdx)
- [Icinga2](/docs/providers/documentation/icinga2-provider.mdx)
- [LibreNMS](/docs/providers/documentation/librenms-provider.mdx)
- [Netdata](/docs/providers/documentation/netdata-provider.mdx)
- [Pingdom](/docs/providers/documentation/pingdom-provider.mdx)
- [Site24x7](/docs/providers/documentation/site24x7-provider.mdx)
- [StatusCake](/docs/providers/documentation/statuscake-provider.mdx)
- [ThousandEyes](/docs/providers/documentation/thousandeyes-provider.mdx)
- [UptimeKuma](/docs/providers/documentation/uptimekuma-provider.mdx)
- [Wazuh](/docs/providers/documentation/wazuh-provider.mdx)
- [Zabbix](/docs/providers/documentation/zabbix-provider.mdx)

### Identity & Access Management
- [Auth0](/docs/providers/documentation/auth0-provider.mdx)

### Developer Tools & Automation
- [Bash](/docs/providers/documentation/bash-provider.mdx)
- [Console](/docs/providers/documentation/console-provider.mdx)
- [HTTP](/docs/providers/documentation/http-provider.mdx)
- [Keep](/docs/providers/documentation/keep-provider.mdx)
- [Python](/docs/providers/documentation/python-provider.mdx)
- [QuickChart](/docs/providers/documentation/quickchart-provider.mdx)
- [SSH](/docs/providers/documentation/ssh-provider.mdx)
- [Template](/docs/providers/documentation/template-provider.mdx)

### Storage
- [AWS S3](/docs/providers/documentation/aws_s3-provider.mdx)

### Application Performance Monitoring (APM)
- [AppDynamics](/docs/providers/documentation/appdynamics-provider.mdx)
- [Rollbar](/docs/providers/documentation/rollbar-provider.mdx)
- [Sentry](/docs/providers/documentation/sentry-provider.mdx)
