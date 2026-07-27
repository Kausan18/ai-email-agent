# PRODUCT REQUIREMENTS DOCUMENT (PRD)

# AI Context-Aware Email Assistant

## LLM / AI Agent Handoff Document

**Purpose of this document**

This document is intended as a complete handoff specification for
another LLM, AI coding agent, or engineer. It explains the vision,
goals, architecture, implementation strategy, constraints, and roadmap
of the project so development can continue with minimal additional
context.

------------------------------------------------------------------------

# Executive Summary

This project is **not** a traditional email reply generator.

The goal is to build an AI email assistant that behaves like an
intelligent colleague.

Instead of directly generating replies, the system should:

1.  Understand incoming emails.
2.  Decide whether a reply is required.
3.  Decide whether information should be remembered.
4.  Extract structured knowledge.
5.  Retrieve relevant context.
6.  Estimate confidence in available information.
7.  Decide which reply generation strategy is most appropriate.
8.  Produce a grounded draft.
9.  Allow human review before sending.
10. Learn from user feedback over time.

The intelligence of the system lies primarily in its **decision-making
pipeline**, not the text generation itself.

------------------------------------------------------------------------

# Product Vision

Create an explainable, modular AI email agent that reasons before
writing.

The system should be capable of:

-   understanding context
-   remembering important information
-   ignoring irrelevant information
-   retrieving only relevant memories
-   avoiding hallucinations
-   exposing planner decisions
-   improving continuously

This should resemble an AI assistant rather than a chatbot.

------------------------------------------------------------------------

# Core Principles

-   Modular architecture.
-   Human-in-the-loop before sending emails.
-   Explainable planner decisions.
-   Local-first inference.
-   Retrieval before generation when needed.
-   Confidence-aware reasoning.
-   Continuous improvement through feedback.
-   Easy experimentation.

------------------------------------------------------------------------

# Development Philosophy

Development is incremental.

Version 0: Baseline email reply system.

Later versions gradually introduce:

-   memory
-   retrieval
-   planner
-   confidence
-   routing
-   evaluation
-   continual learning

Avoid implementing everything simultaneously.

------------------------------------------------------------------------

# System Overview

Pipeline:

Incoming Email → Gmail API → Parsing → Classification → Entity
Extraction → Memory Decision → Structured Memory → Semantic Memory →
Planner → Context Retrieval → Confidence Assessment → Model Router →
Reply Generation → Verification → User Review → Send → Feedback →
Continual Improvement

------------------------------------------------------------------------

# Functional Modules

## 1. Email Ingestion

Responsibilities

-   Gmail API
-   MIME parsing
-   Thread reconstruction
-   Attachment metadata
-   Sender extraction

Output

Canonical email object.

------------------------------------------------------------------------

## 2. Email Classification

Determine:

-   category
-   reply required
-   memory required
-   priority
-   importance

Example categories

-   Recruiter
-   Internship
-   Meeting
-   Professor
-   Conference
-   Reminder
-   Newsletter
-   Promotion
-   Personal

------------------------------------------------------------------------

## 3. Entity Extraction

Extract structured entities:

-   company
-   recruiter
-   role
-   meeting
-   project
-   deadline
-   organization
-   application status
-   action items

------------------------------------------------------------------------

## 4. Memory System

### Structured Memory

Technology

Supabase PostgreSQL

Stores factual information.

Examples

Applications

Recruiters

Contacts

Meetings

Deadlines

Planner logs

Evaluation logs

------------------------------------------------------------------------

### Semantic Memory

Technology

pgvector

Stores embeddings for

-   thread summaries
-   conversation summaries
-   previous replies
-   meeting summaries
-   project discussions

------------------------------------------------------------------------

### Working Memory

Technology

Redis

Stores

-   current email
-   planner state
-   retrieved memories
-   temporary constraints
-   cache

------------------------------------------------------------------------

## 5. Planner

The planner is the brain.

Responsibilities

-   reply?
-   store?
-   retrieve?
-   calendar?
-   confidence?
-   constraints?
-   routing?

Planner outputs structured decisions rather than natural language.

------------------------------------------------------------------------

## 6. Confidence Engine

Never blindly trust external data.

Every source has:

Status

Confidence

Reliability

Examples

Calendar says FREE.

Reliability LOW.

Planner should avoid committing.

------------------------------------------------------------------------

