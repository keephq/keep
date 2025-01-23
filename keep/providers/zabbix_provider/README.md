## How to start Zabbix?

Clone the Zabbix docker repo:
`git clone https://github.com/zabbix/zabbix-docker.git`

Enter the repo directory:
`cd zabbix-docker`

Run the docker compose file (with PostgreSQL):
`docker compose -f docker-compose_v3_alpine_pgsql_latest.yaml up`

Open the Zabbix UI:
`http://localhost`

Login with the default credentials:
`Admin` / `zabbix`
