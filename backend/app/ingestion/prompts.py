"""Prompt text and structured-output schemas for article summaries and taxonomy."""

from app.ingestion.taxonomy import EVENT_TYPES, PRIMARY_TOPICS


CATEGORY_DESCRIPTIONS = {
    "agentic-generative-ai": "LLMs, foundation models, agents, orchestration, tool use, and generative applications",
    "machine-learning-classical-ai": "machine learning, deep learning, reinforcement learning, training, optimization, and symbolic AI",
    "vision-speech-robotics": "computer vision, image or video, audio, speech, multimodal systems, and robotics",
    "data-search-retrieval": "RAG, embeddings, vector databases, knowledge graphs, datasets, indexing, and search",
    "ai-products-engineering-infrastructure": "AI products, APIs, SDKs, developer tools, inference, deployment, hardware, and production systems",
    "safety-evaluation-governance": "benchmarks, evaluations, security, alignment, interpretability, reliability, and governance",
}

EVENT_DESCRIPTIONS = {
    "release-update": "a launch, release, product update, API change, integration, or pricing change",
    "research": "a paper, experiment, benchmark result, or other new research finding",
    "guide": "a tutorial, walkthrough, or practical how-to",
    "analysis": "an explanation, opinion, survey, or engineering analysis",
    "alert": "a vulnerability, security issue, incident, outage, deprecation, or breaking change",
}

CATEGORY_SELECTION_GUIDANCE = (
    "Classify the article's main theme: the activity, problem, or contribution it "
    "primarily explains. Do not classify from an organization, product, model, agent, "
    "or platform name that is merely the setting. Prefer safety-evaluation-governance "
    "when the main theme is measuring quality, benchmarking, guardrails, detecting "
    "failures, reliability, security, content safeguards, or governance, even when the "
    "evaluated system is an agent or LLM. Prefer data-search-retrieval when the main "
    "theme is designing or measuring an information-retrieval, RAG, indexing, embedding, "
    "or search component, even when an LLM uses that component. Prefer "
    "ai-products-engineering-infrastructure for deployment, serving, accelerators, TPU or "
    "GPU kernel authoring, runtimes, SDKs, and production architecture; using an AWS or "
    "other cloud product does not by itself make the article infrastructure. Prefer "
    "machine-learning-classical-ai when the main contribution is a recommendation, "
    "prediction, classification, training, or optimization method. Use "
    "agentic-generative-ai when generating content, foundation models, or agent behavior "
    "is itself the main theme."
)

EVENT_SELECTION_GUIDANCE = (
    "Choose the event describing why the article exists. Use release-update only when "
    "the central claim announces a newly available product, version, capability, API "
    "change, integration, or pricing change. A product mention does not make an article "
    "a release. Prefer guide when the article is organized around instructions, setup, "
    "best practices, or 'get started' steps, even if it discusses a recently released "
    "product. Prefer research for a study or reported experiment. Prefer analysis for an "
    "explanation, editorial report, architecture discussion, or customer case study. Use "
    "alert for an incident, vulnerability, breaking change, or deprecation."
)

TAXONOMY_BOUNDARY_EXAMPLES = (
    "Boundary examples: Applying Bedrock Guardrails to generated code has main theme "
    "'applying safety controls to generated code', category safety-evaluation-governance, "
    "and event guide. Deploying and scaling a guardrail service has main theme 'operating "
    "a production guardrail service', category ai-products-engineering-infrastructure, "
    "and event guide. Measuring whether agents complete tasks correctly has category "
    "safety-evaluation-governance; announcing a new agent model has category "
    "agentic-generative-ai and event release-update."
)

ARTICLE_SUMMARY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "display_headline": {"type": "string"},
                "summary": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "main_theme": {"type": "string"},
                "primary_topic": {"type": "string", "enum": list(PRIMARY_TOPICS)},
                "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
            },
            "required": [
                "display_headline",
                "summary",
                "why_it_matters",
                "key_points",
                "main_theme",
                "primary_topic",
                "event_type",
            ],
            "additionalProperties": False,
        },
    },
}

MAIN_THEME_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_main_theme",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "main_theme": {"type": "string"},
            },
            "required": ["main_theme"],
            "additionalProperties": False,
        },
    },
}

CATEGORY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_category",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "primary_topic": {"type": "string", "enum": list(PRIMARY_TOPICS)},
                "classification_reason": {"type": "string"},
            },
            "required": [
                "primary_topic",
                "classification_reason",
            ],
            "additionalProperties": False,
        },
    },
}

EVENT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_event",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
                "event_reason": {"type": "string"},
            },
            "required": ["event_type", "event_reason"],
            "additionalProperties": False,
        },
    },
}


