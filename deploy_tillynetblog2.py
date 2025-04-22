import os
import shutil
import subprocess
import re

# === CONFIGURATION ===
obsidian_dir = r"C:\Users\micha\Documents\Local_Obsidian_Vault\my-home-lab-journey"
hugo_root_dir = r"C:\Users\micha\Documents\tillynetblog"
hugo_content_dir = os.path.join(hugo_root_dir, "content", "my-home-lab-journey")
attachments_dir = r"C:\Users\micha\Documents\Local_Obsidian_Vault\assets\images"
static_images_dir = os.path.join(hugo_root_dir, "static", "images")
about_src = r"C:\Users\micha\Documents\Local_Obsidian_Vault\pages\about.md"
about_dst_dir = os.path.join(hugo_root_dir, "content", "about")
about_dst = os.path.join(about_dst_dir, "index.md")
base_url = "https://blog.tillynet.com"

# === STEP 1: Sync Markdown Posts from Obsidian ===
if os.path.exists(hugo_content_dir):
    shutil.rmtree(hugo_content_dir)
shutil.copytree(obsidian_dir, hugo_content_dir)
print("✔ Copied markdown posts from Obsidian.")

# === STEP 2: Process Images in Markdown Files ===
for subdir, _, files in os.walk(hugo_content_dir):
    for filename in files:
        if filename.endswith(".md"):
            md_path = os.path.join(subdir, filename)
            with open(md_path, "r", encoding="utf-8") as file:
                content = file.read()

            images = re.findall(r'\[\[([^]]*\.png)\]\]', content)
            for image in images:
                markdown_image = f"![Image](/images/{image.replace(' ', '%20')})"
                content = content.replace(f"[[{image}]]", markdown_image)
                src_image = os.path.join(attachments_dir, image)
                if os.path.exists(src_image):
                    shutil.copy(src_image, static_images_dir)

            with open(md_path, "w", encoding="utf-8") as file:
                file.write(content)
print("✔ Processed images and updated markdown links.")

# === STEP 3: Copy About Page to /about/ as index.md ===
if os.path.exists(about_src):
    os.makedirs(about_dst_dir, exist_ok=True)
    shutil.copyfile(about_src, about_dst)
    print("✔ Updated About page as /about/index.md.")
else:
    print("⚠ About page not found in Obsidian vault; skipping.")


# === STEP 4: Build Hugo Site with baseURL ===
subprocess.run(["hugo", "-b", base_url], cwd=hugo_root_dir, check=True)
print("✔ Hugo site built with baseURL.")

# === STEP 5: Push changes to GitHub master ===
subprocess.run(["git", "checkout", "master"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "add", "."], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "commit", "-m", "Update blog content"], cwd=hugo_root_dir, check=False)
subprocess.run(["git", "push", "origin", "master"], cwd=hugo_root_dir, check=True)
print("✔ Pushed changes to GitHub master.")

# === STEP 6: Push public folder to hostinger branch ===
subprocess.run(["git", "subtree", "split", "--prefix", "public", "-b", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "push", "origin", "hostinger-deploy:hostinger", "--force"], cwd=hugo_root_dir, check=True)
subprocess.run(["git", "branch", "-D", "hostinger-deploy"], cwd=hugo_root_dir, check=True)
print("✔ Deployed public/ folder to GitHub hostinger branch.")
