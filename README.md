# Software Factory

An autonomous, multi-agent software development pipeline built with the [Google Agent Development Kit (ADK)](https://github.com/google/adk). Inspired by the Google Codelab [Architecting an Autonomous Software Factory: End-to-End Agentic Delivery](https://codelabs.developers.google.com/codelabs/software-factory-end-to-end).

## Overview

The Software Factory coordinates specialized AI agents across a shared remote execution sandbox to take natural language requirements to fully tested, deliverable software:

1. **Tech Lead (`tech_lead_agent`)**: Converts user requirements into formal technical specifications, interfaces, and test criteria.
2. **Developer (`developer_agent`)**: Provisions a shared remote sandbox environment and implements the initial codebase.
3. **Refinement Loop (`refinement_agent`)**:
   - **QA Engineer (`qa_agent`)**: Authors and executes an objective `pytest` suite in the shared sandbox.
   - **Remediation Engineer (`remediation_agent`)**: Automatically diagnoses failures and repairs implementation code until tests pass.
4. **Delivery (`delivery_agent`)**: Packages and outputs the finalized code, test suites, and verification verdict.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Google Cloud Platform credentials with Vertex AI / Gemini API access

### 2. Configuration

Create `factory/.env` based on `factory/.env.example`:

```bash
cp factory/.env.example factory/.env
```

Ensure your GCP project ID and credentials are configured:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
```

### 3. Run

Execute the factory against any feature request:

```bash
uv run adk run factory "Build an in-memory rate limiter supporting Token Bucket and Leaky Bucket algorithms."
```

Follow execution logs in real time:

```bash
tail -F /tmp/agents_log/agent.latest.log
```