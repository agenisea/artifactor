# pyright: reportUnusedFunction=false
# ruff: noqa: E501
"""Per-section system prompts and context builders for LLM synthesis.

Each section has a system prompt (instructions) and a context builder
(data selection from IntelligenceModel → JSON string).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from artifactor.constants import RelationshipType
from artifactor.intelligence.knowledge_graph import (
    GraphEntity,
    GraphRelationship,
)
from artifactor.intelligence.model import IntelligenceModel
from artifactor.intelligence.reasoning_graph import (
    InferredRisk,
    InferredRule,
    Purpose,
    Workflow,
    WorkflowStep,
)

# ── Token budget caps ────────────────────────────────────

MAX_ENTITIES = 30
MAX_RULES = 20
MAX_RISKS = 10
MAX_PURPOSES = 15
MAX_RELATIONSHIPS = 20
MAX_WORKFLOWS = 5
MAX_SAMPLE_RULES = 5
MAX_SAMPLE_RISKS = 5

# ── Serialization helpers ────────────────────────────────


def _serialize_entity(e: GraphEntity) -> dict[str, Any]:
    return {
        "name": e.name,
        "type": e.entity_type,
        "file": e.file_path,
        "line": e.start_line,
        "language": e.language,
        "signature": e.signature,
        "description": e.description,
    }


def _serialize_purpose(p: Purpose) -> dict[str, Any]:
    return {
        "entity_id": p.entity_id,
        "statement": p.statement,
        "confidence": p.confidence.value,
    }


def _serialize_rule(r: InferredRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "text": r.rule_text,
        "type": r.rule_type,
        "condition": r.condition,
        "consequence": r.consequence,
    }


def _serialize_risk(r: InferredRisk) -> dict[str, Any]:
    return {
        "id": r.id,
        "title": r.title,
        "type": r.risk_type,
        "severity": r.severity,
        "description": r.description,
        "file": r.file_path,
        "line": r.line,
    }


def _serialize_relationship(
    r: GraphRelationship,
) -> dict[str, Any]:
    return {
        "source": r.source_id,
        "target": r.target_id,
        "type": r.relationship_type,
    }


def _serialize_workflow(w: Workflow) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "description": w.description,
        "steps": [_serialize_step(s) for s in w.steps],
    }


def _serialize_step(s: WorkflowStep) -> dict[str, Any]:
    return {
        "order": s.order,
        "entity_id": s.entity_id,
        "description": s.description,
    }


def count_context_items(context_str: str) -> int:
    """Count total items across all arrays in a context string."""
    import re as _re

    match = _re.search(
        r"<context>(.*?)</context>", context_str, _re.DOTALL
    )
    if not match:
        return 0
    try:
        data: dict[str, Any] = json.loads(match.group(1))
        count = 0
        for value in data.values():
            if isinstance(value, list):
                count += len(value)  # type: ignore[arg-type]
            elif isinstance(value, (int, float)):
                count += 1
        return count
    except (json.JSONDecodeError, AttributeError):
        return 0


def _wrap_context(
    data: dict[str, Any], section_title: str
) -> str:
    """Wrap context data in XML tags with generation instruction."""
    return (
        "<context>\n"
        + json.dumps(data, indent=2)
        + "\n</context>\n\n"
        + f"Generate the {section_title} section."
    )


# ── Context builders ─────────────────────────────────────


def build_executive_overview_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    entity_types: dict[str, int] = {}
    languages: set[str] = set()
    files: set[str] = set()
    for e in kg.entities.values():
        entity_types[e.entity_type] = (
            entity_types.get(e.entity_type, 0) + 1
        )
        if e.language:
            languages.add(e.language)
        files.add(e.file_path)

    purposes = list(rg.purposes.values())[:MAX_PURPOSES]
    rules = list(rg.rules.values())[:MAX_SAMPLE_RULES]
    risks = list(rg.risks.values())[:MAX_SAMPLE_RISKS]

    return _wrap_context(
        {
            "stats": {
                "total_entities": len(kg.entities),
                "total_files": len(files),
                "languages": sorted(languages),
                "entity_types": entity_types,
                "total_rules": len(rg.rules),
                "total_workflows": len(rg.workflows),
                "total_relationships": len(kg.relationships),
            },
            "purposes": [
                _serialize_purpose(p) for p in purposes
            ],
            "sample_rules": [
                _serialize_rule(r) for r in rules
            ],
            "sample_risks": [
                _serialize_risk(r) for r in risks
            ],
        },
        "Executive Overview",
    )


def build_features_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    func_entities = [
        e
        for e in kg.entities.values()
        if e.entity_type in ("function", "method")
    ][:MAX_ENTITIES]

    file_purposes: list[dict[str, Any]] = []
    for fp, p in list(rg.purposes.items())[:MAX_PURPOSES]:
        file_purposes.append(
            {"file": fp, "purpose": p.statement}
        )

    return _wrap_context(
        {
            "function_entities": [
                _serialize_entity(e) for e in func_entities
            ],
            "file_purposes": file_purposes,
        },
        "Main Application Features",
    )


def build_personas_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    entities = list(kg.entities.values())[:MAX_ENTITIES]
    purposes = list(rg.purposes.values())[:MAX_PURPOSES]

    return _wrap_context(
        {
            "entities": [
                _serialize_entity(e) for e in entities
            ],
            "purposes": [
                _serialize_purpose(p) for p in purposes
            ],
        },
        "User Personas",
    )


def build_user_stories_context(
    model: IntelligenceModel,
) -> str:
    rg = model.reasoning_graph

    rules = list(rg.rules.values())[:MAX_RULES]
    workflows = rg.workflows[:MAX_WORKFLOWS]

    return _wrap_context(
        {
            "rules": [_serialize_rule(r) for r in rules],
            "workflows": [
                _serialize_workflow(w) for w in workflows
            ],
        },
        "User Stories",
    )


def build_security_requirements_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    auth_keywords = {
        "auth",
        "login",
        "logout",
        "token",
        "jwt",
        "oauth",
        "session",
        "password",
        "credential",
        "permission",
        "role",
        "rbac",
        "scope",
        "access",
        "policy",
        "guard",
        "middleware",
    }
    auth_entities = [
        e
        for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in auth_keywords)
    ][:MAX_ENTITIES]

    access_rules = [
        r
        for r in rg.rules.values()
        if r.rule_type == "access_control"
    ][:MAX_RULES]

    return _wrap_context(
        {
            "auth_entities": [
                _serialize_entity(e) for e in auth_entities
            ],
            "access_control_rules": [
                _serialize_rule(r) for r in access_rules
            ],
        },
        "Security Requirements",
    )


def build_system_overview_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    entities = list(kg.entities.values())[:MAX_ENTITIES]
    purposes = list(rg.purposes.values())[:MAX_PURPOSES]
    rels = kg.relationships[:MAX_RELATIONSHIPS]

    return _wrap_context(
        {
            "entities": [
                _serialize_entity(e) for e in entities
            ],
            "purposes": [
                _serialize_purpose(p) for p in purposes
            ],
            "relationships": [
                _serialize_relationship(r) for r in rels
            ],
        },
        "System Overview",
    )


def build_data_models_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    data_entities = [
        e
        for e in kg.entities.values()
        if e.entity_type in ("class", "table")
    ][:MAX_ENTITIES]

    data_ids = {e.id for e in data_entities}
    data_rels = [
        r
        for r in kg.relationships
        if r.source_id in data_ids or r.target_id in data_ids
    ][:MAX_RELATIONSHIPS]

    data_rules = [
        r
        for r in rg.rules.values()
        if r.rule_type == "data_constraint"
    ][:MAX_RULES]

    return _wrap_context(
        {
            "data_entities": [
                _serialize_entity(e) for e in data_entities
            ],
            "data_relationships": [
                _serialize_relationship(r) for r in data_rels
            ],
            "data_constraint_rules": [
                _serialize_rule(r) for r in data_rules
            ],
        },
        "Data Models",
    )


def build_interfaces_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph

    iface_entities = [
        e
        for e in kg.entities.values()
        if e.entity_type == "interface"
        or (
            e.entity_type == "class"
            and any(
                kw in e.name.lower()
                for kw in (
                    "service",
                    "repository",
                    "handler",
                    "controller",
                )
            )
        )
    ][:MAX_ENTITIES]

    rels = kg.relationships[:MAX_RELATIONSHIPS]

    return _wrap_context(
        {
            "interface_entities": [
                _serialize_entity(e) for e in iface_entities
            ],
            "relationships": [
                _serialize_relationship(r) for r in rels
            ],
        },
        "Interface Specifications",
    )


def build_ui_specs_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph

    ui_keywords = {
        "component",
        "page",
        "view",
        "screen",
        "form",
        "modal",
        "dialog",
        "button",
        "input",
        "layout",
        "template",
        "widget",
    }
    ui_entities = [
        e
        for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in ui_keywords)
        or any(
            ext in e.file_path
            for ext in (".tsx", ".jsx", ".vue", ".svelte")
        )
    ][:MAX_ENTITIES]

    return _wrap_context(
        {
            "ui_entities": [
                _serialize_entity(e) for e in ui_entities
            ],
        },
        "UI Specifications",
    )


def build_api_specs_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph

    endpoint_entities = [
        e
        for e in kg.entities.values()
        if e.entity_type == "endpoint"
        or (
            e.entity_type == "function"
            and any(
                kw in e.name.lower()
                for kw in (
                    "route",
                    "handler",
                    "endpoint",
                    "view",
                )
            )
        )
    ][:MAX_ENTITIES]

    return _wrap_context(
        {
            "endpoint_entities": [
                _serialize_entity(e) for e in endpoint_entities
            ],
        },
        "API Specifications",
    )


def build_integrations_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph

    import_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == RelationshipType.IMPORTS
    ][:MAX_RELATIONSHIPS]

    return _wrap_context(
        {
            "import_relationships": [
                _serialize_relationship(r) for r in import_rels
            ],
        },
        "Integration Points",
    )


def build_tech_stories_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    call_rels = [
        r
        for r in kg.relationships
        if r.relationship_type == RelationshipType.CALLS
    ][:MAX_RELATIONSHIPS]

    workflows = rg.workflows[:MAX_WORKFLOWS]

    return _wrap_context(
        {
            "call_relationships": [
                _serialize_relationship(r) for r in call_rels
            ],
            "workflows": [
                _serialize_workflow(w) for w in workflows
            ],
        },
        "Technical User Stories",
    )


def build_security_considerations_context(
    model: IntelligenceModel,
) -> str:
    kg = model.knowledge_graph
    rg = model.reasoning_graph

    vuln_keywords = {
        "eval",
        "exec",
        "system",
        "popen",
        "subprocess",
        "shell",
        "pickle",
        "deserialize",
        "unsafe",
        "raw_sql",
        "sql",
        "inject",
    }
    sensitive_keywords = {
        "password",
        "secret",
        "key",
        "token",
        "credential",
        "private",
    }

    vuln_entities = [
        e
        for e in kg.entities.values()
        if any(kw in e.name.lower() for kw in vuln_keywords)
    ][:MAX_ENTITIES]

    sensitive_entities = [
        e
        for e in kg.entities.values()
        if any(
            kw in e.name.lower() for kw in sensitive_keywords
        )
    ][:MAX_ENTITIES]

    risks = list(rg.risks.values())[:MAX_RISKS]

    return _wrap_context(
        {
            "vulnerability_entities": [
                _serialize_entity(e) for e in vuln_entities
            ],
            "sensitive_entities": [
                _serialize_entity(e)
                for e in sensitive_entities
            ],
            "risks": [_serialize_risk(r) for r in risks],
        },
        "Security Considerations",
    )


# ── Registries ───────────────────────────────────────────

CONTEXT_BUILDERS: dict[
    str, Callable[[IntelligenceModel], str]
] = {
    "executive_overview": build_executive_overview_context,
    "features": build_features_context,
    "personas": build_personas_context,
    "user_stories": build_user_stories_context,
    "security_requirements": build_security_requirements_context,
    "system_overview": build_system_overview_context,
    "data_models": build_data_models_context,
    "interfaces": build_interfaces_context,
    "ui_specs": build_ui_specs_context,
    "api_specs": build_api_specs_context,
    "integrations": build_integrations_context,
    "tech_stories": build_tech_stories_context,
    "security_considerations": build_security_considerations_context,
}

SECTION_SYSTEM_PROMPTS: dict[str, str] = {
    "executive_overview": """You are a technical documentation writer. Generate the Executive Overview section for a software project's documentation.

