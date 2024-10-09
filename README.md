# Document Q&A

This project provides a Flask-based API that uses Google Vertex AI's Gemini generative model to answer questions about a document. It leverages a context cache for improved performance and consistency, and includes robust error handling and logging.

## Features

* **Context-Aware Responses:** The bot maintains context across a conversation using a message history.
* **Detailed Explanations:** Provides comprehensive answers tailored for non-expert users.
* **Report Referencing:** Cites relevant chapters from the document.
* **Concise Answers:** Limits responses to 2000 characters.
* **Robust Error Handling:** Includes retry mechanisms and informative error messages.
* **Comprehensive Logging:** Logs requests, responses, and errors for debugging and monitoring.
* **CORS Enabled:** Allows cross-origin requests for flexibility in deployment.
* **Context Caching:** Uses Vertex AI's caching mechanism for faster and more consistent responses.


## Prerequisites

* **Google Cloud Project:** A Google Cloud project with the Vertex AI API enabled.
* **Service Account:** A service account with permissions to access Vertex AI and Google Cloud Storage.
* **Environment Variables:** The following environment variables must be set:
* `BUCKET_NAME`: The name of the GCS bucket containing the report content.
* `BLOB_NAME`: The name of the blob within the GCS bucket containing the report content.
* `PROJECT_ID`: Your Google Cloud project ID.
* `LOCATION`: The Google Cloud region where your Vertex AI resources are located (e.g., `us-central1`).
* `CACHE_NAME`: The display name of the Context Cache.


## Installation

1. Clone this repository:
```bash
git clone https://github.com/jorsj/doc-qa
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Upload the document to your Google Cloud Storage bucket at the specified `BUCKET_NAME` and `BLOB_NAME`. The content should be in a format understandable by the LLM (e.g., text/markdown).
4. Set the required environment variables.


## Usage

### Running with Docker

```bash
docker build . -t doc-qa

docker run \
-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/application_default_credentials.json \
-v <YOUR_GOOGLE_APPLICATION_CREDENTIALS_PATH>:/tmp/keys/application_default_credentials.json:ro \
-e BUCKET_NAME=<YOUR_BUCKET_NAME> \
-e LOCATION=<YOUR_LOCATION> \
-e BLOB_NAME=<YOUR_BLOB_NAME> \
-e PROJECT_ID=<YOUR_PROJECT_ID> \
-e CACHE_NAME=<YOUR_CACHE_NAME>
-p 8080:8080 \
doc-qa
```

Replace the bracketed placeholders with your actual values. Make sure the path you mount for `GOOGLE_APPLICATION_CREDENTIALS` contains your actual credentials file.


### Running Locally

```bash
export BUCKET_NAME=<YOUR_BUCKET_NAME>
export LOCATION=<YOUR_LOCATION>
export BLOB_NAME=<YOUR_BLOB_NAME>
export PROJECT_ID=<YOUR_PROJECT_ID>
export CACHE_NAME=<YOUR_CACHE_NAME>
export GOOGLE_APPLICATION_CREDENTIALS=<YOUR_GOOGLE_APPLICATION_CREDENTIALS_PATH>
python app.py
```

Replace the bracketed placeholders with your actual values.


Send POST requests to the `/` endpoint with a JSON payload containing the following:

```json
{
  "question": "Your question",
  "messages": [
    {
      "role": "user",
      "content": "Previous message 1"
    },
    {
      "role": "assistant",
      "content": "Previous response 1"
    },
    ...
  ]
}
```

The `messages` array provides the conversation history, which allows the bot to maintain context.


## Example Request

```bash
curl --location localhost:8080 \
--header 'Content-Type: application/json' \
--data '{
  "question": "Okay, what next?",
  "messages": [
    {
      "role": "user",
      "content": "I want to cook pasta for dinner tonight but I've never done it before."
    },
    {
      "role": "assistant",
      "content": "First, you need to boil a large pot of salted water."
    },
    {
      "role": "user",
      "content": "How much salt should I add?"
    },
    {
      "role": "assistant",
      "content": "A good rule of thumb is about a tablespoon of salt per gallon of water."
    }
  ]
}'
```
