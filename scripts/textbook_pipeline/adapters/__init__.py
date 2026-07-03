"""Parser adapters that output pre-classification RawSpan + page identity.

Adapters are pure parsers. They do NOT classify, summarize, or write
generated/ data. Downstream IR construction (DocumentNode, DocumentBlock)
is the responsibility of the pipeline, not the adapter.
"""
