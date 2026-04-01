import json
from datasets import load_dataset
from collections import defaultdict

def main():
    print("Loading hallucination dataset...")
    try:
        with open("rq2_hallucination_dataset.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find rq2_hallucination_dataset.json")
        return

    # Find the PRs where agent claimed success AND reviewer refuted
    confrontations = [pr for pr in data if pr.get("agent_claimed_success") and pr.get("reviewer_refuted")]
    confrontation_ids = {pr["pr_id"] for pr in confrontations}
    print(f"Found {len(confrontation_ids)} Direct Confrontation PRs.")

    if not confrontation_ids:
        print("No confrontations found to export.")
        return

    print("Loading HuggingFace conversations...")
    comments_ds = load_dataset("hao-li/AIDev", "pr_comments", split="train")
    reviews_ds = load_dataset("hao-li/AIDev", "pr_reviews", split="train")

    conversations = defaultdict(list)

    # 1. Grab PR Body 
    for pr in confrontations:
        if pr.get("body"):
            conversations[pr["pr_id"]].append(("🤖 AGENT (PR BODY)", pr["body"]))

    # 2. Grab Comments
    for comment in comments_ds:
        pr_id = comment.get("pr_id")
        if pr_id in confrontation_ids:
            author_type = getattr(comment, "user_type", "")
            user_login = str(comment.get("user", "")).lower()
            
            if author_type == "Bot" or "agent" in user_login or "bot" in user_login:
                author = "🤖 AGENT"
            else:
                author = f"👤 REVIEWER ({comment.get('user', 'Unknown')})"
                
            body = comment.get("body", "")
            if body:
                conversations[pr_id].append((author, body))

    # 3. Grab Reviews
    for review in reviews_ds:
        pr_id = review.get("pr_id")
        if pr_id in confrontation_ids:
            author_type = getattr(review, "user_type", "")
            user_login = str(review.get("user", "")).lower()
            
            if author_type == "Bot" or "agent" in user_login or "bot" in user_login:
                author = "🤖 AGENT"
            else:
                author = f"👤 REVIEWER ({review.get('user', 'Unknown')})"
                
            body = review.get("body", "")
            if body:
                conversations[pr_id].append((author, body))

    # Output to a readable markdown file
    output_file = "direct_confrontations_examples.md"
    print(f"Writing conversations to {output_file}...")
    
    with open(output_file, "w") as f:
        f.write("# Direct Confrontations: Agent Hallucinations vs. Reviewer Reality\n\n")
        f.write("Below are the exact conversational turns extracted from the 23 PRs where the autonomous agent asserted testing success, but the Human Reviewer explicitly refuted the claim due to CI failure or broken logic.\n\n")
        f.write("---\n\n")
        
        for pr in confrontations:
            pr_id = pr["pr_id"]
            url = pr.get("html_url", "Unknown URL")
            agent = pr.get("agent_type", "Unknown Agent")
            pr_num = pr.get("pr_number", "Unknown")
            
            f.write(f"## PR #{pr_num} ({agent})\n")
            f.write(f"**URL**: [{url}]({url})\n\n")
            
            turns = conversations.get(pr_id, [])
            for author, text in turns:
                f.write(f"### {author}\n")
                # Quote the text for readability
                for line in text.split("\n"):
                    f.write(f"> {line}\n")
                f.write("\n")
                
            f.write("---\n\n")

    print(f"Export completed successfully. Open {output_file} to read the conversations.")

if __name__ == "__main__":
    main()
