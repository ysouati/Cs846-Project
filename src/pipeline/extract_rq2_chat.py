import json
import asyncio
import os
from collections import defaultdict
from datasets import load_dataset
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

CONCURRENCY_LIMIT = 5

PROMPT_SYSTEM = """You are an expert software engineering analyst evaluating Pull Request conversations.
I will provide you with the text conversation between an Autonomous Coding Agent (who authored the PR) and Human Reviewers.
The PR ultimately failed (it was not merged).

Your task is to analyze the conversation and evaluate two boolean flags:
1. `agent_claimed_success`: Did the agent explicitly state in its PR body or comments that it successfully ran the tests, that the tests passed, or that it successfully verified the logic? (Wait for explicit text claims of testing success. Providing a test file is not enough, it must state that the tests PASS or completely execute successfully.)
2. `reviewer_refuted`: Did the human reviewer explicitly state that the tests actually failed, that the CI is broken, or that the agent's code/tests do not work as claimed?

CRITICAL RULES:
- Output ONLY a valid JSON object. Do NOT wrap it in Markdown (```json).
- Format exactly: {"agent_claimed_success": bool, "reviewer_refuted": bool}
"""

async def analyze_conversation(semaphore, pr_id, conversation_text, max_retries=3):
    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": PROMPT_SYSTEM},
                        {"role": "user", "content": f"PR CONVERSATION:\n\n{conversation_text}"}
                    ],
                    response_format={"type": "json_object"},
                    stream=False
                )
                
                content = response.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                    
                result = json.loads(content.strip())
                return pr_id, result
            except Exception as e:
                await asyncio.sleep(2 ** attempt)
        
        return pr_id, {"agent_claimed_success": False, "reviewer_refuted": False}


async def main():
    print("1) Loading RQ1 Dataset to identify failed PRs...")
    with open("rq1_deepseek_filtered.json", "r") as f:
        rq1_data = json.load(f)

    # Failed PRs are those where resolution_time_seconds is None or merged_at is null
    failed_prs = [pr for pr in rq1_data if pr.get("resolution_time_seconds") is None]
    failed_pr_ids = {pr["pr_id"]: pr for pr in failed_prs}
    print(f"   Found {len(failed_prs)} Failed Test PRs out of {len(rq1_data)} total.")

    print("2) Loading Conversations from HuggingFace dataset...")
    # Load PR comments
    print("   Loading pr_comments...")
    comments_ds = load_dataset('hao-li/AIDev', 'pr_comments', split='train')
    
    # Load PR reviews
    print("   Loading pr_reviews...")
    reviews_ds = load_dataset('hao-li/AIDev', 'pr_reviews', split='train')

    conversations = defaultdict(list)
    
    # Also grab PR bodies
    print("   Extracting PR bodies...")
    for pr in failed_prs:
        if pr.get("body"):
            conversations[pr["pr_id"]].append(f"AGENT (PR BODY): {pr['body']}")

    print("   Mapping PR Comments...")
    for comment in comments_ds:
        pr_id = comment.get("pr_id")
        if pr_id in failed_pr_ids:
            author = "AGENT" if getattr(comment, "user_type", "") == "Bot" or "agent" in str(comment.get("user")).lower() else "REVIEWER"
            body = comment.get("body", "")
            if body:
                conversations[pr_id].append(f"{author} COMMENT: {body}")
                
    print("   Mapping PR Reviews...")
    for review in reviews_ds:
        pr_id = review.get("pr_id")
        if pr_id in failed_pr_ids:
            author = "AGENT" if getattr(review, "user_type", "") == "Bot" or "agent" in str(review.get("user")).lower() else "REVIEWER"
            body = review.get("body", "")
            if body:
                conversations[pr_id].append(f"{author} REVIEW: {body}")

    # Build the final conversation strings
    print("3) Compiling text prompts...")
    tasks_to_run = []
    
    cache_file = "rq2_deepseek_chat_cache.json"
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
        print(f"   Loaded {len(cache)} pre-evaluated conversations from cache.")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    for pr_id, turns in conversations.items():
        if pr_id in cache:
            continue
            
        full_text = "\n\n---\n\n".join(turns)
        
        # Prevent token overflow by truncating extreme logs if necessary
        # ~100k chars is well within context limits, but let's cap at 150k for safety
        if len(full_text) > 150000:
            full_text = full_text[:150000] + "\n...[TRUNCATED_LACK_OF_SPACE]..."
            
        if full_text.strip():
            tasks_to_run.append(analyze_conversation(semaphore, pr_id, full_text))

    if tasks_to_run:
        print(f"4) Sending {len(tasks_to_run)} conversations to DeepSeek for hallucination checks...")
        
        # Batch execution to print progress
        batch_size = 50
        for i in range(0, len(tasks_to_run), batch_size):
            batch = tasks_to_run[i:i+batch_size]
            results = await asyncio.gather(*batch)
            for pr_id, res in results:
                cache[pr_id] = res
            print(f"   Completed {min(i+batch_size, len(tasks_to_run))}/{len(tasks_to_run)}")
            
            # Save cache incrementally
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
    else:
        print("4) All conversations already evaluated.")

    print("5) Saving to rq2_hallucination_dataset.json...")
    
    # Merge the DeepSeek insights into the failed PR objects
    for pr in failed_prs:
        pr_id = pr["pr_id"]
        eval_data = cache.get(pr_id, {"agent_claimed_success": False, "reviewer_refuted": False})
        pr["agent_claimed_success"] = eval_data.get("agent_claimed_success", False)
        pr["reviewer_refuted"] = eval_data.get("reviewer_refuted", False)
        
    with open("rq2_hallucination_dataset.json", "w") as f:
        json.dump(failed_prs, f, indent=2)
        
    print("Success. Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