## Output Requirements
- Start with a # Executive Overview heading
- Write a one-paragraph summary of what the project does based on file purposes
- Include "## At a Glance" with aggregate statistics as a bullet list
- Include "## Key Capabilities" highlighting 3-5 main capabilities derived from rules and purposes
- Write in third person, present tense
- Every claim must be grounded in the provided context data
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent features not present in the context
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Suggest improvements or changes
- Repeat the same information in multiple places""",
    "features": """You are a technical documentation writer. Generate the Main Application Features section.

## Output Requirements
- Start with a # Main Application Features heading
- Group features by functional area (inferred from file purposes and function names)
- For each feature area, write a brief description of what it does
- Include "## Feature Summary" with a table: Feature | Description | Key Functions
- Write in third person, present tense
- Ground every claim in the provided entities and file purposes
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent features not present in the context
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Simply list function names without explaining what they do
- Repeat the same information in multiple places""",
    "personas": """You are a technical documentation writer. Generate the User Personas section.

## Output Requirements
- Start with a # User Personas heading
- Identify 2-4 personas from the code patterns (admin, developer, end user, etc.)
- For each persona, write: who they are, what they do, and which parts of the system they interact with
- Use the entity names and file purposes to ground persona descriptions
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent personas with no evidence in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Create generic personas disconnected from the actual codebase""",
    "user_stories": """You are a technical documentation writer. Generate the User Stories section.

