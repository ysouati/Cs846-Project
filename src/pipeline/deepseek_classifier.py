import json
import asyncio
import os
import math
from collections import defaultdict
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Process in chunks to save tokens and conform to the model's context
CHUNK_SIZE = 150
# Simultaneous API requests to avoid rate limits
CONCURRENCY_LIMIT = 5

PROMPT_SYSTEM = """You are an expert software test classifier. I will provide you a JSON array of file paths. 
Your task is to determine if each file path represents an actual software test file.
If it is NOT a test file, classify it as "not_a_test".
If it IS a test file, classify it deeply as exactly ONE of: "unit", "integration", or "e2e".
CRITICAL RULES:
- Output ONLY a valid JSON object. Do NOT wrap it in Markdown (```json).
- The JSON object must consist of exact file paths as keys, and the classification string as values.
- You must classify EVERY path provided in the list."""

async def classify_chunk(paths_chunk, semaphore, chunk_idx, total_chunks, max_retries=3):
    async with semaphore:
        prompt_user = json.dumps(paths_chunk)
        
        for attempt in range(max_retries):
            try:
                print(f"   [{chunk_idx}/{total_chunks}] Sending chunk to DeepSeek...")
                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": PROMPT_SYSTEM},
                        {"role": "user", "content": prompt_user}
                    ],
                    response_format={"type": "json_object"},
                    stream=False
                )
                
                response_content = response.choices[0].message.content
                # Simple cleanup if the model still wraps in markdown
                if response_content.startswith('```json'):
                    response_content = response_content[7:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
                    
                classification = json.loads(response_content.strip())
                return classification
            except Exception as e:
                print(f"   [Exception on chunk {chunk_idx}] {e}. Retrying...")
                await asyncio.sleep(2 ** attempt)
                
        print(f"   [FAILED] Chunk {chunk_idx} failed after {max_retries} retries.")
        # Return fallback heuristic preserving original paths as unknown safely if totally failed
        return {}

async def main():
    print("1) Loading initial RQ1 Metrics Dataset...")
    try:
        with open("rq1_metrics_dataset.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: rq1_metrics_dataset.json not found.")
        return

    # Extract all unique paths
    unique_paths = set()
    for pr in data:
        for paths in pr.get("test_type_paths", {}).values():
            unique_paths.update(paths)
            
    paths_list = list(unique_paths)
    print(f"   Found {len(paths_list)} unique test paths to classify.")
    
    # Check for existing cache
    cache_file = "deepseek_cache.json"
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
        print(f"   Loaded {len(cache)} pre-classified paths from {cache_file}.")
        
        # Filter out already classified paths
        paths_list = [p for p in paths_list if p not in cache]
        print(f"   {len(paths_list)} paths remaining to classify.")
        
    if len(paths_list) > 0:
        chunks = [paths_list[i:i + CHUNK_SIZE] for i in range(0, len(paths_list), CHUNK_SIZE)]
        total_chunks = len(chunks)
        print(f"2) Batching into {total_chunks} prompts for DeepSeek API...")
        
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        
        tasks = [classify_chunk(chunk, semaphore, idx+1, total_chunks) for idx, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            cache.update(res)
                
        print("3) Saving extracted cache to deepseek_cache.json...")
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
    else:
        print("2) All paths already classified in cache.")
        
    print("4) Re-building PR Dataset with validated paths...")
    final_prs = []
    
    for pr in data:
        new_paths = {
            "unit": [],
            "integration": [],
            "e2e": []
        }
        
        # Re-map all old paths
        for old_type, paths in pr.get("test_type_paths", {}).items():
            for p in paths:
                deepseek_decision = cache.get(p, "unknown").lower()
                
                # Default to the heuristic categorization if DeepSeek failed to categorize it
                if deepseek_decision == "unknown":
                    deepseek_decision = old_type
                    
                if deepseek_decision in new_paths:
                    new_paths[deepseek_decision].append(p)
                elif deepseek_decision == "not_a_test":
                    pass # Discard
                else:
                    # In case DeepSeek halucinates a type, bucket it back to unit
                    new_paths["unit"].append(p)
                    
        # Calculate new counts
        new_counts = {
            "unit": len(new_paths["unit"]),
            "integration": len(new_paths["integration"]),
            "e2e": len(new_paths["e2e"])
        }
        
        total_valid = sum(new_counts.values())
        if total_valid == 0:
            # PR has NO valid tests after DeepSeek validation, discard the PR entirely
            continue
            
        # Determine new dominant type
        dominant = max(new_counts, key=new_counts.get)
        
        pr["test_type_paths"] = new_paths
        pr["test_type_counts"] = new_counts
        pr["dominant_test_type"] = dominant
        
        final_prs.append(pr)
        
    print(f"   Final Valid PRs after filtering: {len(final_prs)} (Started with {len(data)})")
    
    print("5) Saving to rq1_deepseek_filtered.json...")
    with open("rq1_deepseek_filtered.json", "w") as f:
        json.dump(final_prs, f, indent=2)
        
    print("Success. Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
