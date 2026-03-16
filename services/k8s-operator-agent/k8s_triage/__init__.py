"""K8s Triage — detect and diagnose failing pods in a Kubernetes namespace."""

from k8s_triage.models import PodDiagnostic, TriageReport
from k8s_triage.watcher import K8sWatcher

__all__ = ["PodDiagnostic", "TriageReport", "K8sWatcher"]
