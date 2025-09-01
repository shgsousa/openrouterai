from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import sqlite3
from typing import List, Optional
from contextlib import asynccontextmanager
import httpx
from datetime import timedelta, datetime
import os
import asyncio

DB_NAME = "models.db"

def get_db_connection():
    """Create and return a database connection to the models database.
    
    Establishes a connection to the SQLite database file and configures
    it to return rows as dictionary-like objects for easier data access.
    
    Returns:
        sqlite3.Connection: Database connection with Row factory configured.
        
    Note:
        The connection should be properly closed after use to avoid
        resource leaks. Consider using context managers for automatic cleanup.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

class Model(BaseModel):
    __name__ = "mcp.model"
    __title__ = "Model"

    id: str = Field(..., description="The unique identifier of the model.")
    company: Optional[str] = Field(None, description="The company that created the model.")
    model: Optional[str] = Field(None, description="The name of the model.")
    canonical_slug: Optional[str] = Field(None, description="The canonical slug of the model.")
    hugging_face_id: Optional[str] = Field(None, description="The Hugging Face ID of the model.")
    name: Optional[str] = Field(None, description="The name of the model.")
    created: Optional[int] = Field(None, description="The creation timestamp of the model.")
    created_date: Optional[str] = Field(None, description="The creation date of the model.")
    description: Optional[str] = Field(None, description="A description of the model.")
    context_length: Optional[int] = Field(None, description="The context length of the model.")
    prompt_price: Optional[float] = Field(None, description="The price per million tokens for prompts.")
    completion_price: Optional[float] = Field(None, description="The price per million tokens for completions.")

    @classmethod
    def search(
        cls,
        company: Optional[str] = Field(None, description="The company that created the model."),
        input_modality: Optional[str] = Field(None, description="The input modality of the model."),
        output_modality: Optional[str] = Field(None, description="The output modality of the model."),
        is_free: Optional[bool] = Field(None, description="Whether the model is free to use."),
        name_like: Optional[str] = Field(None, description="A string to search for in the model name."),
        min_context_length: Optional[int] = Field(None, description="The minimum context length of the model."),
        price_type: Optional[str] = Field("prompt", description="Type of pricing to filter by: 'prompt' or 'completion'"),
        min_price: Optional[float] = Field(None, description="Minimum price per million tokens"),
        max_price: Optional[float] = Field(None, description="Maximum price per million tokens"),
        min_price_inclusive: Optional[bool] = Field(False, description="Whether min_price bound is inclusive (default: true)"),
        max_price_inclusive: Optional[bool] = Field(True, description="Whether max_price bound is inclusive (default: false)"),
    ) -> List["Model"]:
        """Search for AI models in the database with advanced filtering options.
        
        This method queries the SQLite database for models matching the specified criteria.
        It supports filtering by company, modalities, pricing, and other model attributes.
        
        The method performs the following operations:
        1. Builds a dynamic SQL query based on provided filters
        2. Executes the query against the models and pricings tables
        3. Converts database results to Model instances
        4. Transforms prices from per-token to per-million-tokens format
        
        Args:
            company: Filter by model provider company
            input_modality: Filter by input type (text, image, etc.)
            output_modality: Filter by output type (text, image, etc.)
            is_free: Filter for free models (True) or exclude free models (False)
            name_like: Partial string match for model names
            min_context_length: Minimum context window size
            price_type: Which pricing to filter by ("prompt" or "completion")
            min_price: Minimum price per million tokens
            max_price: Maximum price per million tokens
            min_price_inclusive: Whether min_price bound is inclusive
            max_price_inclusive: Whether max_price bound is inclusive
            
        Returns:
            List of Model instances matching the search criteria, with prices
            converted to dollars per million tokens.
            
        Note:
            Free models (with NULL or zero prices) are handled consistently
            across all filtering operations.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT m.*, p.prompt as prompt_price, p.completion as completion_price FROM models m LEFT JOIN pricings p ON m.id = p.model_id"
        params = []
        joins = set()

        if company:
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            query += " m.company = ?"
            params.append(company)
        
        if input_modality:
            joins.add(" JOIN input_modalities im ON m.id = im.model_id")
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            query += " im.modality = ?"
            params.append(input_modality)

        if output_modality:
            joins.add(" JOIN output_modalities om ON m.id = om.model_id")
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            query += " om.modality = ?"
            params.append(output_modality)

        if is_free is not None:
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            if is_free:
                # Free models: NULL, '0.0', or '0' prices
                query += " (COALESCE(p.prompt, '0.0') IN ('0.0', '0') AND COALESCE(p.completion, '0.0') IN ('0.0', '0') AND COALESCE(p.request, '0.0') IN ('0.0', '0') AND COALESCE(p.image, '0.0') IN ('0.0', '0'))"
            else:
                # Non-free models: at least one non-zero price
                query += " ((p.prompt IS NOT NULL AND p.prompt NOT IN ('0.0', '0')) OR (p.completion IS NOT NULL AND p.completion NOT IN ('0.0', '0')) OR (p.request IS NOT NULL AND p.request NOT IN ('0.0', '0')) OR (p.image IS NOT NULL AND p.image NOT IN ('0.0', '0')))"

        # Price filtering
        if min_price is not None or max_price is not None:
            if price_type not in ["prompt", "completion"]:
                price_type = "prompt"  # Default fallback
            
            price_column = "p.prompt" if price_type == "prompt" else "p.completion"
            
            # For price filtering, treat NULL and '0'/'0.0' prices as 0
            price_expr = f"CASE WHEN {price_column} IS NULL OR {price_column} IN ('0', '0.0') THEN 0 ELSE CAST({price_column} AS REAL) END * 1000000"
            
            if min_price is not None:
                if "WHERE" not in query:
                    query += " WHERE"
                else:
                    query += " AND"
                operator = ">=" if min_price_inclusive else ">"
                query += f" {price_expr} {operator} ?"
                params.append(min_price)
            
            if max_price is not None:
                if "WHERE" not in query:
                    query += " WHERE"
                else:
                    query += " AND"
                operator = "<=" if max_price_inclusive else "<"
                query += f" {price_expr} {operator} ?"
                params.append(max_price)

        if name_like:
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            query += " m.name LIKE ?"
            params.append(f"%{name_like}%")

        if min_context_length:
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            query += " m.context_length >= ?"
            params.append(min_context_length)

        final_query = query
        
        cursor.execute(final_query, params)
        models = cursor.fetchall()
        conn.close()

        # Convert prices from per-token to per-million-tokens
        models_list = []
        for row in models:
            row_dict = dict(row)
            if row_dict.get('prompt_price') is not None:
                try:
                    price_str = str(row_dict['prompt_price']).strip()
                    if price_str in ('', '0', '0.0'):
                        row_dict['prompt_price'] = 0.0
                    else:
                        row_dict['prompt_price'] = float(price_str) * 1000000
                except (ValueError, TypeError):
                    row_dict['prompt_price'] = None
            if row_dict.get('completion_price') is not None:
                try:
                    price_str = str(row_dict['completion_price']).strip()
                    if price_str in ('', '0', '0.0'):
                        row_dict['completion_price'] = 0.0
                    else:
                        row_dict['completion_price'] = float(price_str) * 1000000
                except (ValueError, TypeError):
                    row_dict['completion_price'] = None
            models_list.append(Model(**row_dict))
        
        return models_list