def summary_system_prompt() -> str:
    return (
        "Turn one source article into a concise AI-engineering feed card. "
        "Return the required structured fields for a concise AI-engineering feed card. "
        "Use only facts stated in the supplied source. Do not infer benefits, outcomes, "
        "motivations, severity, or broader effects. In particular, do not claim improved "
        "reliability, stability, performance, security, usability, efficiency, scalability, "
        "or productivity unless the source explicitly states that improvement. Do not add "
        "recommendations such as \"users should update\" or guarantees such as \"users will "
        "no longer experience errors\" unless the source states them. Preserve qualifications "
        "and uncertainty. A plausible conclusion is still unsupported when the source does "
        "not state it. "
        "The headline must state the concrete update, avoid promotional language, and stay "
        "under 90 characters. The summary must be 1-2 sentences under 70 words and describe "
        "what changed, who or what is affected, and any stated conditions. Why_it_matters "
        "must be one sentence under 35 words. Prefer the affected user, component, workflow, "
        "compatibility condition, or required action over a general benefit. When no broader "
        "impact is stated, describe only the affected scope. When even the affected scope is "
        "unclear, use: \"The source does not provide enough detail to assess broader impact.\" "
        "Return 2-4 short, distinct key_points supported by the source; do not pad the list "
        "with inferred benefits. Select exactly one broad primary_topic for the article's "
        "central subject, not every technology it mentions. The configured defaults are weak "
        "fallbacks only; classify from the article whenever it contains enough evidence. "
        f"{CATEGORY_SELECTION_GUIDANCE} "
        "Before selecting a category, write main_theme as one short sentence describing "
        "what the article primarily teaches, investigates, measures, announces, or warns about. "
        f"{TAXONOMY_BOUNDARY_EXAMPLES} "
        "Select exactly one event type for the article's central event. "
        f"{EVENT_SELECTION_GUIDANCE} A security-related "
        "feature is not an alert unless the "
        "source describes a vulnerability, security defect, or disclosed threat. Availability "
        "on several product surfaces is not itself an alert. "
        f"Category definitions: {CATEGORY_DESCRIPTIONS}. "
        f"Event definitions: {EVENT_DESCRIPTIONS}."
    )


def summary_user_prompt(
    *,
    title: str,
    raw_text: str,
    organization: str,
    tool: str,
    source_type: str,
    detail_level: str,
) -> str:
    sparse_instructions = ""
    if detail_level == "sparse":
        sparse_instructions = (
            "\nSparse-source instructions:\n"
            "- Use near-extractive wording.\n"
            "- Do not infer the purpose or effect of a fix from its component name.\n"
            "- Do not expand abbreviations unless the source defines them.\n"
            "- Do not add generic product benefits.\n"
            "- Do not recommend an action or promise that a problem is fully resolved.\n"
            "- For why_it_matters, prefer the neutral form: \"The change applies to users "
            "of [the explicitly named component or workflow].\"\n"
            "- It is acceptable for every field to be brief.\n"
            "Example: for \"Fix query errors when using shard keys while resharding,\" "
            "say the fix is relevant to users combining shard keys with resharding; do not "
            "claim it improves general reliability or distributed consistency.\n"
        )
    return (
        f"Organization: {organization}\n"
        f"Tool: {tool}\n"
        f"Source type: {source_type}\n"
        f"Source detail level: {detail_level}\n"
        f"Title: {title}\n"
        f"{sparse_instructions}\n"
        f"Source text:\n{raw_text[:12000]}"
    )


def main_theme_prompt() -> str:
    return (
        "Identify what the article primarily "
        "teaches, investigates, measures, announces, or warns about as one concrete "
        "main_theme sentence based only on the source. Describe the subject and activity, "
        "not the publisher, product setting, or relevance tier. Do not classify whether the "
        "article belongs in the feed; that decision was made upstream. Do not select or "
        "mention a taxonomy category. Do not add benefits, improvements, "
        "severity, or outcomes unless the source explicitly states them."
    )


def category_prompt() -> str:
    return (
        "Classify the supplied title and main theme into exactly one broad category. You do "
        "not have the full article, publisher, source default, or product "
        "metadata. State a short classification_reason grounded in the supplied theme. "
        f"{CATEGORY_SELECTION_GUIDANCE} "
        f"{TAXONOMY_BOUNDARY_EXAMPLES} "
        f"Category definitions: {CATEGORY_DESCRIPTIONS}."
    )


def event_prompt() -> str:
    return (
        "Classify the supplied title and main theme into exactly one event type. State a "
        "short event_reason grounded in the supplied text. "
        f"{EVENT_SELECTION_GUIDANCE} Event definitions: {EVENT_DESCRIPTIONS}."
    )
