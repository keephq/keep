1. Make sure you have a docker-compose.common.yml file with the common service configurations.
2. Create an nginx.conf file in the same directory with the Nginx configuration provided in the docs/deployment/ngnix.mdx file.
3. If you plan to use SSL, create a certbot directory with conf and www subdirectories for Let's Encrypt certificates.
4. Run the following command to start the services:

```bash
docker-compose -f docker-compose-nginx.yml up -d
```