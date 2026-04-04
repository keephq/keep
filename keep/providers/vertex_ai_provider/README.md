# Vertex AI Provider

The Vertex AI Provider integrates Keep with [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai), enabling Keep workflows to invoke powerful Google generative AI models (Gemini, PaLM 2, etc.) directly.

## Features

- **Text generation** using Vertex AI generative models (Gemini 1.5 Flash, Pro, Ultra, etc.)
- **Structured JSON output** — enforce a JSON schema on model responses
- **System instruction** support for fine-grained model behavior
- **Service account authentication** or Application Default Credentials (ADC)

## Authentication

The provider supports two authentication modes:

### Option 1: Application Default Credentials (ADC)
Leave `credentials_json` empty. Ensure your environment has ADC configured:
```bash
gcloud auth application-default login
```

### Option 2: Service Account JSON Key
Paste the full content of your service account JSON key file into `credentials_json`.

1. Go to **GCP Console** → **IAM & Admin** → **Service Accounts**
2. Create or select a service account
3. Grant `Vertex AI User` role (`roles/aiplatform.user`)
4. Create and download a JSON key

## Configuration

| Field              | Required | Description                                                           |
|--------------------|----------|-----------------------------------------------------------------------|
| `project_id`       | ✅ Yes   | Your Google Cloud Project ID                                          |
| `location`         | ❌ No    | GCP region (default: `us-central1`)                                   |
| `credentials_json` | ❌ No    | Service account key JSON content (uses ADC if not provided)           |

## Usage in Keep Workflows

```yaml
steps:
  - name: analyze-alert
    provider:
      type: vertex_ai
      config: "{{ providers.my-vertex-ai }}"
    with:
      prompt: "Analyze this alert and suggest actions: {{ alert.description }}"
      model: "gemini-1.5-flash-001"
      max_tokens: 512
      temperature: 0.2
      structured_output_format:
        json_schema:
          type: object
          properties:
            severity:
              type: string
              enum: [critical, high, medium, low]
            summary:
              type: string
            action:
              type: string
          required: [severity, summary, action]
```

## Available Models

| Model Name                   | Description                              |
|------------------------------|------------------------------------------|
| `gemini-1.5-flash-001`       | Fast, efficient (default)                |
| `gemini-1.5-pro-001`         | High capability, complex tasks           |
| `gemini-1.0-pro-001`         | Balanced performance                     |
| `text-bison@002`             | PaLM 2 text model                        |

## References

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Vertex AI Generative AI](https://cloud.google.com/vertex-ai/docs/generative-ai/start/quickstarts/api-quickstart)
- [Authentication Guide](https://cloud.google.com/vertex-ai/docs/authentication)
- [Python SDK (google-cloud-aiplatform)](https://cloud.google.com/python/docs/reference/aiplatform/latest)
