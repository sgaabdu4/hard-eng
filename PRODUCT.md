# Hard Eng

Hard Eng is a repository-local scaffold for developers and coding agents working in existing projects. It supplies shared instructions, native tool configuration and gates selected from the project's tech stack.

The required behavior and implementation status are recorded in [DECISION.md](DECISION.md). Installation preserves project-owned content. Updates affect the installed scaffold; checks must report real failures rather than claim unverified work is complete.

The source repository is not a global agent directory. Installation, hook configuration and generated files belong to the target repository. Remote branch protection requires separate approval.
