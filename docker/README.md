# Docker Deployment Guide

This guide explains how to deploy **Tiny GenBI (MySQL)** using Docker and Docker Compose.

## Quick Start

### 1. Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

### 2. Configuration

Copy the example environment file and edit it with your settings:

```bash
cd docker
cp .env.example .env
```

Edit `.env` with your LLM provider credentials:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-actual-api-key

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=your-actual-api-key
```

### 3. Start the Application

```bash
docker-compose up -d
```

This will:
- Build the Docker image (may take a few minutes the first time)
- Start the GenBI application
- Expose the application on `http://localhost:5556`

### 4. Access the Application

Open your browser and navigate to:
```
http://localhost:5556
```

The API documentation is available at:
- Swagger UI: `http://localhost:5556/docs`
- ReDoc: `http://localhost:5556/redoc`

### 5. Stop the Application

```bash
docker-compose down
```

To also remove volumes (data will be lost):

```bash
docker-compose down -v
```

## Advanced Configuration

### Using Local LLM (Ollama)

If you want to use a local LLM instead of commercial APIs:

1. Uncomment the `ollama` service in `docker-compose.yml`
2. Update your `.env` file:
   ```env
   LLM_PROVIDER=local
   LLM_MODEL=llama2
   LLM_BASE_URL=http://ollama:11434/v1
   EMBEDDING_PROVIDER=local
   EMBEDDING_BASE_URL=http://ollama:11434/v1
   ```
3. Start the services:
   ```bash
   docker-compose up -d
   ```
4. Pull the model in Ollama:
   ```bash
   docker exec -it genbi-ollama ollama pull llama2
   ```

### Using Test MySQL Database

The `docker-compose.yml` includes an optional MySQL service for testing:

1. Uncomment the `mysql` service in `docker-compose.yml`
2. Start the services:
   ```bash
   docker-compose up -d
   ```
3. MySQL will be available at:
   - Host: `localhost` (or `mysql` from within Docker network)
   - Port: `3306`
   - Database: `testdb`
   - User: `testuser`
   - Password: `testpassword`

## Docker Commands Reference

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f genbi
```

### Restart Services

```bash
docker-compose restart
```

### Rebuild Image

If you make changes to the code:

```bash
docker-compose build --no-cache
docker-compose up -d
```

### Check Container Status

```bash
docker-compose ps
```

### View Container Resource Usage

```bash
docker stats tiny-genbi
```

## Data Persistence

Data is persisted in Docker volumes:

- `genbi-data`: Stores indexed database dumps and vector stores
- `genbi-credentials`: Stores encrypted database credentials

To backup data:

```bash
# Create backup directory
mkdir -p backups

# Backup data volume
docker run --rm -v genbi-data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/genbi-data-backup.tar.gz -C /data .

# Backup credentials volume
docker run --rm -v genbi-credentials:/data -v $(pwd)/backups:/backup alpine tar czf /backup/genbi-credentials-backup.tar.gz -C /data .
```

To restore data:

```bash
# Restore data volume
docker run --rm -v genbi-data:/data -v $(pwd)/backups:/backup alpine sh -c "cd /data && tar xzf /backup/genbi-data-backup.tar.gz"

# Restore credentials volume
docker run --rm -v genbi-credentials:/data -v $(pwd)/backups:/backup alpine sh -c "cd /data && tar xzf /backup/genbi-credentials-backup.tar.gz"
```

## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker-compose logs genbi
```

### Port Already in Use

Change the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "8080:5556"  # Use port 8080 instead of 5556
```

### Out of Memory

Increase Docker memory limits in Docker Desktop settings or add memory limits to the container.

### Database Connection Issues

If connecting to MySQL on host machine from Docker:
- Use `host.docker.internal` as the MySQL host (macOS/Windows)
- Use `172.17.0.1` (Docker bridge IP) on Linux

### Permission Issues

If you encounter permission issues with volumes:

```bash
docker-compose down
docker volume rm genbi-data genbi-credentials
docker-compose up -d
```

## Security Considerations

1. **Never commit `.env` file** to version control
2. **Rotate API keys regularly**
3. **Use Docker secrets** for sensitive data in production
4. **Keep Docker images updated**: `docker-compose pull && docker-compose up -d`
5. **Limit container capabilities** if possible
6. **Use read-only filesystems** where appropriate

## Support

For issues or questions:
- Check the main [README.md](../README.md)
- Open an issue on GitHub
- Review Docker and Docker Compose documentation

---

**Happy Deploying! 🚀**
