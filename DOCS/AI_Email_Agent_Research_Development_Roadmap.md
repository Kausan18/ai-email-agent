# AI Context-Aware Email Assistant

# Research & Development Roadmap (Master)

> This document is the canonical roadmap describing the evolution of the
> project from a baseline email assistant into an adaptive AI email
> agent.

------------------------------------------------------------------------

# Project Philosophy

The project will **not** be built all at once.

Each version is a stable milestone with its own: - Engineering
objective - Research objective - AI capabilities - Technology stack -
Evaluation metrics

Every version extends the previous one.

------------------------------------------------------------------------

# Overall Evolution

  -----------------------------------------------------------------------
  Version                 Theme                   Research Question
  ----------------------- ----------------------- -----------------------
  V1                      Foundation              Can a base LLM generate
                                                  useful professional
                                                  email replies?

  V2                      Personalization         Does fine-tuning +
                                                  planning improve
                                                  quality over a generic
                                                  model?

  V3                      Intelligence            Can retrieval, routing
                                                  and continual learning
                                                  create an adaptive
                                                  email agent?
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# VERSION 1 --- FOUNDATION

## Goal

Build a reliable baseline using a local LLM.

## Pipeline

Gmail → Parser → Classifier → Prompt Builder → Base Model (Ollama) →
Human Review

## Engineering Scope

-   Gmail API integration
-   MIME parsing
-   Thread reconstruction
-   Basic classifier
-   Prompt templates
-   Logging
-   Human approval

## AI Concepts

-   Prompt Engineering
-   Zero-shot / few-shot prompting
-   Local inference
-   Basic intent classification

## Models

-   Base instruct model served with Ollama (model selected during
    implementation)

## Not Included

-   Fine-tuning
-   Memory
-   RAG
-   Planner
-   Router
-   Evaluation
-   Continual learning

## Research

Compare prompt strategies and establish baseline metrics.

------------------------------------------------------------------------

# VERSION 2 --- PERSONALIZED ASSISTANT

## Goal

Personalize responses using fine-tuning while introducing structured
reasoning.

## Pipeline

Gmail → Parser → Classifier → Entity Extraction → Structured Memory →
Planner → Prompt Builder → Fine-Tuned Model → Verification → Human
Review

## Engineering Scope

-   Structured memory (Supabase PostgreSQL)
-   Entity extraction
-   Planner
-   Reply verification
-   Preference storage

## AI Concepts

-   Supervised Fine-Tuning (SFT)
-   Instruction tuning
-   QLoRA
-   LoRA adapters
-   Prompt engineering
-   Structured reasoning

## Training Stack

-   Hugging Face Transformers
-   PEFT
-   TRL (SFTTrainer)
-   QLoRA
-   BitsAndBytes (4-bit quantization)
-   Google Colab GPU

## Initial Training Hyperparameters (starting point)

-   Quantization: 4-bit NF4
-   LoRA Rank (r): 16
-   LoRA Alpha: 32
-   LoRA Dropout: 0.05
-   Optimizer: AdamW
-   Learning Rate: 2e-4
-   Scheduler: Cosine
-   Batch Size: 4 (effective via gradient accumulation)
-   Gradient Accumulation: 4
-   Epochs: 3-5
-   Max Sequence Length: 2048
-   Mixed Precision: BF16 if available, otherwise FP16
-   Save Best Checkpoint
-   Early Stopping enabled

> These values are starting points and may be tuned experimentally.

## Research

Base Model vs Fine-Tuned Model Measure: - Tone - Professionalism - Edit
distance - User acceptance - Hallucination rate

------------------------------------------------------------------------

# VERSION 3 --- INTELLIGENT CONTEXT-AWARE AGENT

## Goal

Create an adaptive agent capable of selecting the best generation
strategy and learning from feedback.

## Pipeline

Gmail → Parser → Classifier → Structured Memory → Semantic Memory
(pgvector) → Retriever → Planner → Confidence Engine → Router →
Generate: - Fine-Tuned - RAG - Hybrid → Evaluation → Best Draft → Human
Review → Feedback → Dataset → Periodic Retraining

## Engineering Scope

-   Semantic retrieval
-   pgvector
-   Embeddings
-   Confidence engine
-   Intelligent router
-   Evaluation framework
-   Continual learning

## AI Concepts

-   Retrieval-Augmented Generation (RAG)
-   Dense embeddings
-   Vector similarity search
-   Hybrid generation
-   LLM-as-a-Judge
-   Rule-based verification
-   Continual learning
-   Model routing
-   Confidence estimation

## Retrieval Stack

-   pgvector
-   Sentence Transformers / BAAI embedding model
-   Metadata filtering
-   Similarity ranking

## Router

Inputs: - Planner outputs - Retrieval confidence - Memory confidence -
Email category - Complexity - Risk

Outputs: - Fine-Tuned - RAG - Hybrid

## Evaluation

Compare: - Fine-Tuned - RAG - Hybrid

Metrics: - Grounding - Hallucination - Tone - Grammar - Completeness -
Latency - User edits - Acceptance rate - Router accuracy

## Continual Learning

Dataset stores: - Original email - Planner decisions - FT reply - RAG
reply - Hybrid reply - Winning reply - User edits - Final sent email

Retraining targets: - Fine-tuned model - Router - Prompt templates -
Retrieval quality

------------------------------------------------------------------------

# Technology Evolution

  Component             V1    V2     V3
  -------------------- ---- ------- ----
  Gmail API             ✓      ✓     ✓
  Parser                ✓      ✓     ✓
  Classification        ✓      ✓     ✓
  Entity Extraction            ✓     ✓
  Structured Memory            ✓     ✓
  Semantic Memory                    ✓
  Planner                      ✓     ✓
  Confidence Engine                  ✓
  Router                             ✓
  Fine-Tuning                  ✓     ✓
  RAG                                ✓
  Hybrid                             ✓
  Evaluation                 Basic   ✓
  Continual Learning                 ✓

------------------------------------------------------------------------

# Core Technology Decisions

Frontend: - Next.js - React - Tailwind CSS - shadcn/ui

Backend: - FastAPI

Inference: - Ollama

Training: - Hugging Face Transformers - PEFT - TRL - QLoRA - Google
Colab

Storage: - Supabase PostgreSQL - pgvector - Redis

Embeddings: - Sentence Transformers (or BAAI equivalent)

APIs: - Gmail API - Google Calendar API

------------------------------------------------------------------------

# Research Roadmap

1.  Establish Base LLM benchmark.
2.  Measure gains from fine-tuning.
3.  Measure gains from planner + memory.
4.  Compare FT vs RAG vs Hybrid.
5.  Build intelligent router.
6.  Measure continual learning improvements.

------------------------------------------------------------------------

# Definition of Success

Engineering: - Modular architecture - Explainable planner - Human
approval workflow - Stable APIs

Research: - Lower hallucination rate - Reduced user edits - Higher
acceptance rate - Better factual grounding - Accurate routing
decisions - Demonstrable improvement across versions

------------------------------------------------------------------------

# Long-Term Vision

The finished system should behave as a trustworthy digital colleague
that reasons before writing, uses memory responsibly, retrieves only
relevant context, selects the most appropriate generation strategy, and
improves continuously from user feedback.
