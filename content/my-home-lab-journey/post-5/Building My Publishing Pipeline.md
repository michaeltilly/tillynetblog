---
title: "Building My Publishing Pipeline: Obsidian → Hugo → GitHub → Hostinger"
date: 2025-04-20
tags: ["tillynet", "automation", "hugo", "obsidian", "python", "github", "hostinger"]
categories: ["My Home Lab Journey"]
draft: false
---

# Obsidian → Hugo → GitHub → Hostinger Automation Workflow

This post documents the full setup of my **static site publishing pipeline** that automates taking blog posts from **Obsidian**, rendering them with **Hugo**, pushing the output to **GitHub**, and then having **Hostinger** automatically update my website via webhook.

---

## Tools Used

- **Obsidian** – Markdown note-taking and blog writing  
- **Hugo** – Static site generator using the [PaperMod theme](https://github.com/adityatelange/hugo-PaperMod) 
	- [Hugo PaperMod Wiki](https://github.com/adityatelange/hugo-PaperMod/wiki/Installation)
	- [My Hugo yaml File](https://github.com/michaeltilly/tillynetblog/blob/master/hugo.yaml)
- **GitHub** – Repository with two branches:  
  - `master` → Hugo project & content  
  - `hostinger` → Static site output  
- **Hostinger** – Web hosting platform with webhook integration  
- **Python** – Automation script for content syncing and site deployment [My Automation Script](https://github.com/michaeltilly/tillynetblog/blob/master/deploy_tillynetblog2.py)

---

## 📁 Folder Structure

```plaintext
📂 Local_Obsidian_Vault/
  └── my-home-lab-journey/
      ├── post-1/
	        └── index.md
      ├── post-2/
	        └── index.md
      ├── post-3/
	        └── index.md
      └── ...

📂 tillynetblog/
  ├── hugo.yaml
  ├── content/
  │   └── my-home-lab-journey/
  ├── public/
  ├── themes/
  │   └── PaperMod/
  └── static/
	  └── images
      └── css/custom.css
```

---
## What the Automation Script Does

### Imports

```python
import os
import shutil
import subprocess
import re
```

- **os**: for filesystem operations like path handling
- **shutil**: for copying/removing files and directories
- **subprocess**: for running shell commands like ``hugo`` and ``git``
- **re**: for finding image links in markdown via regular expressions

### Configuration

```python
obsidian_dir = r"C:\Users\micha\Documents\Local_Obsidian_Vault\my-home-lab-journey"
hugo_root_dir = r"C:\Users\micha\Documents\tillynetblog"
hugo_content_dir = os.path.join(hugo_root_dir, "content", "my-home-lab-journey")
attachments_dir = r"C:\Users\micha\Documents\Local_Obsidian_Vault\assets\images"
static_images_dir = os.path.join(hugo_root_dir, "static", "images")
about_src = r"C:\Users\micha\Documents\Local_Obsidian_Vault\pages\about.md"
about_dst_dir = os.path.join(hugo_root_dir, "content", "about")
about_dst = os.path.join(about_dst_dir, "index.md")
base_url = "https://blog.tillynet.com"
```

- Sets paths to:
	- Obsidian content (``obsidian_dir``)
	- Hugo blog folder
	- Where to copy markdown posts
	- Where Obsidian images are and where to move them
	- Source/destination for the ``about.md`` file
	- The blog's base URL for Hugo

### STEP 1: Copy Markdown Posts

```python
if os.path.exists(hugo_content_dir):
    shutil.rmtree(hugo_content_dir)
shutil.copytree(obsidian_dir, hugo_content_dir)
print("✔ Copied markdown posts from Obsidian.")
```

- Deletes existing markdown content in Hugo
- Copies fresh markdown files from Obsidian
- Confirms the copy

### STEP 2: Convert Image Embeds and Copy Images

```python
for subdir, _, files in os.walk(hugo_content_dir):
    for filename in files:
        if filename.endswith(".md"):
            ...
```

- iterates through every markdown file in the blog content

```python
            images = re.findall(r'\[\[([^]]*\.png)\]\]', content)
```

-  Looks for image link like (``example.png``)

```python
            for image in images:
                markdown_image = f"![Image](/images/{image.replace(' ', '%20')})"
```

- Replaces with standard Markdown image syntax

```python
                src_image = os.path.join(attachments_dir, image)
                if os.path.exists(src_image):
                    shutil.copy(src_image, static_images_dir)
```

- copies matching images from Obsidian to Hugo's static image folder

```python
            with open(md_path, "w", encoding="utf-8") as file:
                file.write(content)
```

- Overwrites the file with the updated content

```python
print("✔ Processed images and updated markdown links.")
```

- Confirms processing is complete

### STEP 3: Copy About Page

```python
if os.path.exists(about_src):
    os.makedirs(about_dst_dir, exist_ok=True)
    shutil.copyfile(about_src, about_dst)
    print("✔ Updated About page as /about/index.md.")
else:
    print("⚠ About page not found in Obsidian vault; skipping.")
```

- Copies ``about.md`` from Obsidian to Hugo content
- Skips and warns if the file is missing

### STEP 4: Clean Existing ``public/`` Folder

```python
public_dir = os.path.join(hugo_root_dir, "public")
if os.path.exists(public_dir):
    shutil.rmtree(public_dir)
    print("✔ Cleaned existing public/ folder.")
```

- Removes the old ``public/`` folder
- Forces Hugo to rebuild the entire static site from scratch, picking up all new pages and changes

### STEP 5: Build the Hugo Site

```python
subprocess.run(["hugo", "--buildDrafts", "--buildFuture", "-b", base_url], cwd=hugo_root_dir, check=True)
print("✔ Hugo site built with baseURL.")
```

- Builds the site using the ``hugo`` command with my specified ``BaseURL``

### STEP 6: Push Source Files to GitHub ``master``

```python
subprocess.run(["git", "checkout", "master"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "add", "."], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "commit", "-m", "Update blog content"], cwd=hugo_root_dir, check=False)
subprocess.run(["git", "push", "origin", "master"], cwd=hugo_root_dir, check=True)
print("✔ Pushed changes to GitHub master.")
```

- Commits and pushes all changes to the ``master`` branch

### STEP 7: Deploy Public Folder to ``hostinger`` Branch

```python
subprocess.run(["git", "subtree", "split", "--prefix", "public", "-b", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "push", "origin", "hostinger-deploy:hostinger", "--force"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "branch", "-D", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
print("✔ Deployed public/ folder to GitHub hostinger branch.")
```

- Splits ``public/`` into a new branch
- Pushes it forcefully to the ``hostinger`` branch on GitHub (used for site deployment)
- Deletes the temporary ``hostinger-deploy`` branch
	- This is necessary for our webhook to recognize the changes

---

##  Issues I Encountered  

###  CSS Not Applying on Deployed Site

- **Root Cause:** Hostinger was caching fingerprinted CSS
    
- **Fix:**
    
    - Disabled Hugo asset fingerprinting in `hugo.yaml`:
        
        
        ```yaml
        assets:
		  disableFingerprinting: true
		```
        
    - Verified correct path: `assets/css/custom.css`
        

---

## Lessons Learned

- Static site deployment workflows require full control over content paths and assets
- Asset fingerprinting can break styling if not handled properly
- Obsidian's `[[embed]]` syntax must be converted for Hugo compatibility
- Git subtree pushing keeps deployment clean and isolated to `public/`
- Have my python automation script remove the old ``public/`` folder so that Hugo is forced to rebuild the entire static site from scratch thus picking up all new pages and changes
    

---

## Final Outcome

- End-to-end deployment is fully automated
    
- Blog posts are written in Obsidian subfolders
    
-  Single Python script deploys everything to GitHub and Hostinger
    
- Duplicate post issues and CSS bugs resolved
    
-  Dark/light theme and custom styles work across devices
    

---

## Resume Bullet

> Built an automated static site deployment pipeline linking Obsidian, Hugo (PaperMod), GitHub, and Hostinger via webhook; resolved CSS asset fingerprinting issues, enabled Hugo theme integration, and automated blog post syncing using Python.