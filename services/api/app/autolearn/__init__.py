"""AutoLearn — experimental Teacher->human-reviewed->Student vertical slice (M3).

This package is an explicitly UNVERIFIED experiment isolated from the accepted
M1/M2 pipeline. It never authorizes a Teacher-backed workflow action. The
offline labeling client proposes dataset labels for human review only; the
fitted Student is used solely for offline classification once a human approves
it and its held-out metrics clear a predefined gate.
"""
