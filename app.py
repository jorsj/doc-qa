import logging
import os
import datetime

import vertexai
from flask import Flask, jsonify, request
from flask_cors import CORS
from tenacity import retry, stop_after_attempt, wait_random_exponential

import vertexai.generative_models
from vertexai.preview.generative_models import GenerativeModel, Part
from google.api_core.exceptions import InvalidArgument
from vertexai.preview.prompts import Prompt
from vertexai.preview import caching
import requests
import google.auth.transport.requests
from google.auth import default

# Initialize Flask app
app = Flask(__name__)

# Configure CORS to allow requests from any origin
CORS(app, resources={r"/": {"origins": "*"}})


def create_context_cache():
    """
    Creates a Context Cache with system instructions and initial content.

    Returns:
        A vertexai.preview.caching.CachedContent object.
    """
    try:
        with open("./system_instructions.txt", "r") as file:
            system_instruction = file.read()
        logger.info("Successfully loaded system instructions.")
    except FileNotFoundError:
        logger.error("system_instructions.txt not found.", exc_info=True)
        raise  # Re-raise the exception to halt execution
    try:
        contents = Part.from_uri(
            f"gs://{BUCKET_NAME}/{BLOB_NAME}",  # Added bucket and blob name
            mime_type="text/markdown",
        )
        logger.info(f"Loaded content from gs://{BUCKET_NAME}/{BLOB_NAME}")
    except Exception as e:
        logger.error(f"Error loading content from GCS: {e}", exc_info=True)
        raise
    try:
        cached_content = caching.CachedContent.create(
            model_name="gemini-1.5-flash-002",
            system_instruction=system_instruction,
            contents=contents,
            ttl=datetime.timedelta(days=360),
            display_name=CACHE_NAME,
        )
        return cached_content
    except Exception as e:
        logger.error(f"Error creating context cache: {e}", exc_info=True)
        raise


def fetch_cached_content():
    """
    Retrieves cached content from Vertex AI.

    This function fetches cached content from Vertex AI. It first authenticates using
    default credentials, then builds the request URL and headers.

    Args:
        None: This function takes no parameters.

    Returns:
        caching.CachedContent: If a cached content with the specified name is found.
        None: If no cached content with the specified name is found.

    Raises:
        Exception: If an error occurs while fetching or parsing the cached content.
    """
    creds, _ = default()
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)

    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/cachedContents"
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.request("GET", url, headers=headers).json()
    try:
        response = requests.request("GET", url, headers=headers).json()
        for cached_content in response["cachedContents"]:
            if cached_content["displayName"] == CACHE_NAME:
                logging.info(f"Found context cache with name {cached_content["name"]}")
                return caching.CachedContent(cached_content_name=cached_content["name"])

        raise Exception

    except Exception:
        logging.info("No cached content found.")
        raise  # Re-raise the exception to propagate the error


def refresh_cached_context():
    """
    Refreshes the cached context and generates a new model instance.

    This function attempts to fetch the cached context. If the fetch fails, it
    creates a new context cache. It then returns the cached content and a new
    GenerativeModel instance initialized with the cached content.

    Returns:
        A tuple containing the cached content and a new GenerativeModel instance.

    Raises:
        Exception: If an error occurs while fetching or creating the cached context.
    """
    try:
        cached_content = fetch_cached_content()
    except Exception as e:
        logging.info(f"Creating new context cache because of error: {str(e)}")
        cached_content = create_context_cache()
    return cached_content, GenerativeModel.from_cached_content(cached_content)


@retry(wait=wait_random_exponential(max=60), stop=stop_after_attempt(6))
@app.route("/", methods=["GET", "POST", "OPTIONS"])
def bot():
    """
    Handles requests to the bot endpoint.

    GET: Returns a welcome message and status.
    POST: Processes the user's question and context, generates a response from the LLM, and returns the answer.
    OPTIONS: Handles CORS preflight requests.

    Returns:
        A JSON response containing the bot's answer or an error message, and the HTTP status code.
    """
    global cached_content, model
    if request.method == "GET":
        logger.info("Received GET request.")
        return "OK", 200

    if request.method == "POST":
        try:
            request_json = request.get_json()
            logger.info(
                f"Received POST request with data: {request_json}"
            )  # Log the actual request data

            question = request_json["question"]
            messages = request_json["messages"]

            prompt = prompt_template.format(messages=messages, question=question)

            answer = model.generate_content(prompt)

            logger.info(
                f"Successfully generated answer: {answer.candidates[0].text.strip()}"
            )  # Log the answer

            text = clean_response(answer.candidates[0].text.strip())

            json_array = {"answer": text}
            logging.info("Processed answer")

        except InvalidArgument as e:
            logger.info(f"Error querying the context cache: {str(e)}")
            cached_content, model = refresh_cached_context()

        except Exception as e:
            logger.error(
                f"Error processing POST request: {str(e)}", exc_info=True
            )  # Include exc_info for stack trace
            json_array = {
                "error": str(e),
                "answer": "I couldn't find an answer, please try again.",
            }

        return jsonify(json_array), 200

    # OPTIONS requests are handled by Flask-CORS
    return "", 204


@retry(wait=wait_random_exponential(max=60), stop=stop_after_attempt(6))
def clean_response(answer: str) -> str:
    """
    Cleans the LLM response by fixing capitalization, removing special characters and emojis.

    Args:
        answer: The LLM generated response string.

    Returns:
        The cleaned response string.
    """
    try:
        prompt_obj = Prompt(
            system_instruction="Convert markdown syntax to plain text, keep everything in a single paragraph, correct spelling and remove emojis.",
            prompt_data=[answer],
            model_name="gemini-1.5-flash-002",
        )
        llm_response = prompt_obj.generate_content(
            contents=prompt_obj.assemble_contents(), stream=False
        )
        logger.info(f"Cleaned response: {llm_response.candidates[0].text.strip()}")
        return llm_response.candidates[0].text.strip()
    except Exception as e:
        logger.error(f"Error cleaning response: {e}", exc_info=True)
        return answer  # Return original answer if cleaning fails


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    logger.info("Starting application...")

    # Configure logging - Improved formatting and file handling

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Verify required environment variables
    required_env_vars = ["BUCKET_NAME", "BLOB_NAME", "PROJECT_ID", "LOCATION"]
    for var in required_env_vars:
        if var not in os.environ:
            raise EnvironmentError(f"Missing required environment variable: {var}")

    # Load environment variables
    BUCKET_NAME = os.environ["BUCKET_NAME"]
    BLOB_NAME = os.environ["BLOB_NAME"]
    PROJECT_ID = os.environ["PROJECT_ID"]
    LOCATION = os.environ["LOCATION"]
    CACHE_NAME = os.environ["CACHE_NAME"]

    # Load prompt template from file - with error handling
    try:
        with open("./prompt_template.txt", "r") as file:
            prompt_template = file.read()
        logger.info("Successfully loaded prompt template.")
    except FileNotFoundError:
        logger.error("prompt_template.txt not found.", exc_info=True)
        raise

    # Initialize Vertex AI
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    cached_content, model = refresh_cached_context()

    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
