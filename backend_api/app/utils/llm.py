from typing import List
from openai import OpenAI
from config import config
from .system_prompt import get_system_prompt
from .vector_store import find_similar_documents
from ddtrace.llmobs.decorators import embedding, llm, workflow
from ddtrace.llmobs import LLMObs

EMBED_URL = f"{config.EMBED_BASE_URL}:{config.EMBED_PORT}/v1"
LLM_URL = f"{config.LLM_BASE_URL}:{config.LLM_PORT}/v1"

openai_client_llm = OpenAI(
    base_url=LLM_URL,
    api_key=config.OPENAI_API_KEY,
)

openai_client_embedding = OpenAI(
    base_url=EMBED_URL,
    api_key=config.OPENAI_API_KEY,
)


@llm(model_name=config.LLM_MODEL)
def ask_the_llm(prompt: str, system_prompt: str = None) -> str:
    """
    Calls the LLM with the given prompt and system context
    """
    if system_prompt is None:
        system_prompt = get_system_prompt()
    response = openai_client_llm.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )
    LLMObs.annotate(
        input_data=prompt,
        output_data=response.choices[0].message.content,
    )
    return response.choices[0].message.content


@embedding(model_name=config.EMBED_MODEL)
def create_embeddings(text: str, prefix: str = "search_query") -> List[float]:
    """
    Creates embeddings for the given text using the configured embedding model.
    """
    response = openai_client_embedding.embeddings.create(
        model=config.EMBED_MODEL, input=[f"{prefix}: {text}"]
    )
    return response.data[0].embedding


@llm(model_name=config.LLM_MODEL)
def categorize_query(query: str) -> str:
    """
    Categorizes a user query  knowledge base collections.
    Returns the most relevant collection name for the query.
    """
    VALID_CATEGORIES = [
        "faq",
        "legal",
        "sales",
        "technology",
        "travel_experience",
        "travel_packages",
        "travel_policies",
    ]

    def find_categories(text: str) -> list:
        """Helper function to find valid categories in text."""
        # Replace underscores with spaces in the text for matching
        text_normalized = text.replace("_", " ")

        found = []
        for category in VALID_CATEGORIES:
            # Check exact match with original format
            if category == text:
                return [category]

            # Check both underscore and space versions
            category_spaced = category.replace("_", " ")
            if category_spaced in text_normalized.split():
                found.append(category)

        return found

    system_prompt = (
        "You are a query categorization assistant. Choose exactly ONE "
        "category from this list:\n\n"
        f"{', '.join(VALID_CATEGORIES)}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Respond with ONLY the category name\n"
        "2. Do not add any explanation or punctuation\n"
        "3. The response must be exactly one of the categories\n\n"
        f"Question to categorize: {query}"
    )

    response = openai_client_llm.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        temperature=0,
    )

    # Extract and clean the category from the response
    response_text = response.choices[0].message.content.strip().lower()

    # First try: Check if the entire response is a valid category
    if response_text in VALID_CATEGORIES:
        return response_text

    # Second try: Look for valid categories in the response
    found_categories = find_categories(response_text)

    if len(found_categories) == 1:
        return found_categories[0]
    elif len(found_categories) > 1:
        categories_list = ", ".join(VALID_CATEGORIES)
        found_list = ", ".join(found_categories)
        raise ValueError(
            f"Found multiple categories: {found_list}. "
            f"Must be one of: {categories_list}"
        )

    # If no valid category found, raise error
    categories_list = ", ".join(VALID_CATEGORIES)
    raise ValueError(
        f"No valid category found in response: '{response_text}'. "
        f"Must be one of: {categories_list}"
    )


@workflow
def ask_the_llm_with_rag(prompt: str) -> str:
    """
    Constructs a prompt for the LLM using a retrieval-augmented generation (RAG) approach.
    Calls the LLM and returns the response.
    """
    # Step 1: Categorize the query to provide a topic for document retrieval
    topic = categorize_query(prompt)

    # Step 2: Create embeddings for the search query
    embedded_search_query = create_embeddings(prompt, "search_query")

    # Step 3: Find relevant documents using vector similarity search
    results = find_similar_documents(embedded_search_query, topic=topic)

    # Step 4: Augment the prompt with retrieved context
    system_prompt = (
        "Act as the Time Travel Concierge for QuantumHound."
        "Help travelers by answering questions based on the "
        "provided context.\n\n"
        "Instructions:\n"
        "- Use only the provided context.\n"
        "- Respond in a helpful, welcoming tone.\n"
        "- If it lacks relevant information, say so clearly."
    )
    user_prompt = (
        f"Context ({topic} knowledge base):\n{results}\n\n"
        f"Traveler Question: {prompt}"
    )

    # Step 5: Get response from LLM using the augmented prompt
    return ask_the_llm(user_prompt, system_prompt)
