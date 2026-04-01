import json
import random

def sample_json(filename, sample_rate, out_key, results_dict):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            
        sample_size = max(1, int(len(data) * sample_rate))
        # Use a fixed seed for reproducibility across inspections if needed
        random.seed(42)
        sampled_data = random.sample(data, sample_size)
        results_dict[out_key] = sampled_data
        print(f"Sampled {sample_size} entries from {filename} out of {len(data)} total ({(sample_rate*100):.1f}%).")
    except FileNotFoundError:
        print(f"Warning: {filename} not found.")

def main():
    print("Generating 1% samples for manual inspection...")
    results = {}
    
    # "regex only, that we got in the beginning"
    # This corresponds to Phase 2 metrics output BEFORE DeepSeek validation
    sample_json("rq1_metrics_dataset.json", 0.01, "regex_only_1_percent_sample", results)
    
    # "after running the deepseek"
    # This corresponds to Phase 3 output AFTER DeepSeek
    sample_json("rq1_deepseek_filtered.json", 0.01, "deepseek_filtered_1_percent_sample", results)
    
    out_file = "manual_inspection_samples.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved combined samples to {out_file}")

if __name__ == "__main__":
    main()
