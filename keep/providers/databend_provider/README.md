## Databend Setup using Docker

1. Run the following command to start a Databend container.

```bash
docker run \
    -p 8000:8000 \
    -e QUERY_DEFAULT_USER=databend \
    -e QUERY_DEFAULT_PASSWORD=databend \
    datafuselabs/databend
```
