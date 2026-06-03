"""Step 4: Structurize knowledge points using LLM (async).

This version includes token usage tracking, cost estimation, and balance monitoring.
Uses DeepSeek-V4-Pro pricing:
- Input (cache hit): ¥0.025/百万 tokens
- Input (cache miss): ¥3/百万 tokens
- Output: ¥6/百万 tokens
"""

import asyncio
import json
import re
import sys
import time

from rich.console import Console
from rich.panel import Panel
from tqdm.asyncio import tqdm

import config
from prompts import STRUCTURIZE_PROMPT

console = Console()

# Token cost tracking
total_input_tokens = 0
total_output_tokens = 0


def get_llm_client():
    """Return an LLM client based on config."""
    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        if not config.ANTHROPIC_API_KEY:
            console.print("[bold red]❌ ANTHROPIC_API_KEY not set")
            sys.exit(1)
        return anthropic.AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            base_url=config.ANTHROPIC_BASE_URL,
        )
    else:
        import openai
        if not config.OPENAI_API_KEY:
            console.print("[bold red]❌ OPENAI_API_KEY not set")
            sys.exit(1)
        return openai.AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response that may be wrapped in markdown or mixed with text."""
    if not text or not text.strip():
        raise ValueError("Empty response from LLM")
    
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)
    else:
        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            text = match.group(1)
    
    # Remove control characters that break JSON parsing
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
    
    return json.loads(text)


def estimate_tokens(text: str) -> int:
    """Estimate token count based on DeepSeek's official guidelines.
    
    DeepSeek token estimation:
    - 1 Chinese character ≈ 0.6 token
    - 1 English character ≈ 0.3 token
    """
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 0.6 + other_chars * 0.3)


def print_cost_estimate(cache_hit_rate: float = 0.0):
    """Print current cost estimate.
    
    Args:
        cache_hit_rate: Estimated cache hit rate (0.0-1.0)
    """
    global total_input_tokens, total_output_tokens

    # DeepSeek-V4-Pro pricing (per million tokens)
    # Input: ¥0.025 (cache hit), ¥3 (cache miss)
    # Output: ¥6
    cache_hit_tokens = int(total_input_tokens * cache_hit_rate)
    cache_miss_tokens = total_input_tokens - cache_hit_tokens
    
    input_cost_hit = (cache_hit_tokens / 1_000_000) * 0.025
    input_cost_miss = (cache_miss_tokens / 1_000_000) * 3
    output_cost = (total_output_tokens / 1_000_000) * 6
    total_cost = input_cost_hit + input_cost_miss + output_cost

    console.print(f"\n[yellow]💰 Current cost estimate:[/yellow]")
    if cache_hit_rate > 0:
        console.print(f"   Input tokens: {total_input_tokens:,} (hit: {cache_hit_tokens:,}, miss: {cache_miss_tokens:,})")
        console.print(f"   Input cost: ~¥{input_cost_hit + input_cost_miss:.2f} (hit: ¥{input_cost_hit:.2f}, miss: ¥{input_cost_miss:.2f})")
    else:
        console.print(f"   Input tokens: {total_input_tokens:,} (~¥{input_cost_miss:.2f})")
    console.print(f"   Output tokens: {total_output_tokens:,} (~¥{output_cost:.2f})")
    console.print(f"   [bold]Total: ~¥{total_cost:.2f}[/bold]")

    return total_cost


async def call_llm_async(client, prompt: str) -> tuple[str, dict]:
    """Async LLM call with token usage tracking."""
    global total_input_tokens, total_output_tokens

    if config.LLM_PROVIDER == "anthropic":
        resp = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text, {}
    else:
        resp = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        usage = getattr(resp, 'usage', None)
        if usage:
            total_input_tokens += usage.prompt_tokens
            total_output_tokens += usage.completion_tokens
        return resp.choices[0].message.content, usage


async def structurize_one(
    client,
    semaphore: asyncio.Semaphore,
    kp: dict,
    pbar: tqdm,
    max_retries: int = 3,
) -> dict:
    """Structurize a single knowledge point with retry mechanism."""
    async with semaphore:
        name = kp["name"]
        kp_type = kp.get("type", "disease")
        text = kp.get("extracted_text", "")

        if not text or kp.get("status") != "success":
            kp["structured"] = None
            kp["structurize_status"] = "skipped: no text"
            pbar.update(1)
            return kp

        # Limit text length to control cost
        text_limited = text[:6000]

        prompt = STRUCTURIZE_PROMPT.format(
            knowledge_name=name,
            knowledge_type=kp_type,
            text=text_limited,
        )

        for attempt in range(max_retries):
            try:
                raw, usage = await asyncio.wait_for(
                    call_llm_async(client, prompt),
                    timeout=config.REQUEST_TIMEOUT,
                )

                # If usage not provided by API, estimate from response
                if not usage:
                    output_tokens = estimate_tokens(raw)
                    global total_output_tokens
                    total_output_tokens += output_tokens
                    total_input_tokens += estimate_tokens(prompt)

                structured = extract_json(raw)
                kp["structured"] = structured
                kp["structurize_status"] = "success"
                break
            except Exception as exc:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # Wait before retry
                    continue
                else:
                    kp["structured"] = None
                    kp["structurize_status"] = f"error: {exc}"

        pbar.update(1)
        return kp


async def structurize_knowledge(blocks_path: str, output_path: str) -> None:
    """Read blocks and structurize each knowledge point."""
    console.rule("[bold blue]Step 4: Structurize Knowledge")

    with open(blocks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])
    console.print(f"📝 Total knowledge points to structurize: {len(kps)}")

    # Estimate total cost before starting
    sample_text = kps[0].get("extracted_text", "")[:6000] if kps else ""
    sample_prompt = STRUCTURIZE_PROMPT.format(
        knowledge_name="示例",
        knowledge_type="disease",
        text=sample_text,
    )
    sample_input_tokens = estimate_tokens(sample_prompt)
    sample_output_tokens = 2000

    estimated_input = sample_input_tokens * len(kps)
    estimated_output = sample_output_tokens * len(kps)
    
    # Conservative estimate (assume all cache miss)
    estimated_cost_worst = (estimated_input / 1_000_000) * 3 + (estimated_output / 1_000_000) * 6
    # Optimistic estimate (assume 50% cache hit)
    estimated_cost_best = (estimated_input / 1_000_000) * 1.5 + (estimated_output / 1_000_000) * 6

    console.print(f"\n[yellow]📊 Pre-run cost estimate (DeepSeek-V4-Pro):[/yellow]")
    console.print(f"   Estimated input tokens: {estimated_input:,}")
    console.print(f"   Estimated output tokens: {estimated_output:,}")
    console.print(f"   [green]Best case (50% cache hit): ~¥{estimated_cost_best:.2f}[/green]")
    console.print(f"   [red]Worst case (0% cache hit): ~¥{estimated_cost_worst:.2f}[/red]")
    console.print(f"   [dim]Pricing: Input ¥0.025(hit)/¥3(miss), Output ¥6 per million tokens[/dim]\n")

    client = get_llm_client()
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY)

    pbar = tqdm(total=len(kps), desc="Structurizing")

    # Process in smaller batches to allow for periodic cost checks
    batch_size = 10
    results = []

    for i in range(0, len(kps), batch_size):
        batch = kps[i:i + batch_size]
        tasks = [
            structurize_one(client, semaphore, kp, pbar)
            for kp in batch
        ]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        # Print cost after each batch (assume 0% cache hit for safety)
        current_cost = print_cost_estimate(cache_hit_rate=0.0)
        console.print(f"   Progress: {len(results)}/{len(kps)} completed\n")

    pbar.close()

    success = sum(1 for r in results if r.get("structurize_status") == "success")
    skipped = sum(1 for r in results if "skipped" in r.get("structurize_status", ""))
    failed = len(results) - success - skipped

    # Print final cost
    print_cost_estimate(cache_hit_rate=0.0)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"knowledge_points": results}, f, ensure_ascii=False, indent=2)

    console.print(Panel.fit(
        f"[green]✓[/green] Structured saved to: {output_path}\n"
        f"[green]✓[/green] Success: {success}\n"
        f"[yellow]⊘[/yellow] Skipped: {skipped}\n"
        f"[red]✗[/red] Failed: {failed}",
        title="Structurize Complete",
        border_style="green" if failed == 0 else "yellow",
    ))


if __name__ == "__main__":
    asyncio.run(structurize_knowledge(str(config.BLOCKS_JSON), str(config.STRUCTURED_JSON)))