## Output Requirements
- Start with a # User Stories heading
- Convert each business rule into a proper user story: "As a [role], I want [action], so that [outcome]"
- Group stories by theme (validation, access control, workflow, data, etc.)
- If workflows are provided, create stories that describe the end-to-end flow
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent stories not grounded in the provided rules
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Use generic outcomes — tie each outcome to the specific rule type""",
    "security_requirements": """You are a technical documentation writer. Generate the Security Requirements section.

## Output Requirements
- Start with a # Security Requirements heading
- Include "## Authentication" listing auth mechanisms found in the code
- Include "## Authorization" listing access control patterns
- Include "## Access Control Rules" summarizing business rules related to access
- If no security patterns are found, state that explicitly
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent security mechanisms not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Recommend security improvements (just document what exists)""",
    "system_overview": """You are a technical documentation writer. Generate the System Overview section.

## Output Requirements
- Start with a # System Overview heading
- Write a 2-3 paragraph architectural narrative describing the system's structure
- Include "## Module Structure" describing the main modules/directories and their responsibilities
- Include "## Key Relationships" describing how modules interact (calls, imports)
- Use the entity list and relationship data to build the narrative
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent architecture not evident from the entities and relationships
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Simply dump entity lists without narrative context""",
    "data_models": """You are a technical documentation writer. Generate the Data Models section.

