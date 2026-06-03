"""Retry failed knowledge points from structured.json."""

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

import config
from step4_structurize import get_llm_client, structurize_one
from tqdm.asyncio import tqdm

console = Console()


async def retry_failed():
    """Retry only failed knowledge points."""
    console.rule("[bold blue]Retry Failed Knowledge Points")

    # Load existing structured data
    with open(config.STRUCTURED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])

    # Find failed ones
    failed_kps = [kp for kp in kps if kp.get("structurize_status", "").startswith("error")]

    if not failed_kps:
        console.print("[green]✓ No failed knowledge points to retry!")
        return

    console.print(f"📝 Found {len(failed_kps)} failed knowledge points to retry")

    # Show which ones
    for kp in failed_kps:
        console.print(f"   - {kp['name']}: {kp['structurize_status']}")

    # Get LLM client
    client = get_llm_client()
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY)

    # Retry with progress bar
    pbar = tqdm(total=len(failed_kps), desc="Retrying")

    tasks = [structurize_one(client, semaphore, kp, pbar) for kp in failed_kps]
    retried_results = await asyncio.gather(*tasks)

    pbar.close()

    # Update results in original data
    retried_map = {kp["name"]: kp for kp in retried_results}

    for i, kp in enumerate(kps):
        if kp["name"] in retried_map:
            kps[i] = retried_map[kp["name"]]

    # Save updated data
    with open(config.STRUCTURED_JSON, "w", encoding="utf-8") as f:
        json.dump({"knowledge_points": kps}, f, ensure_ascii=False, indent=2)

    # Summary
    success = sum(1 for kp in retried_results if kp.get("structurize_status") == "success")
    failed = len(retried_results) - success

    console.print(Panel.fit(
        f"[green]✓[/green] Retried: {len(retried_results)}\n"
        f"[green]✓[/green] Now success: {success}\n"
        f"[red]✗[/red] Still failed: {failed}",
        title="Retry Complete",
        border_style="green" if failed == 0 else "yellow",
    ))


if __name__ == "__main__":
    asyncio.run(retry_failed())
