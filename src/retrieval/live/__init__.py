"""Live evidence for free-text forwards: Wikipedia and Google Fact Check (post-test Phase 7).

Opt-in and per claim: nothing here runs unless the user clicks "search live" on
a card, and only that claim's text leaves the machine (SRS C-5, NFR-8). No
evaluation config reaches this package, so no reported number depends on it.

Standard library only (urllib): CI installs the core lock, and a network client
must not drag in a dependency or a model library.
"""
