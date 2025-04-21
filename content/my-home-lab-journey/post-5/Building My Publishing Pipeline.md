---
title: "Building My Publishing Pipeline: Obsidian → Hugo → GitHub → Hostinger"
date: 2025-04-20
tags: ["tillynet", "automation", "hugo", "obsidian", "python", "github", "hostinger"]
categories: ["My Home Lab Journey"]
draft: false
---

# 🔁 Obsidian → Hugo → GitHub → Hostinger Automation Workflow

This post documents the full setup of my **static site publishing pipeline** that automates taking blog posts from **Obsidian**, rendering them with **Hugo**, pushing the output to **GitHub**, and then having **Hostinger** automatically update my website via webhook.

---

## 🛠️ Tools Used

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

## ⚙️ What the Automation Script Does

- **Clears old blog posts** from Hugo’s `/content/my-home-lab-journey`
    
- **Copies blog post folders** from Obsidian vault into Hugo
    
- **Converts image embeds** (`![Image](/images/image.png)`) to Hugo-style `![Image Description](...)`
    
- **Copies images** to `static/images`
    
- **Builds the Hugo site** with:
    


```bash
hugo -D --cleanDestinationDir --themesDir=./themes
```


- **Pushes** full repo to GitHub `master`
    
- **Subtree pushes** `public/` output to `hostinger` branch
    

---

## 🐞 Issues I Encountered

### ❌ Website Styling Not Matching Local Preview

- **Problem:** Hostinger version didn’t load custom CSS or theme
    
- **Fix:** Used this build command:
    
    bash
    
    CopyEdit
    
    `hugo -D --cleanDestinationDir --themesDir=./themes`
    

### ❌ CSS Not Applying on Deployed Site

- **Root Cause:** Hostinger was caching fingerprinted CSS
    
- **Fix:**
    
    - Disabled Hugo asset fingerprinting in `hugo.yaml`:
        
        
        ```yaml
        assets:
		  disableFingerprinting: true
		```
        
    - Verified correct path: `assets/css/custom.css`
        

---

## 🧠 Lessons Learned

- Static site deployment workflows require full control over content paths and assets
    
- Asset fingerprinting can break styling if not handled properly
    
- Obsidian's `[[embed]]` syntax must be converted for Hugo compatibility
    
- Git subtree pushing keeps deployment clean and isolated to `public/`
    

---

## ✅ Final Outcome

- 🔁 End-to-end deployment is fully automated
    
- ✍️ Blog posts are written in Obsidian subfolders
    
- 🚀 Single Python script deploys everything to GitHub and Hostinger
    
- 🧼 Duplicate post issues and CSS bugs resolved
    
- ✨ Dark/light theme and custom styles work across devices
    

---

## 🧾 Resume Bullet

> Built an automated static site deployment pipeline linking Obsidian, Hugo (PaperMod), GitHub, and Hostinger via webhook; resolved CSS asset fingerprinting issues, enabled Hugo theme integration, and automated blog post syncing using Python.