## 7. Context Retrieval

Retrieve only relevant context.

Possible sources

-   previous emails
-   internship applications
-   meetings
-   recruiter history
-   semantic memories

------------------------------------------------------------------------

## 8. Router

Three generation strategies exist.

Fine-Tuned

RAG

Hybrid

Router selects the most suitable strategy.

Future versions may replace rule-based routing with a learned router.

------------------------------------------------------------------------

## 9. Reply Generation

Generation is the final stage.

Inputs

Email

Planner output

Retrieved context

Constraints

Confidence

The generator should never infer missing facts when confidence is low.

------------------------------------------------------------------------

## 10. Reply Verification

Validate

-   hallucinations
-   unsupported claims
-   wrong company
-   wrong person
-   unsafe commitments
-   tone

------------------------------------------------------------------------

## 11. Human Review

The system never automatically sends emails in Version 1.

User can

Review

Edit

Approve

Send

------------------------------------------------------------------------

## 12. Feedback Pipeline

Store

Original email

Planner decisions

Generator used

Three generated replies (research mode)

Winner

User edits

Final reply

These records become training data.

------------------------------------------------------------------------

# Generation Strategies

## Fine-Tuned

Strength

Style

Weakness

No retrieval.

------------------------------------------------------------------------

## RAG

Strength

Grounded.

Weakness

Prompt dependent.

------------------------------------------------------------------------

## Hybrid

Fine-tuned model plus retrieved context.

Expected to perform best for complex professional emails.

------------------------------------------------------------------------

# Research Mode vs Production Mode

Research Mode

Generate

Fine-Tuned

RAG

Hybrid

Evaluate all three.

Choose best.

Store all outputs.

Production Mode

Planner chooses one strategy.

Only one reply is generated.

------------------------------------------------------------------------

# Evaluation

Compare

Grammar

Professional tone

Grounding

Hallucination

Completeness

Latency

User edits

Acceptance rate

Router accuracy

------------------------------------------------------------------------

# Continual Improvement

Feedback should improve:

Planner

Router

Prompts

Retriever

Fine-tuned model

Retraining should occur periodically, not after every email.

------------------------------------------------------------------------

# Technology Stack

Frontend

Next.js

React

Tailwind

shadcn/ui

Backend

FastAPI

Inference

Ollama

Training

Hugging Face Transformers

PEFT

QLoRA

TRL

Google Colab

Databases

Supabase PostgreSQL

pgvector

Redis

Embeddings

Sentence Transformers or BAAI embedding model.

External APIs

Gmail API

Google Calendar API

Version Control

Git/GitHub

------------------------------------------------------------------------

# Edge Cases

Examples

-   newsletters
-   promotions
-   acknowledgements
-   duplicate memories
-   missing retrieval
-   unknown contacts
-   incomplete calendar
-   low-confidence external context
-   hallucinated commitments
-   missing attachments
-   conflicting memories

Every new edge case should be documented and added to the planner tests.

------------------------------------------------------------------------

# Development Roadmap

Phase 0

Baseline

Phase 1

Email ingestion

Phase 2

Classification

Phase 3

Memory

Phase 4

Retrieval

Phase 5

Planner

Phase 6

Confidence

Phase 7

Router

Phase 8

Reply generation

Phase 9

Evaluation

Phase 10

Continual learning

------------------------------------------------------------------------

# Success Criteria

The project is successful if:

-   replies are context-aware
-   hallucinations are reduced
-   planner decisions are explainable
-   memories are relevant
-   retrieval is grounded
-   routing selects appropriate generation strategies
-   user editing effort decreases over time
-   modular architecture allows future expansion

------------------------------------------------------------------------

# Instructions for Future AI Agents

When extending this project:

1.  Preserve modularity.
2.  Do not bypass the planner.
3.  Do not tightly couple modules.
4.  Prefer structured outputs over free-form text.
5.  Keep generation separate from reasoning.
6.  Maintain human review before sending.
7.  Optimize for correctness before fluency.
8.  Document architectural decisions.
9.  Build incrementally.
10. Treat this project as an AI agent, not a chatbot.

End Goal:

Deliver a production-quality, explainable, context-aware AI email
assistant capable of reasoning, retrieving knowledge, selecting the best
generation strategy, and continuously improving from user feedback while
remaining modular and research-friendly.