# Database rebuild functions
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

def rebuild_database() -> str:
    """Rebuild the models database by fetching fresh data from OpenRouter API.
    
    This function performs a complete refresh of the local SQLite database by:
    1. Connecting to the OpenRouter API (https://openrouter.ai/api/v1/models)
    2. Fetching the latest model catalog
    3. Dropping all existing database tables
    4. Recreating the database schema
    5. Inserting fresh model data including pricing and specifications
    
    The database includes the following tables:
    - models: Basic model information
    - architectures: Technical specifications
    - input_modalities/output_modalities: Model capabilities
    - pricings: Cost information per token
    
    Returns:
        str: Success message with model count or error description.
        
    Raises:
        This function handles exceptions internally and returns error messages
        as strings rather than raising exceptions.
        
    Example:
        result = rebuild_database()
        print(result)  # "Successfully rebuilt database with 150 models"
        
    Note:
        This is a destructive operation that replaces all existing data.
        Network connectivity to OpenRouter API is required.
        The operation may take 10-30 seconds depending on API response time.
    """
    url = "https://openrouter.ai/api/v1/models"
    try:
        response = httpx.get(url)
        response.raise_for_status()
        models_data = response.json()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Drop existing tables
        cursor.execute("DROP TABLE IF EXISTS models")
        cursor.execute("DROP TABLE IF EXISTS architectures")
        cursor.execute("DROP TABLE IF EXISTS input_modalities")
        cursor.execute("DROP TABLE IF EXISTS output_modalities")
        cursor.execute("DROP TABLE IF EXISTS pricings")
        cursor.execute("DROP TABLE IF EXISTS top_providers")
        cursor.execute("DROP TABLE IF EXISTS per_request_limits")
        cursor.execute("DROP TABLE IF EXISTS supported_parameters")
        
        # Create tables (simplified version)
        cursor.execute('''
            CREATE TABLE models (
                id TEXT PRIMARY KEY,
                company TEXT,
                model TEXT,
                canonical_slug TEXT,
                hugging_face_id TEXT,
                name TEXT,
                created INTEGER,
                created_date DATETIME,
                description TEXT,
                context_length INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE input_modalities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT,
                modality TEXT,
                FOREIGN KEY (model_id) REFERENCES models (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE output_modalities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT,
                modality TEXT,
                FOREIGN KEY (model_id) REFERENCES models (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE pricings (
                model_id TEXT PRIMARY KEY,
                prompt TEXT,
                completion TEXT,
                request TEXT,
                image TEXT,
                web_search TEXT,
                internal_reasoning TEXT,
                input_cache_read TEXT,
                input_cache_write TEXT,
                FOREIGN KEY (model_id) REFERENCES models (id)
            )
        ''')
        
        # Insert data
        for model_data in models_data.get('data', []):
            model_id = model_data.get('id')
            company = model_id.split('/')[0] if model_id and '/' in model_id else None
            model_name = model_id.split('/')[1] if model_id and '/' in model_id else None
            created_timestamp = model_data.get('created')
            created_date = datetime.fromtimestamp(created_timestamp) if created_timestamp else None
            
            cursor.execute('''
                INSERT OR REPLACE INTO models (id, company, model, canonical_slug, hugging_face_id, name, created, created_date, description, context_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                model_id, company, model_name, model_data.get('canonical_slug'), 
                model_data.get('hugging_face_id'), model_data.get('name'),
                created_timestamp, created_date, model_data.get('description'), 
                model_data.get('context_length')
            ))
            
            # Insert modalities
            for modality in model_data.get('architecture', {}).get('input_modalities', []):
                cursor.execute('INSERT INTO input_modalities (model_id, modality) VALUES (?, ?)', (model_id, modality))
            
            for modality in model_data.get('architecture', {}).get('output_modalities', []):
                cursor.execute('INSERT INTO output_modalities (model_id, modality) VALUES (?, ?)', (model_id, modality))
            
            # Insert pricing
            pricing = model_data.get('pricing', {})
            cursor.execute('''
                INSERT OR REPLACE INTO pricings (model_id, prompt, completion, request, image, web_search, internal_reasoning, input_cache_read, input_cache_write)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                model_id, pricing.get('prompt'), pricing.get('completion'), 
                pricing.get('request'), pricing.get('image'),
                pricing.get('web_search'), pricing.get('internal_reasoning'),
                pricing.get('input_cache_read'), pricing.get('input_cache_write')
            ))
        
        conn.commit()
        conn.close()
        
        model_count = len(models_data.get('data', []))
        return f"Successfully rebuilt database with {model_count} models"
        
    except Exception as e:
        return f"Error rebuilding database: {str(e)}"

