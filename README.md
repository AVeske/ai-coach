AI Coach — Gym Exercise Analysis from Video
1. Problem the Project Solves

This project focuses on analyzing human movement from video and providing feedback on exercise performance.

In real-world training scenarios:

users often lack immediate feedback
incorrect movement patterns go unnoticed
poor technique can reduce effectiveness or cause injury

The goal of this project is to:

detect repetitions from video
evaluate movement quality
provide structured feedback based on measurable criteria
2. System Overview

The system is built as a modular data processing pipeline, transforming raw video into structured feedback.

Input
Short video clip (recorded or uploaded)
Controlled constraints (duration, camera angle)
Pose Estimation
Uses a pre-trained model (MoveNet)
Extracts human body keypoints per frame
Feature Extraction
Keypoints are converted into:
joint angles (e.g., elbow, knee)
positional signals (e.g., vertical movement of joints)
Signals are smoothed and normalized to reduce noise
Temporal Analysis
Time-series signals are analyzed to detect:
movement cycles (repetitions)
key phases (top, bottom positions)
Rep Detection
Generic top–bottom–top pattern detection
Uses peak detection and temporal constraints
Designed to generalize across different exercises
Evaluation Logic

Each repetition is evaluated using rule-based metrics:

Range of Motion (ROM)
Movement tempo (total, eccentric, concentric phases)
Joint constraints (e.g., lockout, depth)

Configuration is defined via structured YAML files, enabling:

consistent evaluation logic
easy extension to new exercises
Feedback Layer
Per-rep metrics are aggregated
Flags (e.g., low ROM, too fast) are generated
AI component converts structured data into human-readable feedback
3. Technical Implementation

This project demonstrates the design and implementation of an end-to-end intelligent system, combining computer vision, signal processing, and rule-based evaluation.

Key components:

Backend System
Python + FastAPI service for handling video processing
Modular architecture separating extraction, analysis, and scoring
Time-Series Processing
Conversion of pose data into continuous signals
Smoothing and normalization techniques
Event detection (peaks, transitions) in noisy data
Rep Detection Algorithm
Generic pattern detection for cyclic motion
Robust to noise and partial repetitions
Configurable via parameters (distance, prominence, duration)
Rule-Based Scoring System
YAML-driven configuration per exercise
Standardized evaluation metrics across movements
Extensible design for adding new exercises
Data Structuring
Each repetition represented as structured data:
timestamps
range of motion
tempo phases
detected issues
System Design Principles
Modularity (separate pipeline stages)
Reusability (shared detection logic across exercises)
Interpretability (rule-based metrics instead of black-box scoring)
4. Project Status
Functional prototype
Rep detection works reliably across multiple exercises
Per-repetition analysis implemented
Feedback generation integrated
UI and evaluation still being refined

This project is not production-ready, but demonstrates core system functionality and design.

5. Relevance to Robotics and Data Science

This project aligns with key topics in Robotics and Data Science:

Computer Vision — human pose estimation from visual input
Time-Series Analysis — extracting structure from temporal signals
Signal Processing — smoothing and feature extraction from noisy data
Machine Learning Integration — using pre-trained models in a pipeline
Intelligent Systems — combining data-driven and rule-based reasoning
Human Movement Analysis — interpreting physical actions computationally

It demonstrates the ability to:

build data pipelines from raw input to structured output
design interpretable evaluation systems
apply theoretical concepts to a practical, real-world problem