## Output Requirements
- Start with a # Data Models heading
- Describe each data entity (class, table) with its purpose and key attributes
- Include "## Entity Relationships" describing how data entities relate to each other
- If data constraint rules exist, include "## Data Constraints" section
- If no data entities exist, explain that the project may use dynamic data structures
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent data models not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Generate ER diagrams (Mermaid) — just describe in prose""",
    "interfaces": """You are a technical documentation writer. Generate the Interface Specifications section.

## Output Requirements
- Start with a # Interface Specifications heading
- Describe each interface/protocol entity and its contract
- Include "## Service Boundaries" for service/repository/handler classes
- Describe how interfaces are used based on relationships
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent interfaces not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Simply list names without explaining their purpose""",
    "ui_specs": """You are a technical documentation writer. Generate the UI Specifications section.

## Output Requirements
- Start with a # UI Specifications heading
- Group UI entities by type (pages, components, forms, modals, etc.)
- Describe each component's likely purpose based on its name, file path, and type
- Include "## Component Summary" with a count and breakdown
- If no UI entities exist, explain that the project may be backend-only or use a separate frontend
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent UI components not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Describe visual layout — focus on functional purpose""",
    "api_specs": """You are a technical documentation writer. Generate the API Specifications section.

## Output Requirements
- Start with a # API Specifications heading
- Include "## Endpoints" listing each endpoint with method, path, and description
- Include "## Route Handlers" for handler functions
- Describe the API's purpose based on endpoint patterns
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent endpoints not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Generate OpenAPI/Swagger specs — use prose and tables""",
    "integrations": """You are a technical documentation writer. Generate the Integration Points section.

## Output Requirements
- Start with a # Integration Points heading
- Group imports by external dependency (third-party modules)
- Describe what each major dependency is used for
- Include "## Dependency Overview" with a summary table: Module | Used By | Purpose
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent dependencies not present in the import data
- Include placeholder text like [TODO] or [PROJECT_NAME]
- List standard library imports as integration points""",
    "tech_stories": """You are a technical documentation writer. Generate the Technical User Stories section.

## Output Requirements
- Start with a # Technical User Stories heading
- Convert call chain relationships into technical stories about system behavior
- If workflows exist, describe each workflow as a narrative with steps
- Use the format: "When [trigger], the system [action sequence], resulting in [outcome]"
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent technical flows not present in the call data
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Simply list function calls without explaining the flow""",
    "security_considerations": """You are a technical documentation writer. Generate the Security Considerations section.

## Output Requirements
- Start with a # Security Considerations heading
- Include "## Potential Vulnerability Patterns" for entities matching dangerous patterns (eval, exec, SQL, etc.)
- Include "## Sensitive Data Handlers" for entities handling secrets/credentials
- Include "## Risk Assessment" summarizing LLM-detected risks by severity
- Include "## Coverage Summary" with a checklist of security aspects (auth, validation, encryption, etc.)
- Output valid Markdown only. No JSON wrapping.

## What You NEVER Do
- Invent security issues not present in the code
- Include placeholder text like [TODO] or [PROJECT_NAME]
- Recommend fixes — just document what exists and potential risks""",
}
