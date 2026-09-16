# Production deployment

## Server secrets

Configure these GitHub Actions repository secrets before using automatic production deployment:

- `DEPLOY_HOST`: production server hostname or IP
- `DEPLOY_USER`: SSH user
- `DEPLOY_SSH_KEY`: private SSH key with access to the deployment user
- `DEPLOY_PORT`: optional SSH port, defaults to `22`
- `DEPLOY_PATH`: optional checkout path, defaults to `/opt/personal-ai-secretary`

## Update flow

A push to `main` runs `.github/workflows/deploy.yml`. The server pulls the new `main`, rebuilds the Docker API container, runs Alembic migrations, and checks `/health`.

The deployment exports the Git commit SHA as `APP_VERSION`. Web pages expose that release identifier through `/api/system/version` and the shared `/update.js` client checks it every 30 seconds. When the server release changes, open browser pages reload automatically. The mobile meeting page defers reload while recording is active and picks up the new release afterward.
