from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import sqlite3
from typing import List, Optional
from contextlib import asynccontextmanager

DB_NAME = "models.db"

def get_db_connection():
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

    @classmethod
    def search(
        cls,
        company: Optional[str] = Field(None, description="The company that created the model."),
        input_modality: Optional[str] = Field(None, description="The input modality of the model."),
        output_modality: Optional[str] = Field(None, description="The output modality of the model."),
        is_free: Optional[bool] = Field(None, description="Whether the model is free to use."),
        name_like: Optional[str] = Field(None, description="A string to search for in the model name."),
        min_context_length: Optional[int] = Field(None, description="The minimum context length of the model."),
    ) -> List["Model"]:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT m.* FROM models m"
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
            joins.add(" LEFT JOIN pricings p ON m.id = p.model_id")
            if "WHERE" not in query:
                query += " WHERE"
            else:
                query += " AND"
            if is_free:
                query += " (p.prompt IS NULL OR p.prompt = '0.0') AND (p.completion IS NULL OR p.completion = '0.0') AND (p.request IS NULL OR p.request = '0.0') AND (p.image IS NULL OR p.image = '0.0')"
            else:
                query += " ((p.prompt IS NOT NULL AND p.prompt != '0.0') OR (p.completion IS NOT NULL AND p.completion != '0.0') OR (p.request IS NOT NULL AND p.request != '0.0') OR (p.image IS NOT NULL AND p.image != '0.0'))"

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

        final_query = query.replace("SELECT m.* FROM models m", "SELECT m.* FROM models m" + "".join(list(joins)))
        
        cursor.execute(final_query, params)
        models = cursor.fetchall()
        conn.close()

        return [Model(**dict(row)) for row in models]

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 OpenRouter AI MCP Server is running!")
    print("📋 Available endpoints:")
    print("  - GET  /health")
    print("    Health check endpoint")
    print("  - GET  /models")
    print("    Search models with query parameters:")
    print("    ?company={str}           - Filter by company")
    print("    ?input_modality={str}    - Filter by input modality")
    print("    ?output_modality={str}   - Filter by output modality")
    print("    ?is_free={bool}          - Filter by free models")
    print("    ?name_like={str}         - Search in model name")
    print("    ?min_context_length={int} - Minimum context length")
    print("  - POST /mcp")
    print("    MCP protocol endpoint with methods:")
    print("    • initialize     - Initialize MCP session")
    print("    • tools/list     - List available tools")
    print("    • tools/call     - Call tools (inference, search_models)")
    print("  - GET  /docs")
    print("    FastAPI interactive documentation")
    print(f"🌐 Server URL: http://127.0.0.1:8000")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/models")
def search_models_api(
    company: Optional[str] = None,
    input_modality: Optional[str] = None,
    output_modality: Optional[str] = None,
    is_free: Optional[bool] = None,
    name_like: Optional[str] = None,
    min_context_length: Optional[int] = None,
):
    """Search for models via REST API."""
    models = Model.search(
        company=company,
        input_modality=input_modality,
        output_modality=output_modality,
        is_free=is_free,
        name_like=name_like,
        min_context_length=min_context_length,
    )
    return {"models": models}

mcp = FastMCP("OpenRouter AI")

@mcp.tool()
def inference(prompt: str) -> str:
    """Generate a response to the given prompt."""
    # In a real implementation, this would call the model to get a response.
    # For now, we'll just return a dummy response.
    return f"Response to: {prompt}"

@mcp.tool()
def search_models(
    company: Optional[str] = None,
    input_modality: Optional[str] = None,
    output_modality: Optional[str] = None,
    is_free: Optional[bool] = None,
    name_like: Optional[str] = None,
    min_context_length: Optional[int] = None,
) -> List[Model]:
    """Search for models based on various criteria."""
    return Model.search(
        company=company,
        input_modality=input_modality,
        output_modality=output_modality,
        is_free=is_free,
        name_like=name_like,
        min_context_length=min_context_length,
    )

# Mount the MCP server to the FastAPI app
from fastmcp.server.http import create_streamable_http_app
mcp_app = create_streamable_http_app(mcp, "/mcp")
app.mount("/mcp", mcp_app)