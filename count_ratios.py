import json
with open('rq1_deepseek_filtered.json', 'r') as f:
    data = json.load(f)
c = sum(1 for pr in data if (pr.get('test_additions',0)+pr.get('test_deletions',0))/(pr.get('prod_additions',0)+pr.get('prod_deletions',0) or 1e-10) > 10.0)
print('capped_count:', c, 'out of total:', len(data))
