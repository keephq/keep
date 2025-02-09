docker compose --project-directory . -f superset/docker-compose-superset.yml up -d
docker compose --project-directory . -f superset/docker-compose-superset.yml stop

docker compose --project-directory . -f superset/docker-compose-superset.yml up superset
