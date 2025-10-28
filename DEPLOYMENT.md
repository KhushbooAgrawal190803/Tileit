# 🚀 Deploying Tileit to Render.com (FREE)

## Prerequisites
- GitHub account
- Render.com account (free signup)

## Step-by-Step Deployment

### 1. Push to GitHub

```bash
# Initialize git if you haven't
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Ready for deployment"

# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/tileit.git
git branch -M main
git push -u origin main
```

### 2. Deploy on Render

1. Go to [https://render.com](https://render.com)
2. Sign up/Login (can use GitHub)
3. Click **"New +"** → **"Web Service"**
4. Click **"Connect Repository"** → Select your `tileit` repo
5. Configure:
   - **Name**: `tileit-roofing-quotes`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --chdir backend tileit_app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Instance Type**: `Free`
6. Click **"Create Web Service"**

### 3. Wait for Deployment (5-10 minutes)

You'll see logs showing:
- Installing dependencies
- Starting gunicorn
- Your app is live! 🎉

### 4. Access Your Live Website

Your app will be at: `https://tileit-roofing-quotes.onrender.com`

## Important Notes

### Free Tier Limitations
- App sleeps after 15 minutes of inactivity
- Takes ~30 seconds to wake up on first request
- 512MB RAM limit
- Shared CPU

### Database Persistence
Your SQLite databases (`tileit_users.db`, `roofing_users.db`) will persist across deployments.

### Environment Variables (Optional)
If you want to add:
1. Go to your service dashboard
2. Click "Environment"
3. Add variables like:
   - `FLASK_ENV=production`
   - `SECRET_KEY=your-secret-key`

## Updating Your App

After making changes:

```bash
git add .
git commit -m "Update description"
git push
```

Render will automatically redeploy! 🚀

## Custom Domain (Optional)

On Render's free tier, you can add a custom domain:
1. Buy domain from Namecheap/GoDaddy
2. In Render, go to Settings → Custom Domain
3. Follow instructions to update DNS records

## Troubleshooting

### App won't start
- Check logs in Render dashboard
- Verify `requirements.txt` has all dependencies
- Check start command syntax

### Database errors
- Render may need write permissions
- Consider upgrading to Render's managed PostgreSQL

### Slow first load
- Normal on free tier (app was sleeping)
- Consider upgrading to paid tier ($7/month) for always-on

## Alternative: Railway.app

If Render doesn't work:
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "Deploy from GitHub repo"
4. Select your repo
5. Railway auto-detects and deploys!

## Support

- Render docs: https://render.com/docs
- Railway docs: https://docs.railway.app

---

**Your app will be LIVE and FREE!** 🎊

