#!/usr/bin/env python3
"""
01_llm_inference_scratch.py

Karpathy-style, zero-dependency illustration of raw LLM interaction.
This script demonstrates how to:
1. Make raw API calls using Python's standard `urllib.request` (no OpenAI/Gemini SDKs).
2. Process SSE (Server-Sent Events) streams token-by-token.
3. Count approximate tokens and calculate cost in real-time.
4. Enforce and parse structured JSON outputs without complex schemas.
"""

import json
import os
import time
import urllib.request
import urllib.error
from typing import Generator, Dict, Any, Optional

# --- MODEL PRICING CONFIGURATION (USD per 1M tokens) ---
# Updated June 2026 - prices from official provider pages
PRICING = {
    # OpenAI (https://openai.com/api/pricing/)
    "gpt-5.5": {"input": 5.00, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-4o-mini": {"input": 0.150, "output": 0.60},
    
    # Anthropic (https://www.anthropic.com/pricing)
    "claude-opus-4.8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4.5": {"input": 1.00, "output": 5.00},
    
    # Google Gemini (https://ai.google.dev/gemini-api/docs/pricing)
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    
    # NVIDIA Nemotron (https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b)
    # Free tier via NVIDIA NIM API, self-hosted for production
    "nemotron-3-ultra": {"input": 0.0, "output": 0.0},
    
    # MiniMax (https://platform.minimaxi.com/docs/guides/pricing-paygo)
    # 50% promotional pricing, CNY converted at ~7.25 CNY/USD
    "minimax-m3": {"input": 0.29, "output": 1.16},
    "minimax-m3-long": {"input": 0.58, "output": 2.32},
    
    # Qwen (https://www.aliyun.com/product/tongyi) - Aliyun Bailian pricing varies
    "qwen-3.7-max": {"input": 0.0, "output": 0.0},  # Check Aliyun console for exact rates
    
    # Mock for offline/testing
    "mock-model": {"input": 0.0, "output": 0.0}
}

class CostTracker:
    """Tracks inputs, outputs, token consumption, and financial costs."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.pricing = PRICING.get(model_name, {"input": 0.0, "output": 0.0})
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0

    def estimate_tokens(self, text: str) -> int:
        # A simple but practical approximation: ~4 characters per token
        return max(1, len(text) // 4)

    def track_request(self, prompt: str):
        tokens = self.estimate_tokens(prompt)
        self.input_tokens += tokens
        self.total_cost += (tokens / 1_000_000.0) * self.pricing["input"]

    def track_response(self, response_text: str):
        tokens = self.estimate_tokens(response_text)
        self.output_tokens += tokens
        self.total_cost += (tokens / 1_000_000.0) * self.pricing["output"]

    def get_report(self) -> str:
        return (f"[{self.model_name}] Tokens: {self.input_tokens} In / {self.output_tokens} Out "
                f"| Cost: ${self.total_cost:.8f}")


def print_pricing_table() -> None:
    """Print a formatted table of all known model pricing."""
    print("\n=== MODEL PRICING REFERENCE (USD per 1M tokens) ===")
    print(f"{'Model':<25} {'Input':>10} {'Output':>10} {'Notes'}")
    print("-" * 75)
    for model, prices in PRICING.items():
        if model == "mock-model":
            continue
        notes = ""
        if "nemotron" in model:
            notes = "Free via NVIDIA NIM API"
        elif "minimax" in model:
            notes = "50% promo pricing (CNY)"
        elif "qwen" in model:
            notes = "Check Aliyun Bailian console"
        elif "gpt-5" in model:
            notes = "OpenAI flagship"
        elif "claude" in model:
            notes = "Anthropic"
        elif "gemini" in model:
            notes = "Google"
        print(f"{model:<25} ${prices['input']:>9.4f} ${prices['output']:>9.4f}  {notes}")
    print("-" * 75)
    print("Note: Prices from official provider pages as of June 2026\n")


# --- RAW HTTP API CLIENTS ---

def call_gemini_api_raw(
    prompt: str, 
    api_key: str, 
    model: str = "gemini-1.5-flash",
    stream: bool = False
) -> Generator[str, None, None]:
    """
    Constructs a raw HTTP request to Gemini API.
    Uses urllib to avoid external dependencies.
    """
    # Gemini API uses separate endpoints for stream vs non-stream
    action = "streamGenerateContent" if stream else "generateContent"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as response:
            if stream:
                # Gemini streams a JSON array of events or multiple JSON objects
                # Let's read the stream chunk by chunk
                buffer = ""
                while True:
                    chunk = response.read(1024)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8")
                    
                    # Gemini returns standard stream in a single JSON array or chunks.
                    # For simplicity of parsing a raw chunked stream, we extract 'text' properties
                    # directly using index scans if it contains partial JSON objects.
                    # Here is a robust regex-free JSON parser for stream chunks:
                    while "text" in buffer:
                        try:
                            # Let's locate the first "text": "..." value in the buffer
                            idx = buffer.find('"text":')
                            if idx == -1:
                                break
                            start_quote = buffer.find('"', idx + 7)
                            if start_quote == -1:
                                break
                            
                            # Find end quote, avoiding escaped quotes
                            end_quote = start_quote + 1
                            while True:
                                end_quote = buffer.find('"', end_quote)
                                if end_quote == -1:
                                    break
                                # If it's escaped, continue
                                if buffer[end_quote - 1] == '\\':
                                    end_quote += 1
                                    continue
                                break
                            
                            if end_quote == -1:
                                break
                            
                            extracted_text = buffer[start_quote + 1:end_quote]
                            # Decode escape sequences (like \n, \t)
                            clean_text = bytes(extracted_text, "utf-8").decode("unicode_escape")
                            yield clean_text
                            
                            # Clean buffer up to end_quote
                            buffer = buffer[end_quote + 1:]
                        except Exception:
                            # If parsing partial buffer fails, wait for more data
                            break
            else:
                resp_data = json.loads(response.read().decode("utf-8"))
                yield resp_data["candidates"][0]["content"]["parts"][0]["text"]
                
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        raise RuntimeError(f"API Error ({e.code}): {error_msg}")


# --- MOCK FALLBACK FOR OFFLINE / KEYLESS RUNS ---

def call_mock_model(prompt: str, stream: bool = False) -> Generator[str, None, None]:
    """Mock engine simulating a streaming LLM response."""
    response_template = (
        "Here is the structured payload you requested: "
        '{"status": "success", "data": {"message": "Hello from Karpathy-style Agent Hub!", "tokens_used": 42}}'
    )
    if stream:
        for word in response_template.split(" "):
            time.sleep(0.05)  # Simulate latency
            yield word + " "
    else:
        yield response_template


# --- STRUCTURED JSON PARSER ---

def extract_and_parse_json(text: str) -> Dict[str, Any]:
    """
    Extracts the first valid JSON block from a raw string.
    Useful when LLM returns JSON enclosed in ```json ... ``` blocks.
    """
    # Find start and end brackets
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    
    if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
        raise ValueError("No valid JSON structure found in response.")
        
    json_candidate = text[start_idx:end_idx + 1]
    
    try:
        return json.loads(json_candidate)
    except json.JSONDecodeError as e:
        # Fallback cleaning if there are weird trailing commas or breaks
        try:
            # Let's try fixing simple json syntax errors (e.g. trailing commas)
            # by evaluating a safe subset or raising original
            raise ValueError(f"JSON Syntax Error: {e.msg} at line {e.lineno} col {e.colno}")
        except Exception:
            raise ValueError(f"Could not parse extracted JSON candidate. Raw candidate: {json_candidate}")


# --- RUNNER & DEMONSTRATION ---

def run_inference_demo():
    print("=== AI Engineering Lab: LLM Inference Primitive ===")
    
    # Show pricing reference
    print_pricing_table()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    model_name = "gemini-1.5-flash" if api_key else "mock-model"
    
    tracker = CostTracker(model_name)
    prompt = "Give me a JSON structure with an application log indicating a successfully initialized database connection."
    
    print(f"Prompt: '{prompt}'")
    tracker.track_request(prompt)
    
    print("\nStreaming response:", end=" ", flush=True)
    full_response = ""
    
    # Select engine
    if api_key:
        stream_generator = call_gemini_api_raw(prompt, api_key, model=model_name, stream=True)
    else:
        print("\n[NOTE] No GEMINI_API_KEY found. Running with mock local model.")
        stream_generator = call_mock_model(prompt, stream=True)
        
    for chunk in stream_generator:
        print(chunk, end="", flush=True)
        full_response += chunk
        
    print("\n")
    tracker.track_response(full_response)
    print(tracker.get_report())
    
    # Extracting Structured Output
    print("\n--- Structured Output Parsing ---")
    try:
        structured_data = extract_and_parse_json(full_response)
        print("Successfully parsed JSON:")
        print(json.dumps(structured_data, indent=2))
    except ValueError as e:
        print(f"Failed to parse structured output: {e}")

if __name__ == "__main__":
    run_inference_demo()
