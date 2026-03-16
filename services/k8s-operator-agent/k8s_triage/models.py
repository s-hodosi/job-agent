"""
Pydantic data models for the triage output.

These models define the structured JSON payload produced by the watcher
and consumed downstream by LangGraph nodes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class PodDiagnostic(BaseModel):
    """Diagnostic bundle for a single failing pod."""

    pod_name: str = Field(..., description="Name of the failing pod")
    namespace: str = Field(..., description="Namespace the pod belongs to")
    error_type: str = Field(
        ...,
        description="Detected error reason, e.g. CrashLoopBackOff or Error",
    )
    logs: str = Field(
        default="",
        description="Last N lines of container logs",
    )
    events: str = Field(
        default="",
        description="Kubernetes events associated with the pod",
    )
    status_detail: str = Field(
        default="",
        description="Formatted pod status and conditions (similar to kubectl describe)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of when the diagnostic was captured",
    )

    @property
    def context_data(self) -> str:
        """Combined context string for downstream consumption."""
        sections = []
        if self.logs:
            sections.append(f"=== LOGS ===\n{self.logs}")
        if self.events:
            sections.append(f"=== EVENTS ===\n{self.events}")
        if self.status_detail:
            sections.append(f"=== STATUS ===\n{self.status_detail}")
        return "\n\n".join(sections)

    def to_context_dict(self) -> dict:
        """Return the compact JSON shape requested in the spec."""
        return {
            "pod_name": self.pod_name,
            "error_type": self.error_type,
            "context_data": self.context_data,
        }


class TriageReport(BaseModel):
    """Aggregated triage report for an entire namespace scan."""

    failing_pods: List[PodDiagnostic] = Field(default_factory=list)
    scanned_namespace: str = Field(..., description="The namespace that was scanned")
    scan_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of when the scan completed",
    )

    def to_context_dicts(self) -> list[dict]:
        """Return a list of compact context dicts for every failing pod."""
        return [pod.to_context_dict() for pod in self.failing_pods]
