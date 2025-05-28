import os
import shutil
import subprocess
import re

# === CONFIGURATION ===
obsidian_dir = r"C:\Users\tillyadmin\Documents\TillyDomain_Obsidian_Vault\on-premise-engineering-labs"
cloud_labs_dir = r"C:\Users\tillyadmin\Documents\TillyDomain_Obsidian_Vault\cloud-engineering-labs"
hugo_root_dir = r"C:\Users\tillyadmin\Documents\tillynetblog"
hugo_content_dir = os.path.join(hugo_root_dir, "content", "on-premise-engineering-labs")
hugo_cloud_labs_dir = os.path.join(hugo_root_dir, "content", "cloud-engineering-labs")
attachments_dir = r"C:\Users\tillyadmin\Documents\TillyDomain_Obsidian_Vault\assets\images"
static_images_dir = os.path.join(hugo_root_dir, "static", "images")
about_src = r"C:\Users\tillyadmin\Documents\TillyDomain_Obsidian_Vault\pages\about.md"
about_dst_dir = os.path.join(hugo_root_dir, "content", "about")
about_dst = os.path.join(about_dst_dir, "index.md")
base_url = "https://blog.tillynet.com"

def process_content_directory(source_dir, destination_dir, content_type):
    """Process a content directory (copy markdown and handle images)"""
    print(f"📁 Processing {content_type} content...")
    
    # Remove existing content
    if os.path.exists(destination_dir):
        shutil.rmtree(destination_dir)
    
    # Check if source directory exists
    if not os.path.exists(source_dir):
        print(f"⚠ {content_type} directory not found: {source_dir} - skipping.")
        return
    
    # Copy content
    shutil.copytree(source_dir, destination_dir)
    print(f"✔ Copied {content_type} markdown posts from Obsidian.")
    
    # Process images in markdown files
    for subdir, _, files in os.walk(destination_dir):
        for filename in files:
            if filename.endswith(".md"):
                md_path = os.path.join(subdir, filename)
                with open(md_path, "r", encoding="utf-8") as file:
                    content = file.read()

                # Find Obsidian-style image embeds (keeping your original regex for consistency)
                images = re.findall(r'\[\[([^]]*\.png)\]\]', content)
                for image in images:
                    markdown_image = f"![Image](/images/{image.replace(' ', '%20')})"
                    content = content.replace(f"[[{image}]]", markdown_image)
                    src_image = os.path.join(attachments_dir, image)
                    if os.path.exists(src_image):
                        shutil.copy(src_image, static_images_dir)

                with open(md_path, "w", encoding="utf-8") as file:
                    file.write(content)
    
    print(f"✔ Processed images and updated markdown links for {content_type}.")

# === STEP 1: Sync Markdown Posts from Obsidian (On Premise Engineering Labs) ===
process_content_directory(obsidian_dir, hugo_content_dir, "On-Premise Engineering Labs")

# === STEP 2: Sync Markdown Posts from Obsidian (Cloud Engineering Labs) ===
process_content_directory(cloud_labs_dir, hugo_cloud_labs_dir, "Cloud Engineering Labs")

# === STEP 3: Copy About Page to /about/ as index.md ===
if os.path.exists(about_src):
    os.makedirs(about_dst_dir, exist_ok=True)
    shutil.copyfile(about_src, about_dst)
    print("✔ Updated About page as /about/index.md.")
else:
    print("⚠ About page not found in Obsidian vault; skipping.")

# === STEP 4: Clean existing public/ folder ===
public_dir = os.path.join(hugo_root_dir, "public")
if os.path.exists(public_dir):
    shutil.rmtree(public_dir)
    print("✔ Cleaned existing public/ folder.")

# === STEP 5: Build Hugo Site with baseURL ===
build_result = subprocess.run(["hugo", "--buildDrafts", "--buildFuture", "-b", base_url], cwd=hugo_root_dir)

if build_result.returncode != 0:
    print("❌ Hugo build failed. Aborting deployment.")
    exit(1)

# Safety check: confirm public/ folder has content
if not os.listdir(public_dir):
    print("❌ Hugo public/ folder is empty after build. Aborting deployment.")
    exit(1)

print("✔ Hugo site built successfully with content.")

# === STEP 6: Push changes to GitHub master ===
subprocess.run(["git", "checkout", "master"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "add", "."], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "commit", "-m", "Update blog content"], cwd=hugo_root_dir, check=False)
subprocess.run(["git", "push", "origin", "master"], cwd=hugo_root_dir, check=True)
print("✔ Pushed changes to GitHub master.")

# === STEP 7: Push public folder to hostinger branch ===
subprocess.run(["git", "subtree", "split", "--prefix", "public", "-b", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "push", "origin", "hostinger-deploy:hostinger", "--force"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "branch", "-D", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
print("✔ Deployed public/ folder to GitHub hostinger branch.")