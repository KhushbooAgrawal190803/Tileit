# GitHub Pages Setup Guide

## Option 1: Host in Same Repository (Recommended)

### Step 1: Commit the Landing Page
```bash
git add landing-page/
git commit -m "Add landing page for Google Ads"
git push origin master
```

### Step 2: Enable GitHub Pages
1. Go to your GitHub repository: `https://github.com/KhushbooAgrawal190803/Tileit`
2. Click **Settings** (top menu)
3. Scroll down to **Pages** (left sidebar)
4. Under **Source**, select:
   - **Branch**: `master` (or `main`)
   - **Folder**: `/landing-page`
5. Click **Save**

### Step 3: Access Your Site
Your landing page will be available at:
```
https://khushbooagrawal190803.github.io/Tileit/landing-page/
```

**Note:** GitHub Pages serves from the root, so you'll need to access it via the full path.

---

## Option 2: Create Separate Repository (Better for Landing Page)

### Step 1: Create New Repository
1. Go to GitHub and create a new repository (e.g., `tileit-landing-page`)
2. Don't initialize with README

### Step 2: Push Landing Page Files
```bash
cd landing-page
git init
git add .
git commit -m "Initial commit: Landing page"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tileit-landing-page.git
git push -u origin main
```

### Step 3: Enable GitHub Pages
1. Go to repository **Settings** → **Pages**
2. Select **Source**: `main` branch, `/ (root)` folder
3. Click **Save**

### Step 4: Access Your Site
Your landing page will be available at:
```
https://YOUR_USERNAME.github.io/tileit-landing-page/
```

This is cleaner and gives you a dedicated URL for your landing page!

---

## Which Option to Choose?

- **Option 1**: Keep everything in one repo, but URL includes `/landing-page/`
- **Option 2**: Cleaner URL, separate repo, better for marketing/ads

**Recommendation:** Use Option 2 for a cleaner, shorter URL perfect for Google Ads!

