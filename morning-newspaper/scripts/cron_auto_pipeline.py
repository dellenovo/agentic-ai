#!/usr/bin/env python3
"""
Cron auto pipeline for morning-newspaper.

This script handles all three LLM gate stages by calling the OpenClaw
gateway chat completions API, so the cron can run fully automated in an
isolated session without manual model-result file creation.

Usage: python3 scripts/cron_auto_pipeline.py

Expected env:
  - OPENCLAW_GATEWAY_URL (default http://127.0.0.1:18789)
  - OPENCLAW_GATEWAY_TOKEN

Outputs:
  - runtime/cron_status.json
  - runtime/cron_delivery_message.txt (via cron_prepare_brief.py)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT_ROOT / 'runtime'
STATUS_PATH = RUNTIME / 'cron_status.json'
DELIVERY_PATH = RUNTIME / 'cron_delivery_message.txt'

GATEWAY_URL = os.environ.get('OPENCLAW_GATEWAY_URL', 'http://127.0.0.1:18789')
GATEWAY_TOKEN = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '')

MODEL = 'custom-api-deepseek-com/deepseek-chat'

# ── helpers ──────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_status(payload: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def run_script(name: str) -> tuple[str, str, int]:
    cmd = [sys.executable, f'scripts/{name}']
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True)
    return completed.stdout.strip(), completed.stderr.strip(), completed.returncode


def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 2) -> str | None:
    """Call LLM via openclaw capability CLI (native inference)."""
    full_prompt = f'{system_prompt}\n\n{user_prompt}' if system_prompt else user_prompt

    for attempt in range(1 + max_retries):
        try:
            result = subprocess.run(
                ['openclaw', 'capability', 'model', 'run',
                 '--model', MODEL,
                 '--json',
                 '--prompt', full_prompt],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f'CLI exited {result.returncode}: {result.stderr[:200]}')
            parsed = json.loads(result.stdout)
            if parsed.get('ok') and parsed.get('outputs'):
                return parsed['outputs'][0]['text']
            raise RuntimeError(f'unexpected response: {result.stdout[:200]}')
        except Exception as e:
            if attempt < max_retries:
                time.sleep(3)
            else:
                return None


def extract_json(text: str) -> dict | None:
    """Extract first JSON object from text, stripping markdown fences."""
    text = text.strip()
    # Strip markdown code fences with optional language tag
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def clean_and_write_json(text: str, path: Path) -> dict | None:
    """Extract JSON from LLM output (may include markdown fences), write clean JSON to path."""
    parsed = extract_json(text)
    if parsed is not None:
        path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
    return parsed


# ── stages ──────────────────────────────────────────────────────────


def stage_01_collect() -> bool:
    """Phase 1: collect mailbox + raw + enrich + prepare title shortlist."""
    for script in ['collect_mailbox.py', 'collect_raw.py', 'enrich_content.py', 'prepare_title_shortlist.py']:
        stdout, stderr, rc = run_script(script)
        if rc != 0:
            print(f'[FAIL] {script}: {stderr[:200]}')
            return False
    return True


def stage_02_llm_shortlist() -> bool:
    """LLM gate 1: title shortlist."""
    prompt_file = RUNTIME / 'title_shortlist_prompt.txt'
    result_file = RUNTIME / 'title_shortlist_result.json'
    if not prompt_file.exists():
        print('[FAIL] title_shortlist_prompt.txt not found')
        return False

    prompt_text = prompt_file.read_text(encoding='utf-8')
    result = call_llm('You are an AI news editor.', prompt_text)
    if not result:
        print('[FAIL] LLM call failed for shortlist')
        return False

    parsed = extract_json(result)
    if not parsed or 'ranked_titles' not in parsed:
        print(f'[FAIL] shortlist LLM output invalid: {result[:200]}')
        return False

    clean_and_write_json(result, result_file)

    for script in ['apply_title_shortlist.py', 'prepare_draft_input.py']:
        stdout, stderr, rc = run_script(script)
        if rc != 0:
            print(f'[FAIL] {script}: {stderr[:200]}')
            return False
    return True


def stage_03_llm_draft() -> bool:
    """LLM gate 2: draft."""
    prompt_file = RUNTIME / 'draft_prompt.txt'
    result_file = RUNTIME / 'draft_result.json'
    if not prompt_file.exists():
        print('[FAIL] draft_prompt.txt not found')
        return False

    prompt_text = prompt_file.read_text(encoding='utf-8')
    result = call_llm('You are a Chinese AI news editor.', prompt_text)
    if not result:
        print('[FAIL] LLM call failed for draft')
        return False

    parsed = extract_json(result)
    if not parsed or 'drafts' not in parsed:
        print(f'[FAIL] draft LLM output invalid: {result[:200]}')
        return False

    clean_and_write_json(result, result_file)

    stdout, stderr, rc = run_script('apply_draft_results.py')
    if rc != 0:
        print(f'[FAIL] apply_draft_results.py: {stderr[:200]}')
        return False

    stdout, stderr, rc = run_script('prepare_top10_ranking.py')
    if rc != 0:
        print(f'[FAIL] prepare_top10_ranking.py: {stderr[:200]}')
        return False
    return True


def stage_04_llm_ranking() -> bool:
    """LLM gate 3: top10 ranking."""
    prompt_file = RUNTIME / 'top10_ranking_prompt.txt'
    result_file = RUNTIME / 'top10_ranking_result.json'
    if not prompt_file.exists():
        print('[FAIL] top10_ranking_prompt.txt not found')
        return False

    prompt_text = prompt_file.read_text(encoding='utf-8')
    result = call_llm('You are an AI news ranking editor.', prompt_text)
    if not result:
        print('[FAIL] LLM call failed for ranking')
        return False

    parsed = extract_json(result)
    if not parsed:
        print(f'[FAIL] ranking LLM output invalid: {result[:200]}')
        return False

    clean_and_write_json(result, result_file)

    for script in ['apply_top10_ranking.py', 'build_dashboard.py', 'check_runtime_status.py']:
        stdout, stderr, rc = run_script(script)
        if rc != 0:
            print(f'[FAIL] {script}: {stderr[:200]}')
            return False
    return True


def main() -> int:
    start = time.time()
    ok, step, error_summary = False, 'unknown', ''
    top10_count = 0

    try:
        if not stage_01_collect():
            step, error_summary = 'collect', 'collection phase failed'
        elif not stage_02_llm_shortlist():
            step, error_summary = 'shortlist', 'shortlist LLM gate failed'
        elif not stage_03_llm_draft():
            step, error_summary = 'draft', 'draft LLM gate failed'
        elif not stage_04_llm_ranking():
            step, error_summary = 'ranking', 'ranking LLM gate or dashboard build failed'
        else:
            ok, step = True, 'done'

        publishable = RUNTIME / 'top10_publishable.json'
        if publishable.exists():
            try:
                data = json.loads(publishable.read_text(encoding='utf-8'))
                top10_count = int(data.get('count', 0) or 0)
            except Exception:
                top10_count = 0

        dashboard_exists = (RUNTIME / 'dashboard.html').exists()

    except Exception as e:
        step, error_summary = 'runtime', str(e)[:200]

    elapsed = round(time.time() - start, 1)
    write_status({
        'generated_at': now_iso(),
        'ok': ok,
        'step': step,
        'top10_count': top10_count,
        'dashboard_exists': (RUNTIME / 'dashboard.html').exists(),
        'error_summary': error_summary,
        'elapsed_seconds': elapsed,
    })

    # Also prepare delivery message
    subprocess.run(
        [sys.executable, 'scripts/cron_prepare_brief.py'],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
    )

    print(f'Pipeline complete: ok={ok} step={step} top10={top10_count} elapsed={elapsed}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
