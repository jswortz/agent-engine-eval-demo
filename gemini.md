# Gemini Model Configuration

This document tracks the model selection and configuration for the Agent Engine demo.

## Working Configuration

After testing multiple variations, the following configuration was verified to work locally and is used for deployment:

*   **Model**: `gemini-2.5-flash`
*   **Region**: `us-central1`

## Attempted Models (Failed with 404 or Access Denied)

The following models were attempted in `us-central1` and `us-east1` but were not found or accessible:

*   `gemini-1.5-pro-preview-0409`
*   `gemini-1.5-pro-001`
*   `gemini-1.5-flash-001`
*   `gemini-1.5-flash` (in `us-east1`)
*   `gemini-3-flash-preview` (Preferred by system rules but failed in both regions)
*   `gemini-3`
*   `gemini-1.0-pro`

## Important Notes

*   **Regional Restrictions**: If you encounter 404 errors for models, consider targeting `us-east1` or `us-central1` specifically, as access varies by project.
*   **Global Endpoint**: The user suggested using "gemini 3 - global", but `gemini-3` was not found in `us-east1` or `global` location.
