## Checkmk Setup using Docker

1. Pull the check-mk-cloud image

```bash
docker pull checkmk/check-mk-cloud:2.3.0p19
```

2. Start the container

```bash
docker container run -dit \
  -p 8080:5000 \
  -p 8000:8000 \
  --tmpfs /opt/omd/sites/cmk/tmp:uid=1000,gid=1000 \
  -v monitoring:/omd/sites \
  --name monitoring \
  -v /etc/localtime:/etc/localtime:ro \
  --restart always \
  checkmk/check-mk-cloud:2.3.0p19
```

3. Access the Checkmk web interface at `http://localhost:8080/`

4. You can view your login credentials by running the following command

```bash
docker container logs monitoring
```
