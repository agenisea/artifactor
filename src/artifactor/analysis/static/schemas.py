"""Pydantic models for static analysis output."""

from pathlib import Path

from pydantic import BaseModel, Field


class CodeEntity(BaseModel):
    """A named declaration extracted from the AST."""

    name: str
    entity_type: str  # function, class, method, interface, struct, enum
    file_path: Path
    start_line: int
    end_line: int
    language: str
    signature: str | None = None
    docstring: str | None = None
    parent: str | None = None
    children: list[str] = Field(default_factory=lambda: list[str]())


class ASTForest(BaseModel):
    """All code entities extracted from the repository."""

    entities: list[CodeEntity] = Field(
        default_factory=lambda: list[CodeEntity]()
    )


class CallEdge(BaseModel):
    """A call relationship between two code locations."""

    caller_file: str
    caller_line: int
    callee: str
    receiver: str | None = None  # "obj" in obj.method()
    call_type: str = "direct"  # direct, method, constructor
    confidence: str = "high"  # high, medium, low


class CallGraph(BaseModel):
    """All call edges discovered in the repository."""

    edges: list[CallEdge] = Field(default_factory=lambda: list[CallEdge]())


class DependencyEdge(BaseModel):
    """An import/dependency relationship between files or modules."""

    source_file: str
    target: str
    import_type: str = "module"  # module, symbol, wildcard, dynamic
    symbols: list[str] = Field(default_factory=lambda: list[str]())


class DependencyGraph(BaseModel):
    """All import/dependency edges in the repository."""

    edges: list[DependencyEdge] = Field(
        default_factory=lambda: list[DependencyEdge]()
    )


class SchemaAttribute(BaseModel):
    """A column or field in a data model."""

    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    constraints: list[str] = Field(default_factory=lambda: list[str]())


class SchemaRelationship(BaseModel):
    """A foreign key or ORM relationship."""

    target_entity: str
    relationship_type: str = "one_to_many"
    foreign_key: str | None = None


class SchemaEntity(BaseModel):
    """A data model (table, ORM model, schema definition)."""

    name: str
    source_type: str  # orm_model, sql_definition, migration, schema_file
    file_path: str
    start_line: int
    attributes: list[SchemaAttribute] = Field(
        default_factory=lambda: list[SchemaAttribute]()
    )
    relationships: list[SchemaRelationship] = Field(
        default_factory=lambda: list[SchemaRelationship]()
    )


class SchemaMap(BaseModel):
    """All data schemas found in the repository."""

    entities: list[SchemaEntity] = Field(
        default_factory=lambda: list[SchemaEntity]()
    )


class APIParameter(BaseModel):
    """A parameter for an API endpoint."""

    name: str
    location: str = "query"  # path, query, body, header
    data_type: str = "string"
    required: bool = True


class APIEndpoint(BaseModel):
    """A discovered HTTP API endpoint."""

    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    handler_file: str
    handler_function: str
    handler_line: int
    parameters: list[APIParameter] = Field(
        default_factory=lambda: list[APIParameter]()
    )
    response_type: str | None = None
    auth_required: bool | None = None


class APIEndpoints(BaseModel):
    """All API endpoints found in the repository."""

    endpoints: list[APIEndpoint] = Field(
        default_factory=lambda: list[APIEndpoint]()
    )


class StaticAnalysisResult(BaseModel):
    """Combined output of all static analysis modules."""

    ast_forest: ASTForest = Field(default_factory=ASTForest)
    call_graph: CallGraph = Field(default_factory=CallGraph)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    schema_map: SchemaMap = Field(default_factory=SchemaMap)
    api_endpoints: APIEndpoints = Field(default_factory=APIEndpoints)
