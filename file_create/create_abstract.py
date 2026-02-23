import json
import os

# Load JSON content
with open('set5.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Templates
abstract_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
{body_content}
</body>
</html>
"""

content_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Excerpt</title>
</head>
<body>
    <h2>Excerpt</h2>
    {excerpt}
    <h2>Original Abstract</h2> 
    {abstract}
</body>
</html>
"""

# Generate files
for entry in data:
    idx = entry['index']
    
    # 1. abstract##.html → abstract_gpt
    with open(f'../abstract/abstract{idx}.html', 'w', encoding='utf-8') as f:
        f.write(abstract_template.format(body_content=entry['abstract_gpt']))
    
    # 2. abstract1##.html → abstract_human
    with open(f'../abstract/abstract1{idx}.html', 'w', encoding='utf-8') as f:
        f.write(abstract_template.format(body_content=entry['abstract_human']))
    
    # 3. content##.html → excerpt + abstract_gpt
    with open(f'../content/content{idx}.html', 'w', encoding='utf-8') as f:
        f.write(content_template.format(excerpt=entry['excerpt'], abstract=entry['abstract_gpt']))
    
    # 4. content1##.html → excerpt + abstract_human
    with open(f'../content/content1{idx}.html', 'w', encoding='utf-8') as f:
        f.write(content_template.format(excerpt=entry['excerpt'], abstract=entry['abstract_human']))
