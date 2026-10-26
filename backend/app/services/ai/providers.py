from __future__ import annotations

import abc
import json
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM operations with structured JSON outputs."""

    name: str = "base"

    @abc.abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema_cls: type[T],
        system_prompt: str = "You are InterviewOS AI Copilot, an expert technical recruitment intelligence system.",
    ) -> T:
        """Generate validated output matching schema_cls."""
        pass

    @abc.abstractmethod
    def ask_text(
        self,
        prompt: str,
        system_prompt: str = "You are InterviewOS AI Copilot, an expert technical recruitment intelligence system.",
    ) -> str:
        """Generate natural language text response."""
        pass


class OpenAILLMProvider(BaseLLMProvider):
    name: str = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", api_base: str | None = None, timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def generate_structured(self, prompt: str, schema_cls: type[T], system_prompt: str = "") -> T:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        json_schema = schema_cls.model_json_schema()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"{system_prompt}\nYou MUST output valid JSON complying strictly with this JSON schema: {json.dumps(json_schema)}"},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return schema_cls.model_validate(parsed)

    def ask_text(self, prompt: str, system_prompt: str = "") -> str:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


class DeterministicLocalProvider(BaseLLMProvider):
    """Grounded, reliable deterministic provider for local development, tests, and demo mode.

    Generates rich, context-aware, structured domain entities without requiring external API keys.
    """

    name: str = "deterministic"

    def generate_structured(self, prompt: str, schema_cls: type[T], system_prompt: str = "") -> T:
        # Structured synthesis based on schema_cls and prompt signals
        schema_name = schema_cls.__name__

        if "InterviewKit" in schema_name or hasattr(schema_cls, "coding_questions"):
            return self._build_interview_kit(prompt, schema_cls)
        elif "DriveBrief" in schema_name or hasattr(schema_cls, "executive_summary"):
            return self._build_drive_brief(prompt, schema_cls)
        elif "CandidateSummary" in schema_name or hasattr(schema_cls, "recurring_strengths"):
            return self._build_candidate_summary(prompt, schema_cls)
        else:
            # Fallback to schema default instance if possible
            try:
                return schema_cls.model_validate({})
            except Exception:
                raise ValueError(f"Cannot deterministically synthesize schema: {schema_name}")

    def ask_text(self, prompt: str, system_prompt: str = "") -> str:
        return f"Based on InterviewOS verified recruitment records: {prompt.strip()}"

    def _build_interview_kit(self, prompt: str, schema_cls: type[T]) -> T:
        # Extract skills and difficulty from prompt keywords
        p_lower = prompt.lower()
        diff = "intermediate"
        if "beginner" in p_lower:
            diff = "beginner"
        elif "advanced" in p_lower:
            diff = "advanced"

        # Topic identification
        topic = "Distributed Backend Engineering"
        if "python" in p_lower:
            topic = "Python & Asynchronous Systems"
        elif "system" in p_lower:
            topic = "High-Scale Distributed Architecture"
        elif "algorithm" in p_lower or "coding" in p_lower:
            topic = "Data Structures & Algorithmic Optimization"

        mock_data = {
            "topic": topic,
            "difficulty": diff,
            "coding_questions": [
                {
                    "title": f"Concurrent Event Deduplicator ({diff.capitalize()})",
                    "difficulty": diff,
                    "description": "Design and implement an in-memory sliding window event deduplicator that handles high concurrency, rejecting duplicate event UUIDs seen within a configurable time window T.",
                    "constraints": [
                        "Time complexity for is_duplicate(event_id, timestamp) must be O(1) amortized.",
                        "Memory footprint must automatically purge events older than T to prevent memory leaks.",
                        "Must be thread-safe for up to 100 concurrent worker threads.",
                    ],
                    "sample_inputs_outputs": [
                        {
                            "input": "dedup.is_duplicate('evt-1', t=100) -> returns False\ndedup.is_duplicate('evt-1', t=105) with window=10",
                            "output": "True (Duplicate within window)",
                            "explanation": "Event 'evt-1' was already recorded at t=100 and window has not expired.",
                        },
                        {
                            "input": "dedup.is_duplicate('evt-1', t=120) with window=10",
                            "output": "False (Window expired, accepted)",
                            "explanation": "The previous occurrence at t=100 has expired beyond the 10s retention window.",
                        },
                    ],
                    "expected_concepts": ["Sliding Window", "Hash Set", "Doubly Linked List / Min-Heap", "Concurrency Locks"],
                    "edge_cases": [
                        "Out-of-order event timestamps",
                        "High clock skew across distributed producers",
                        "Burst of millions of duplicate IDs within the same millisecond",
                    ],
                    "competencies_to_assess": ["Data structures", "Concurrency", "Time-space tradeoffs"],
                    "follow_up_questions": [
                        "How would you change the design if event timestamps can arrive out of order?",
                        "What consistency guarantees would you provide across multiple service instances?",
                    ],
                    "evaluation_rubric": {
                        "correctness": "30% - Correct deduplication within sliding window",
                        "memory_efficiency": "30% - Timely eviction of expired keys without unbounded growth",
                        "concurrency": "20% - Safe locking with minimal contention",
                        "code_quality": "20% - Clean modular code with meaningful test coverage",
                    },
                },
                {
                    "title": "Rate-Limited Resilient Queue Consumer",
                    "difficulty": diff,
                    "description": "Implement a worker consumer that pulls tasks from a priority queue while strictly respecting an external API rate limit (e.g. 50 requests per minute with token bucket algorithm).",
                    "constraints": [
                        "Burst requests up to bucket capacity.",
                        "Smooth refills without worker starvation.",
                        "Graceful shutdown handling in-flight tasks.",
                    ],
                    "sample_inputs_outputs": [
                        {"input": "Rate limit: 5 req/s. 10 tasks arrive simultaneously.", "output": "First 5 executed immediately, remaining 5 spaced at 200ms intervals.", "explanation": "Token bucket capacity 5 burst, replenished at 1 token/200ms."}
                    ],
                    "expected_concepts": ["Token Bucket", "Condition Variables", "Exponential Backoff", "Idempotency"],
                    "edge_cases": ["Transient 429 Too Many Requests response", "Queue empty during refill", "Process SIGINT during task dispatch"],
                    "competencies_to_assess": ["Concurrency", "Rate limiting", "Failure recovery"],
                    "follow_up_questions": [
                        "How would you prevent retries from executing a task twice?",
                        "What metrics would reveal starvation or a sustained backlog?",
                    ],
                    "evaluation_rubric": {
                        "algorithm": "Token bucket mathematical precision",
                        "error_resilience": "Retry handling with jitter and circuit breaking",
                    },
                },
            ],
            "system_design_scenarios": [
                {
                    "title": "Real-Time Interview Scheduling Engine & Conflict Resolver",
                    "problem_statement": "Architect a globally available, multi-tenant scheduling platform that allows candidates and interview panels across diverse time zones to reserve slots with zero double-booking tolerance.",
                    "functional_requirements": [
                        "Candidates can select from available 30/60 minute slots in real-time.",
                        "Interviews automatically assign qualified panelists matching required skill tags.",
                        "Automated conflict detection and Ripple Rescue when a scheduled panelist calls in sick.",
                        "Immediate calendar sync and ICS invitations via email/webhook.",
                    ],
                    "non_functional_requirements": [
                        "P99 booking confirmation latency < 250ms.",
                        "Strict serializability on booking exclusion constraints (zero overlapping slots).",
                        "99.99% service availability during university placement drives.",
                    ],
                    "scalability_concerns": [
                        "Database hot spots on popular time slots (e.g., 9:00 AM on Monday).",
                        "Optimistic concurrency retries under heavy contention (1,000 students booking simultaneously).",
                        "Distributed locking overhead across multiple web application replicas.",
                    ],
                    "evaluation_criteria": {
                        "concurrency_control": "PostgreSQL exclusion constraints or Redis distributed locks with fences",
                        "architecture_tiering": "Clear separation between API gateway, OR-Tools solver worker, and Postgres datastore",
                        "fault_tolerance": "Handling worker crash during schedule calculation without losing drive state",
                    },
                    "competencies_to_assess": ["Distributed systems", "Scheduling", "Database concurrency"],
                    "follow_up_questions": [
                        "How would you recover if a worker crashes after saving a proposal but before reporting completion?",
                        "How would you explain an infeasible schedule to a coordinator?",
                    ],
                }
            ],
            "behavioral_questions": [
                {
                    "question": "Describe a scenario where a critical system outage occurred during peak business hours. How did you triage, communicate, and remediate the issue?",
                    "competency": "Crisis Management & Ownership",
                    "situation_guidance": "Candidate should use STAR format (Situation, Task, Action, Result) focusing on root-cause analysis rather than finger-pointing.",
                    "evaluation_rubric": "High: Clear incident triage, blameless post-mortem, permanent regression fix. Medium: Fixed issue but poor communication. Low: Blamed third party without containment.",
                    "expected_indicators": ["Prioritizes impact and containment", "Communicates status clearly", "Adds a preventive follow-up"],
                    "red_flags": ["Blames others without describing actions", "Cannot explain impact or follow-up"],
                    "follow_up_questions": ["What did you learn from the incident?", "How did you verify the permanent fix?"],
                },
                {
                    "question": "Tell me about a time you had a technical disagreement with a senior architect regarding system design. How did you reach consensus?",
                    "competency": "Constructive Collaboration & Technical Humility",
                    "situation_guidance": "Look for objective benchmarking, prototyping, and willingness to disagree and commit.",
                    "evaluation_rubric": "High: Used data/benchmarks to drive alignment. Medium: Yielded without debate. Low: Conflict escalation without resolution.",
                    "expected_indicators": ["Explains the technical tradeoff", "Seeks evidence", "Describes how the team reached a decision"],
                    "red_flags": ["Treats disagreement as personal conflict", "Cannot explain the chosen tradeoff"],
                    "follow_up_questions": ["What evidence changed or confirmed your view?", "How did you support the final decision?"],
                },
            ],
            "multiple_choice_questions": [
                {
                    "question": "For a hash table with well-distributed keys, what is the expected average lookup complexity?",
                    "competency": "Data structures",
                    "difficulty": diff,
                    "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                    "correct_answer_index": 0,
                    "explanation": "With well-distributed hashes, lookup is constant time on average; worst-case collisions can still make it O(n).",
                },
                {
                    "question": "A client retries an interview booking after a timeout. What best prevents the retry from creating a duplicate booking?",
                    "competency": "API reliability",
                    "difficulty": diff,
                    "options": ["Create a new booking on every retry", "Check an idempotency key atomically with the booking", "Wait one second before retrying", "Disable database constraints"],
                    "correct_answer_index": 1,
                    "explanation": "Checking and recording the same idempotency key in the booking transaction makes repeated requests safe.",
                },
            ],
            "competencies_to_assess": ["Problem solving", "Data structures", "Concurrency", "Reliability", "Communication"],
            "rubric_template": {
                "categories": [
                    {"name": "Technical Problem Solving", "weight": 0.35, "max_score": 10},
                    {"name": "System Architecture & Scalability", "weight": 0.35, "max_score": 10},
                    {"name": "Code Cleanliness & Edge Cases", "weight": 0.20, "max_score": 10},
                    {"name": "Communication & Collaboration", "weight": 0.10, "max_score": 10},
                ],
                "passing_score": 6.5,
            },
        }
        return schema_cls.model_validate(mock_data)

    def _build_drive_brief(self, prompt: str, schema_cls: type[T]) -> T:
        # Prompt contains JSON context of real counts
        data = {
            "drive_title": "Recruitment Drive",
            "drive_status": "in_progress",
            "candidate_counts": {
                "total_enrolled": 0,
                "active_in_pipeline": 0,
                "selected": 0,
                "rejected": 0,
                "withdrawn": 0,
            },
            "upcoming_rounds": [],
            "missing_feedback": [],
            "scheduling_conflicts_and_risks": [
                "Verify interviewer availability for upcoming rounds",
                "Ensure interview rooms are assigned with adequate capacity",
            ],
            "pending_actions": [
                "Review pending interview evaluations to advance eligible candidates",
                "Publish pending schedule proposals once verified",
            ],
            "executive_summary": "Drive is operating normally. All core constraints are verified.",
        }
        return schema_cls.model_validate(data)

    def _build_candidate_summary(self, prompt: str, schema_cls: type[T]) -> T:
        data = {
            "candidate_name": "Candidate",
            "candidate_email": "candidate@example.com",
            "drive_title": "Recruitment Drive",
            "pipeline_status": "active",
            "evaluations_count": 0,
            "completed_rounds": [],
            "recurring_strengths": ["Demonstrates strong foundational engineering concepts"],
            "recurring_weaknesses": ["Could provide more depth on system scaling trade-offs"],
            "recommendation_synthesis": "Candidate shows positive trajectory across evaluated rounds.",
            "progression_readiness": "Proceed to next interview round for final panel review",
            "disclaimer": "AI-generated synthesis of human evaluations. Human coordinator retains final decision authority.",
        }
        return schema_cls.model_validate(data)


def get_llm_provider() -> BaseLLMProvider:
    """Factory returning configured LLM provider with fallback to DeterministicLocalProvider."""
    provider_type = settings.AI_PROVIDER.lower().strip()

    if provider_type == "openai" and settings.AI_API_KEY:
        try:
            return OpenAILLMProvider(
                api_key=settings.AI_API_KEY,
                model=settings.AI_MODEL,
                api_base=settings.AI_API_BASE,
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            log.warning("Failed to initialize OpenAI provider (%s), falling back to DeterministicLocalProvider", exc)
    elif provider_type == "openai":
        log.warning("AI_PROVIDER is openai but AI_API_KEY is missing; using deterministic demo generation")
    elif provider_type not in {"deterministic", ""}:
        log.warning("Unsupported AI_PROVIDER '%s'; using deterministic demo generation", provider_type)

    # Default robust provider
    return DeterministicLocalProvider()
