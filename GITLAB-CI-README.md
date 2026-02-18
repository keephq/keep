# GitLab CI/CD Setup Guide

Complete guide for building Docker images and deploying to Helm charts using GitLab CI/CD.

---

## 🚀 Quick Setup (3 Steps)

### Step 1: Configure Image Registry

Edit `.gitlab-ci.yml` and set your Docker registry path (line 5):

```yaml
IMAGE_REGISTRY_PATH: "mycompany.jfrog.io/docker-local/keep"
```

### Step 2: Configure Chart Repository (Optional)

If you want automatic Helm chart updates, edit `.gitlab-ci.yml` (line 12):

```yaml
CHART_REPO_URL: "https://gitlab.com/your-org/helm-charts.git"
```

### Step 3: Set GitLab CI/CD Variables

Go to **Settings → CI/CD → Variables** and add:

| Variable | Description | Required | Protected | Masked |
|----------|-------------|----------|-----------|--------|
| `DOCKER_REGISTRY_USER` | JFrog username | ✅ Yes | ✅ | ✅ |
| `DOCKER_REGISTRY_PASSWORD` | JFrog password/token | ✅ Yes | ✅ | ✅ |
| `CHART_REPO_TOKEN` | Git token for chart repo | Only for deploy | ✅ | ✅ |

**Done!** Push to GitLab and images will build automatically.

---

## 📦 What Gets Built

The pipeline builds 3 Docker images using Kaniko:

| Service | Image Name | Dockerfile | YAML Path (for deploy) |
|---------|------------|------------|------------------------|
| Backend API | `keep-api` | `docker/Dockerfile.api` | `backend.image.tag` |
| Event Handler | `keep-event-handler` | `docker/Dockerfile.api` | `eventHandler.image.tag` |
| Frontend UI | `keep-ui` | `docker/Dockerfile.ui` | `frontend.image.tag` |

Each image is tagged with:
- `${CI_COMMIT_SHORT_SHA}` (e.g., `abc1234`)
- `latest`

**Example:**
```
mycompany.jfrog.io/docker-local/keep/keep-api:abc1234
mycompany.jfrog.io/docker-local/keep/keep-api:latest
```

---

## 🎯 Pipeline Stages

### Stage 1: Build (Automatic)

Builds run automatically when:
- Pushing to `main`, `develop`, or `tags`
- Creating/updating merge requests
- Relevant files change

**Triggers:**
- **API/Event Handler**: Changes to `docker/Dockerfile.api`, `keep/**/*`, `pyproject.toml`, `poetry.lock`
- **UI**: Changes to `docker/Dockerfile.ui`, `keep-ui/**/*`

### Stage 2: Deploy (Manual)

After successful builds, you can **manually trigger** deployment jobs to update your Helm chart repository:

1. Go to **CI/CD → Pipelines** → Select your pipeline
2. Click the ▶️ play button on the deploy job you want:
   - `deploy:api` - Updates `backend.image.tag` in chart repo
   - `deploy:event-handler` - Updates `eventHandler.image.tag` in chart repo
   - `deploy:ui` - Updates `frontend.image.tag` in chart repo

Each deploy job:
- Clones your chart repository
- Updates the image tag in `custom-values.yaml`
- Commits and pushes the change
- Can be triggered independently (3 separate commits)

---

## 🔧 Using Private Registries

### Python/PyPI Dependencies

Add your private registry to `pyproject.toml`:

```toml
[[tool.poetry.source]]
name = "private-pypi"
url = "https://mycompany.jfrog.io/artifactory/api/pypi/pypi-virtual/simple"
priority = "primary"

[[tool.poetry.source]]
name = "pypi"
priority = "supplemental"
```

Poetry automatically reads these sources during build.

### NPM Dependencies

Create `keep-ui/.npmrc`:

```
registry=https://mycompany.jfrog.io/artifactory/api/npm/npm-virtual/
//mycompany.jfrog.io/artifactory/api/npm/npm-virtual/:_authToken=${NPM_TOKEN}
always-auth=true
```

Then add GitLab CI/CD variable:
- `NPM_TOKEN` = Your NPM authentication token

---

## 🔑 GitLab Token Setup (for Chart Deployment)

To enable automatic chart updates, create a GitLab Personal Access Token or Project Access Token:

### Option 1: Personal Access Token

1. Go to **User Settings → Access Tokens**
2. Create token with scopes: `write_repository`
3. Copy the token
4. Add to GitLab CI/CD Variables as `CHART_REPO_TOKEN`

### Option 2: Project Access Token (Recommended)

1. Go to your **chart repository** → **Settings → Access Tokens**
2. Create token with role: `Maintainer` and scopes: `write_repository`
3. Copy the token
4. Add to **this project's** GitLab CI/CD Variables as `CHART_REPO_TOKEN`

---

## 📝 Complete Configuration Example

### .gitlab-ci.yml Configuration

```yaml
variables:
  IMAGE_REGISTRY_PATH: "mycompany.jfrog.io/docker-local/keep"
  CHART_REPO_URL: "https://gitlab.com/myorg/helm-charts.git"
  CHART_REPO_BRANCH: "main"
```

### GitLab CI/CD Variables

```
DOCKER_REGISTRY_USER = gitlab-ci-user
DOCKER_REGISTRY_PASSWORD = ••••••••••••••••
CHART_REPO_TOKEN = glpat-••••••••••••••••
NPM_TOKEN = npm_•••••••••••••••• (optional)
```

### pyproject.toml (Optional - Private PyPI)

```toml
[[tool.poetry.source]]
name = "jfrog-pypi"
url = "https://mycompany.jfrog.io/artifactory/api/pypi/pypi-virtual/simple"
priority = "primary"
```