# Check if the database needs a daily update
def daily_update_database():
    update_flag_file = "last_update.txt"

    # Check if the update flag file exists
    if os.path.exists(update_flag_file):
        with open(update_flag_file, "r") as file:
            last_update = file.read().strip()

        # Compare the last update date with today's date
        if last_update == datetime.now().strftime("%Y-%m-%d"):
            print("Database is already up-to-date.")
            return

    # Update the database and write today's date to the flag file
    print("Updating database...")
    rebuild_database()
    with open(update_flag_file, "w") as file:
        file.write(datetime.now().strftime("%Y-%m-%d"))

# Call the daily update function at the start of the application
daily_update_database()

mcp = FastMCP("OpenRouter AI")
mcp_app = mcp.http_app(path='/')

app = FastAPI(lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)


@app.api_route("/", methods=["GET", "POST"])
def root():
    """Root endpoint to handle base URL requests."""
    return {
        "message": "Welcome to the OpenRouterAI service!",
        "instructions": {
            "REST API Usage": {
                "Health Check": "Send a GET request to /health to check the service status.",
                "Search Models": "Send a GET request to /models with query parameters to search for AI models.",
                "Rebuild Database": "Send a POST request to /rebuild-database to refresh the database."
            },
            "Model Context Protocol (MCP) Usage": {
                "Initialize": "Use the /mcp endpoint with the 'initialize' method to start an MCP session.",
                "List Tools": "Use the /mcp endpoint with the 'tools/list' method to list available tools.",
                "Call Tools": "Use the /mcp endpoint with the 'tools/call' method to perform specific actions like inference or database rebuild."
            }
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint.
    
    Returns a simple status response to verify that the API is running.
    
    Returns:
        dict: A dictionary containing the service status.
            - status (str): Always "ok" if the service is running.
    """
    return {"status": "ok"}

@app.get("/models")
def search_models_api(
    company: Optional[str] = None,
    input_modality: Optional[str] = None,
    output_modality: Optional[str] = None,
    is_free: Optional[bool] = None,
    name_like: Optional[str] = None,
    min_context_length: Optional[int] = None,
    price_type: Optional[str] = "prompt",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_price_inclusive: Optional[bool] = True,
    max_price_inclusive: Optional[bool] = False,
):
    """Search for AI models with advanced filtering options.
    
    This endpoint allows searching through the OpenRouter AI models database
    with various filters including company, modalities, pricing, and more.
    
    Query Parameters:
        company (str, optional): Filter by model provider company (e.g., "OpenAI", "Anthropic")
        input_modality (str, optional): Filter by input type (e.g., "text", "image")
        output_modality (str, optional): Filter by output type (e.g., "text", "image")
        is_free (bool, optional): Filter for free models only (true) or exclude free models (false)
        name_like (str, optional): Search models by name (partial match)
        min_context_length (int, optional): Minimum context window size
        price_type (str, optional): Which pricing to filter by ("prompt" or "completion", default: "prompt")
        min_price (float, optional): Minimum price per million tokens
        max_price (float, optional): Maximum price per million tokens
        min_price_inclusive (bool, optional): Whether min_price bound is inclusive (default: true)
        max_price_inclusive (bool, optional): Whether max_price bound is inclusive (default: false)
    
    Returns:
        dict: A dictionary containing the search results.
            - models (List[Model]): List of matching models with their details including pricing.
    
    Example:
        GET /models?company=OpenAI&is_free=false&min_price=10&max_price=50
    """
    models = Model.search(
        company=company,
        input_modality=input_modality,
        output_modality=output_modality,
        is_free=is_free,
        name_like=name_like,
        min_context_length=min_context_length,
        price_type=price_type,
        min_price=min_price,
        max_price=max_price,
        min_price_inclusive=min_price_inclusive,
        max_price_inclusive=max_price_inclusive,
    )
    return {"models": models}

@app.post("/rebuild-database")
def rebuild_database_api():
    """Rebuild the models database from the OpenRouter API.
    
    This endpoint fetches the latest model information from the OpenRouter API
    and completely rebuilds the local SQLite database. This is useful for:
    - Getting the most up-to-date model list
    - Refreshing pricing information
    - Adding newly released models
    - Fixing any data inconsistencies
    
    The operation may take several seconds as it needs to:
    1. Fetch data from the OpenRouter API
    2. Drop and recreate all database tables
    3. Insert fresh model data
    
    Returns:
        dict: A dictionary containing the operation result.
            - message (str): Success message with model count or error description.
    
    Example Response:
        {"message": "Successfully rebuilt database with 150 models"}
    
    Note:
        This is a destructive operation that will replace all existing data.
        Use with caution in production environments.
    """
    return {"message": rebuild_database()}

@mcp.tool()
def rebuild_database_tool() -> str:
    """Rebuild the models database by fetching fresh data from OpenRouter API.
    
    This tool fetches the latest model information from the OpenRouter API
    and completely rebuilds the local SQLite database. It's useful for:
    - Getting the most up-to-date model list
    - Refreshing pricing information  
    - Adding newly released models
    - Fixing any data inconsistencies
    
    The operation performs these steps:
    1. Connect to OpenRouter API (https://openrouter.ai/api/v1/models)
    2. Fetch current model data
    3. Drop and recreate database tables
    4. Insert fresh model information
    5. Return success/error message
    
    Returns:
        str: A message indicating success with model count or error description.
        
    Example:
        "Successfully rebuilt database with 150 models"
        
    Note:
        This is a destructive operation that replaces all existing data.
        The operation may take several seconds to complete.
    """
    return rebuild_database()

@mcp.tool()
def search_models(
    company: Optional[str] = None,
    input_modality: Optional[str] = None,
    output_modality: Optional[str] = None,
    is_free: Optional[bool] = None,
    name_like: Optional[str] = None,
    min_context_length: Optional[int] = None,
    price_type: Optional[str] = "prompt",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_price_inclusive: Optional[bool] = True,
    max_price_inclusive: Optional[bool] = False,
) -> List[Model]:
    """Search for AI models with advanced filtering and pricing options.
    
    This tool provides comprehensive search capabilities for the OpenRouter AI models
    database, allowing filtering by various criteria including pricing information.
    
    Parameters:
        company (str, optional): Filter by model provider company (e.g., "OpenAI", "Anthropic")
        input_modality (str, optional): Filter by input type ("text", "image", etc.)
        output_modality (str, optional): Filter by output type ("text", "image", etc.)
        is_free (bool, optional): Filter for free models (true) or exclude free models (false)
        name_like (str, optional): Search models by name using partial string matching
        min_context_length (int, optional): Minimum context window size in tokens
        price_type (str, optional): Which pricing to filter by ("prompt" or "completion", default: "prompt")
        min_price (float, optional): Minimum price per million tokens
        max_price (float, optional): Maximum price per million tokens  
        min_price_inclusive (bool, optional): Whether min_price bound is inclusive (default: true)
        max_price_inclusive (bool, optional): Whether max_price bound is inclusive (default: false)
    
    Returns:
        List[Model]: List of matching models with complete information including:
            - Basic model details (id, name, company, description)
            - Technical specs (context_length, modalities)
            - Pricing information (prompt_price, completion_price per million tokens)
    
    Examples:
        # Find all OpenAI models
        search_models(company="OpenAI")
        
        # Find free models with at least 32K context
        search_models(is_free=True, min_context_length=32000)
        
        # Find models costing between $10-50 per million prompt tokens
        search_models(min_price=10, max_price=50, price_type="prompt")
        
        # Find models by name
        search_models(name_like="GPT")
    
    Note:
        All prices are returned in dollars per million tokens for easy comparison.
        Free models will have prices of 0.0.
    """
    return Model.search(
        company=company,
        input_modality=input_modality,
        output_modality=output_modality,
        is_free=is_free,
        name_like=name_like,
        min_context_length=min_context_length,
        price_type=price_type,
        min_price=min_price,
        max_price=max_price,
        min_price_inclusive=min_price_inclusive,
        max_price_inclusive=max_price_inclusive,
    )

# Background task to check database freshness periodically
async def periodic_database_update():
    while True:
        print("Checking database freshness...")
        daily_update_database()
        # Wait for 24 hours before the next check
        await asyncio.sleep(24 * 60 * 60)