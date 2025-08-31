import httpx
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

DB_NAME = "models.db"

# Register the adapter
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

def init_db() -> sqlite3.Connection:
    """Initializes the database and creates the tables."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Drop existing tables to start fresh
    cursor.execute("DROP TABLE IF EXISTS models")
    cursor.execute("DROP TABLE IF EXISTS architectures")
    cursor.execute("DROP TABLE IF EXISTS input_modalities")
    cursor.execute("DROP TABLE IF EXISTS output_modalities")
    cursor.execute("DROP TABLE IF EXISTS pricings")
    cursor.execute("DROP TABLE IF EXISTS top_providers")
    cursor.execute("DROP TABLE IF EXISTS per_request_limits")
    cursor.execute("DROP TABLE IF EXISTS supported_parameters")

    # Create new tables
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
        CREATE TABLE architectures (
            model_id TEXT PRIMARY KEY,
            modality TEXT,
            tokenizer TEXT,
            instruct_type TEXT,
            FOREIGN KEY (model_id) REFERENCES models (id)
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
    cursor.execute('''
        CREATE TABLE top_providers (
            model_id TEXT PRIMARY KEY,
            context_length INTEGER,
            max_completion_tokens INTEGER,
            is_moderated INTEGER,
            FOREIGN KEY (model_id) REFERENCES models (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE per_request_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT,
            limit_key TEXT,
            limit_value TEXT,
            FOREIGN KEY (model_id) REFERENCES models (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE supported_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT,
            parameter TEXT,
            FOREIGN KEY (model_id) REFERENCES models (id)
        )
    ''')
    conn.commit()
    return conn

def insert_model(cursor: sqlite3.Cursor, model_data: Dict[str, Any]) -> None:
    model_id = model_data.get('id')
    company = model_id.split('/')[0] if model_id and '/' in model_id else None
    model_name = model_id.split('/')[1] if model_id and '/' in model_id else None
    created_timestamp = model_data.get('created')
    created_date = datetime.fromtimestamp(created_timestamp) if created_timestamp else None
    cursor.execute('''
        INSERT OR REPLACE INTO models (id, company, model,canonical_slug, hugging_face_id, name, created, created_date, description, context_length)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        model_id, company, model_name, model_data.get('canonical_slug'), model_data.get('hugging_face_id'), model_data.get('name'),
        created_timestamp, created_date, model_data.get('description'), model_data.get('context_length')
    ))

def insert_architecture(cursor: sqlite3.Cursor, model_id: str, architecture_data: Dict[str, Any]) -> None:
    cursor.execute('''
        INSERT OR REPLACE INTO architectures (model_id, modality, tokenizer, instruct_type)
        VALUES (?, ?, ?, ?)
    ''', (model_id, architecture_data.get('modality'), architecture_data.get('tokenizer'), architecture_data.get('instruct_type')))

def insert_modalities(cursor: sqlite3.Cursor, model_id: str, modalities_data: Dict[str, Any]) -> None:
    for modality in modalities_data.get('input_modalities', []):
        cursor.execute('INSERT INTO input_modalities (model_id, modality) VALUES (?, ?)', (model_id, modality))
    
    for modality in modalities_data.get('output_modalities', []):
        cursor.execute('INSERT INTO output_modalities (model_id, modality) VALUES (?, ?)', (model_id, modality))

def insert_pricing(cursor: sqlite3.Cursor, model_id: str, pricing_data: Dict[str, Any]) -> None:
    cursor.execute('''
        INSERT OR REPLACE INTO pricings (model_id, prompt, completion, request, image, web_search, internal_reasoning, input_cache_read, input_cache_write)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        model_id, pricing_data.get('prompt'), pricing_data.get('completion'), pricing_data.get('request'),
        pricing_data.get('image'), pricing_data.get('web_search'), pricing_data.get('internal_reasoning'),
        pricing_data.get('input_cache_read'), pricing_data.get('input_cache_write')
    ))

def insert_top_provider(cursor: sqlite3.Cursor, model_id: str, top_provider_data: Dict[str, Any]) -> None:
    cursor.execute('''
        INSERT OR REPLACE INTO top_providers (model_id, context_length, max_completion_tokens, is_moderated)
        VALUES (?, ?, ?, ?)
    ''', (
        model_id, top_provider_data.get('context_length'), top_provider_data.get('max_completion_tokens'),
        1 if top_provider_data.get('is_moderated') else 0
    ))

def insert_per_request_limits(cursor: sqlite3.Cursor, model_id: str, per_request_limits_data: Dict[str, Any]) -> None:
    for key, value in per_request_limits_data.items():
        cursor.execute('INSERT INTO per_request_limits (model_id, limit_key, limit_value) VALUES (?, ?, ?)', (model_id, key, str(value)))

def insert_supported_parameters(cursor: sqlite3.Cursor, model_id: str, supported_parameters_data: List[str]) -> None:
    for param in supported_parameters_data:
        cursor.execute('INSERT INTO supported_parameters (model_id, parameter) VALUES (?, ?)', (model_id, param))

def insert_models(conn: sqlite3.Connection, models_data: Dict[str, Any]) -> None:
    """Inserts model data into the normalized database tables."""
    cursor = conn.cursor()
    
    for model_data in models_data.get('data', []):
        model_id = model_data.get('id')
        insert_model(cursor, model_data)

        architecture_data = model_data.get('architecture')
        if architecture_data:
            insert_architecture(cursor, model_id, architecture_data)
            insert_modalities(cursor, model_id, architecture_data)

        pricing_data = model_data.get('pricing')
        if pricing_data:
            insert_pricing(cursor, model_id, pricing_data)

        top_provider_data = model_data.get('top_provider')
        if top_provider_data:
            insert_top_provider(cursor, model_id, top_provider_data)

        per_request_limits_data = model_data.get('per_request_limits')
        if per_request_limits_data:
            insert_per_request_limits(cursor, model_id, per_request_limits_data)

        supported_parameters_data = model_data.get('supported_parameters')
        if supported_parameters_data:
            insert_supported_parameters(cursor, model_id, supported_parameters_data)

    conn.commit()

def get_openrouter_models() -> None:
    """
    Fetches the list of available models from the OpenRouter API and stores them in a normalized SQLite database.
    """
    url = "https://openrouter.ai/api/v1/models"
    try:
        response = httpx.get(url)
        response.raise_for_status()
        models = response.json()
        
        conn = init_db()
        conn.execute("PRAGMA foreign_keys = ON")
        insert_models(conn, models)
        conn.close()
        
        print(f"Successfully fetched and stored {len(models.get('data', []))} models in {DB_NAME} with normalized schema.")

    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}.")
    except httpx.HTTPStatusError as exc:
        print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    get_openrouter_models()