### keep-ui/.npmrc (Optional - Private NPM)

```
registry=https://mycompany.jfrog.io/artifactory/api/npm/npm-virtual/
//mycompany.jfrog.io/artifactory/api/npm/npm-virtual/:_authToken=${NPM_TOKEN}
```

---

## 🛠️ Troubleshooting

### Build Issues

**Error: `DOCKER_REGISTRY_PASSWORD is not set`**
- Solution: Add `DOCKER_REGISTRY_PASSWORD` to GitLab CI/CD Variables

**Error: `unauthorized: authentication required`**
- Solution: Verify your JFrog credentials are correct

**Error: `npm ERR! 401 Unauthorized`**
- Solution: Check `NPM_TOKEN` is valid and `.npmrc` is configured correctly

### Deploy Issues

**Error: `CHART_REPO_TOKEN is not set`**
- Solution: Add `CHART_REPO_TOKEN` to GitLab CI/CD Variables

**Error: `Permission denied (publickey)`**
- Solution: Use HTTPS URL (not SSH) for `CHART_REPO_URL`

**Error: `yq: command not found`**
- Solution: This shouldn't happen with `alpine/git:latest`, but you can specify a different image

### Manual Deploy Not Showing

- Deploy jobs only appear after successful build jobs
- Deploy jobs are only available on `main`, `develop`, and `tags` branches
- Check that `needs:` dependencies are satisfied

---

## 🔒 Security Best Practices

1. ✅ Mark all credentials as **Protected** and **Masked** in GitLab
2. ✅ Use tokens instead of passwords
3. ✅ Create tokens with minimal permissions (e.g., only `write_repository` for chart updates)
4. ✅ Rotate credentials regularly
5. ✅ Use Project Access Tokens instead of Personal Access Tokens when possible
6. ✅ Only enable deploy jobs on protected branches

---

## 🎨 Customization

### Change Image Tags

Edit `.gitlab-ci.yml`:

```yaml
variables:
  IMAGE_TAG: "${CI_COMMIT_TAG:-${CI_COMMIT_SHORT_SHA}}"  # Use git tag if available
```

### Change Kaniko Version

```yaml
variables:
  KANIKO_IMAGE: "gcr.io/kaniko-project/executor:v1.22.0"
```

### Disable Layer Caching

In `.gitlab-ci.yml`, change `--cache=true` to `--cache=false`

### Change Chart File Path

If your chart uses a different file than `custom-values.yaml`, edit the deploy template:

```yaml
yq eval ".${YAML_PATH} = \"${IMAGE_TAG}\"" -i your-values-file.yaml
```

### Auto-deploy Without Manual Trigger

Remove `when: manual` from the `.update_chart` template (not recommended for production)

---

## 📊 Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Git Push (main/develop/tags/MR)                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Stage: Build (Automatic)                               │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  build:api  │  │build:event- │  │  build:ui   │    │
│  │             │  │   handler   │  │             │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │            │
│         ▼                ▼                ▼            │
│  keep-api:abc1234  keep-event-      keep-ui:abc1234   │
│  keep-api:latest   handler:abc1234  keep-ui:latest    │
│                    keep-event-                         │
│                    handler:latest                      │
└────────────────┬────────────────┬────────────┬─────────┘
                 │                │            │
                 ▼                ▼            ▼
┌─────────────────────────────────────────────────────────┐
│  Stage: Deploy (Manual Trigger)                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ deploy:api  │  │deploy:event-│  │ deploy:ui   │    │
│  │   (▶️ Play) │  │handler(▶️)  │  │   (▶️ Play) │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │            │
│         ▼                ▼                ▼            │
│  Update backend.   Update event-    Update frontend.  │
│  image.tag in      Handler.image.   image.tag in      │
│  chart repo        tag in chart     chart repo        │
│                    repo                                │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 Additional Information

### Image Naming Convention

```
${IMAGE_REGISTRY_PATH}/${IMAGE_NAME}:${IMAGE_TAG}
```

Example:
```
mycompany.jfrog.io/docker-local/keep/keep-api:abc1234
└────────────┬─────────────────┘ └───┬───┘ └───┬───┘
        Registry Path          Image Name   Tag
```

### Chart Update Format

The deploy jobs update `custom-values.yaml` in your chart repository:

```yaml
# Before
backend:
  image:
    tag: "old-tag"

# After deploy:api with IMAGE_TAG=abc1234
backend:
  image:
    tag: "abc1234"
```

### Commit Message Format

When updating the chart, commits include:

```
Update backend image tag to abc1234

Triggered by: keep
Commit: abc1234567890abcdef1234567890abcdef12345
Pipeline: https://gitlab.com/your-org/keep/-/pipelines/12345
```

---

## ✅ Checklist

Before pushing to GitLab, verify:

- [ ] `IMAGE_REGISTRY_PATH` is set in `.gitlab-ci.yml`
- [ ] `DOCKER_REGISTRY_USER` is set in GitLab CI/CD Variables
- [ ] `DOCKER_REGISTRY_PASSWORD` is set in GitLab CI/CD Variables
- [ ] Variables are marked as **Protected** and **Masked**
- [ ] (Optional) `CHART_REPO_URL` is set for deployments
- [ ] (Optional) `CHART_REPO_TOKEN` is set for deployments
- [ ] (Optional) Private registries configured in `pyproject.toml` / `.npmrc`

---

## 🆘 Need Help?

- Check the troubleshooting section above
- Review GitLab pipeline logs for detailed error messages
- Verify all required variables are set correctly
- Ensure tokens have appropriate permissions
- Check that chart repository URL is accessible

---

**Last Updated:** 2026-02-18
