import os
import re
import shutil
import subprocess

# PATHS (Update if needed)
OBSIDIAN_POSTS_DIR = r"C:\Users\micha\Documents\Local_Obsidian_Vault\my-home-lab-journey"
OBSIDIAN_IMAGES_DIR = r"C:\Users\micha\Documents\Local_Obsidian_Vault\assets\images"
HUGO_CONTENT_DIR = r"C:\Users\micha\Documents\tillynetblog\content\my-home-lab-journey"
HUGO_STATIC_IMAGES_DIR = r"C:\Users\micha\Documents\tillynetblog\static\images"
HUGO_SITE_DIR = r"C:\Users\micha\Documents\tillynetblog"

def clean_hugo_content():
    if os.path.exists(HUGO_CONTENT_DIR):
        for item in os.listdir(HUGO_CONTENT_DIR):
            path = os.path.join(HUGO_CONTENT_DIR, item)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

def process_obsidian_notes():
    for root, _, files in os.walk(OBSIDIAN_POSTS_DIR):
        for file in files:
            if file.endswith(".md"):
                source_md = os.path.join(root, file)
                with open(source_md, 'r', encoding='utf-8') as f:
                    content = f.read()

                images = re.findall(r'\[\[([^]]+\.(?:png|jpg|jpeg|gif))\]\]', content)
                for image in images:
                    safe = image.replace(' ', '%20')
                    markdown_image = f"![Image](/images/{safe})"
                    content = content.replace(f"[[{image}]]", markdown_image)

                    image_path = os.path.join(OBSIDIAN_IMAGES_DIR, image)
                    if os.path.exists(image_path):
                        shutil.copy2(image_path, HUGO_STATIC_IMAGES_DIR)

                rel_path = os.path.relpath(source_md, OBSIDIAN_POSTS_DIR)
                target_md = os.path.join(HUGO_CONTENT_DIR, rel_path)
                os.makedirs(os.path.dirname(target_md), exist_ok=True)
                with open(target_md, 'w', encoding='utf-8') as f:
                    f.write(content)

def build_hugo():
    subprocess.run(["hugo", "-s", HUGO_SITE_DIR, "--cleanDestinationDir"], check=True)

def push_to_github():
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "add", "."], check=True)
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "commit", "-m", "Auto publish from Obsidian"], check=False)
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "push", "origin", "master"], check=True)

def deploy_to_hostinger():
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "branch", "-D", "hostinger-deploy"], check=False)
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "subtree", "split", "--prefix", "public", "-b", "hostinger-deploy"], check=True)
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "push", "-f", "origin", "hostinger-deploy:hostinger"], check=True)
    subprocess.run(["git", "-C", HUGO_SITE_DIR, "branch", "-D", "hostinger-deploy"], check=False)

# 🧠 Run the whole pipeline
clean_hugo_content()
process_obsidian_notes()
build_hugo()
push_to_github()
deploy_to_hostinger()
