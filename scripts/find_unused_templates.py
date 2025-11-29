#!/usr/bin/env python3
import os
import subprocess

repo_root = '/home/pranaya/Pro/LMS'
templates_dir = os.path.join(repo_root, 'library', 'lib', 'templates')

all_templates = []
for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html'):
            rel = os.path.relpath(os.path.join(root, f), repo_root)
            all_templates.append(rel)

unused = []
# Search for each template basename across the repo (excluding db and .pyc)
for tpl in sorted(all_templates):
    basename = os.path.basename(tpl)
    # use grep to search for the basename in the repo
    try:
        # -R recursive, -n show line nums, -I ignore binary, --exclude-dir to skip migrations maybe
        result = subprocess.run(['grep', '-R', '-n', '--exclude-dir=.git', '--exclude-dir=__pycache__', '--exclude-dir=migrations', basename, repo_root], capture_output=True, text=True)
        output = result.stdout.strip()
        if not output:
            unused.append(tpl)
    except Exception as e:
        print('Error searching for', tpl, e)

print('Found {} templates total'.format(len(all_templates)))
print('Found {} candidate-unused templates (no textual references found)'.format(len(unused)))
if unused:
    print('\nCandidate unused templates:')
    for u in unused:
        print(u)
else:
    print('\nNo candidate-unused templates found.')
