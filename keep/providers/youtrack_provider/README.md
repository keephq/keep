## YouTrack Setup using Docker

1. Run the following command to start the YouTrack container (This doesn't persist the data)

```bash
docker run -it --name youtrack -p 8080:8080 jetbrains/youtrack:2025.1.62967
```

For more information, visit the [YouTracker Docker Setup](https://www.jetbrains.com/help/youtrack/server/youtrack-docker-installation.html).