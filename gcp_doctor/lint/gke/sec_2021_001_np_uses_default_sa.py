# Lint as: python3
"""GKE node pool uses default service account.

The GCE default service account has more permissions than are required to run
your Kubernetes Engine cluster. You should create and use a minimally privileged
service account.

Reference: Hardening your cluster's security
  https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster#use_least_privilege_sa
"""

from gcp_doctor import lint, models
from gcp_doctor.queries import gke

ROLE = 'roles/logging.logWriter'


def run_test(context: models.Context, report: lint.LintReportTestInterface):
  # Find all clusters.
  clusters = gke.get_clusters(context)
  if not clusters:
    report.add_skipped(None, 'no clusters found')
  for _, c in sorted(clusters.items()):
    # Verify service-account for every nodepool.
    for np in c.nodepools:
      if np.has_default_service_account():
        report.add_failed(np, 'node pool uses the default GCE service account')
      else:
        report.add_ok(np)