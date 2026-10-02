import type { TimeWindow } from "./api";

const CATEGORY_LABELS: Record<string, string> = {
  "agentic-generative-ai": "AI Agents & Generative AI",
  "machine-learning-classical-ai": "Machine Learning",
  "vision-speech-robotics": "Vision, Voice & Robotics",
  "data-search-retrieval": "Data, Search & Retrieval",
  "ai-products-engineering-infrastructure": "AI Products & Infrastructure",
  "safety-evaluation-governance": "AI Safety & Evaluation",
};
export const WINDOWS = [
  { value: "day", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "all", label: "All time" },
] as const;
export function labelize(value: string) {
  const labels: Record<string, string> = {
    "models-apis": "Models & APIs",
    "api-change": "API change",
    "agents-orchestration": "Agents & orchestration",
    "evaluation-observability": "Evaluation & observability",
    "inference-serving": "Inference & serving",
    "infrastructure-hardware": "Infrastructure & hardware",
    "retrieval-data": "Retrieval & data",
    "safety-security": "Safety & security",
    "training-fine-tuning": "Training & fine-tuning",
  };
  return labels[value] ?? value.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function sourceDisplayName(value: string) {
  const labels: Record<string, string> = {
    "anthropic-engineering": "Anthropic Engineering",
    "aws-machine-learning": "AWS Machine Learning",
    "crewai-blog": "CrewAI",
    "github-changelog": "GitHub Changelog",
    "google-developers": "Google Developers",
    "langchain-blog": "LangChain",
    "letta-blog": "Letta",
    "mcp-blog": "MCP",
    "microsoft-foundry": "Microsoft Foundry",
    "simon-agentic-engineering": "Simon Willison",
  };
  if (labels[value]) return labels[value];
  return value
    .replace(/-(blog|news|changelog|technical-blog)$/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function categoryLabel(value: string) {
  return CATEGORY_LABELS[value] ?? labelize(value);
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

export function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

export function windowLabel(value: TimeWindow) {
  return WINDOWS.find((option) => option.value === value)?.label ?? value;
}

export function windowHeading(value: TimeWindow) {
  const headings: Record<TimeWindow, string> = {
    day: "Today’s AI Agent Updates",
    week: "This Week’s AI Agent Updates",
    month: "This Month’s AI Agent Updates",
    all: "All AI Agent Updates",
  };
  return headings[value];
}

export function isoWeekNumber(date: Date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNumber = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNumber);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil((((target.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

export function formatIssueRange(start: string | null | undefined, end: string | undefined, selectedWindow: TimeWindow) {
  if (selectedWindow === "all" || !start || !end) return windowLabel(selectedWindow);
  const startDate = new Date(start);
  const endDate = new Date(end);
  const startText = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(startDate);
  const endText = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(endDate);
  return `${startText}–${endText}`;
}

export function formatEdition(
  selectedWindow: TimeWindow,
  issueDate: Date,
  issueNumber: string,
  issueRange: string,
) {
  if (selectedWindow === "day") {
    return {
      label: "Daily Brief",
      period: new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(issueDate),
    };
  }
  if (selectedWindow === "month") {
    return {
      label: new Intl.DateTimeFormat(undefined, {
        month: "long",
        year: "numeric",
      }).format(issueDate),
      period: "Monthly briefing",
    };
  }
  if (selectedWindow === "all") {
    return {
      label: "Archive",
      period: "All collected updates",
    };
  }
  return {
    label: `Week ${issueNumber}`,
    period: issueRange,
  };
}

export function readFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const requestedWindow = params.get("window");
  const validWindow = WINDOWS.some((option) => option.value === requestedWindow)
    ? requestedWindow as TimeWindow
    : "week";
  return {
    window: validWindow,
    source: params.get("source") ?? "all",
    category: params.get("category") ?? params.get("topic") ?? "all",
    includeContextual: params.get("context") === "broader",
  };
}
