# Interview Q&A preparation

**Why LangGraph?** It represents the investigation as an explicit state graph, supports checkpoints and human interrupts, and makes each investigation step inspectable.

**Why RAG?** This implementation does not use a document RAG index. It retrieves operational evidence from Prometheus, Loki and Jaeger and supplies that evidence to the RCA step. Do not call this a vector-database RAG pipeline.

**How does the project reduce hallucinations?** The agents retrieve telemetry first, preserve evidence provenance, use structured outputs, restrict allowed actions, label fallback mode and return uncertainty when evidence is missing. These controls reduce risk but cannot guarantee zero hallucinations.

**Why separate PostgreSQL databases?** The platform database stores users, incidents and approvals. The demo application's database is disposable and may be stopped during fault injection without taking down DevOpsPilot itself.

**Why human approval?** A diagnosis is not authorization. The plan is shown with target, risk and rationale; a human records the decision before the restricted controller can execute it.

**Why not give the LLM Docker access?** Model output is untrusted. It can only propose a structured action. The controller independently checks the allowlist and target, and does not accept arbitrary commands.

**How is recovery verified?** A post-action health request checks the monitored API and its database dependency. The incident remains open or reopens when verification fails.
