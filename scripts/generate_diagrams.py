"""Generate all paperbanana diagrams for the agent-engine-eval-demo project."""

import asyncio
import shutil
from pathlib import Path

from dotenv import load_dotenv

from paperbanana import DiagramType, GenerationInput, PaperBananaPipeline
from paperbanana.core.config import Settings

PAPERBANANA_ROOT = Path.home() / "paperbanana"
load_dotenv(PAPERBANANA_ROOT / ".env")
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "paperbanana_inputs"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets" / "generated"

DIAGRAMS = [
    (
        "end_to_end_architecture.txt",
        "End-to-end architecture of the Agent Engine evaluation and reporting pipeline, "
        "from agent deployment through traffic generation, evaluation, and BigQuery export.",
        "end_to_end_architecture.png",
    ),
    (
        "eval_pipeline.txt",
        "Evaluation pipeline showing custom Model-as-a-Judge rubric scoring (helpfulness "
        "and conciseness, rated 1-5) alongside exact-match baseline evaluation.",
        "eval_pipeline.png",
    ),
    (
        "bigquery_sink.txt",
        "Data flow from agent execution through evaluation to BigQuery sink and Looker "
        "dashboarding, showing the complete observability pipeline.",
        "bigquery_sink.png",
    ),
    (
        "otel_tracing.txt",
        "OpenTelemetry span hierarchy for Agent Engine, showing automatic instrumentation "
        "of reasoning loops, LLM calls, and tool execution.",
        "otel_tracing.png",
    ),
]


async def generate_one(
    settings: Settings,
    input_path: Path,
    caption: str,
    output_filename: str,
) -> str:
    source_context = input_path.read_text(encoding="utf-8")

    pipeline = PaperBananaPipeline(settings=settings)
    result = await pipeline.generate(
        GenerationInput(
            source_context=source_context,
            communicative_intent=caption,
            diagram_type=DiagramType.METHODOLOGY,
        )
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUTPUT_DIR / output_filename
    shutil.copy2(result.image_path, dest)
    print(f"  -> {dest}")
    return str(dest)


async def main():
    settings = Settings(
        vlm_provider="gemini",
        vlm_model="gemini-2.5-flash",
        image_provider="google_imagen",
        image_model="gemini-3-pro-image-preview",
        refinement_iterations=2,
        output_dir=str(PROJECT_ROOT / "paperbanana_outputs"),
    )

    print(f"Generating {len(DIAGRAMS)} diagrams...")
    for input_file, caption, output_file in DIAGRAMS:
        input_path = INPUTS_DIR / input_file
        if not input_path.exists():
            print(f"SKIP: {input_path} not found")
            continue
        print(f"\nGenerating: {output_file}")
        try:
            await generate_one(settings, input_path, caption, output_file)
        except Exception as e:
            print(f"FAILED: {output_file}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
