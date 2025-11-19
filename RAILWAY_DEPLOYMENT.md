# Railway Deployment Guide - Rutabaga QA Website

**Status:** Ready for deployment to Railway
**Date:** 2025-11-18
**Completion:** 98% - Production ready

---

## Prerequisites

1. **Railway Account**
   - Sign up at https://railway.app
   - Connect your GitHub account

2. **Required Services**
   - PostgreSQL database (should already be running from Rutabaga Backend)
   - Rutabaga Backend API (answer service)

3. **Google OAuth Credentials**
   - Create OAuth 2.0 credentials at https://console.cloud.google.com/apis/credentials
   - Add authorized redirect URI: `https://your-app.railway.app/login/callback`

---

## Deployment Steps

### 1. Push Code to GitHub

```bash
cd ~/Documents/Rutabaga/Rutabaga_QA_Website
git push origin main
```

### 2. Create New Railway Project

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose `Rutabaga_QA_Website` repository
5. Railway will automatically detect the app

### 3. Configure Environment Variables

In the Railway dashboard, go to **Variables** and add:

#### Required Variables

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=<generate-strong-random-key>

# Database (use existing Rutabaga production database)
DATABASE_URL=postgresql://user:password@host:port/rutabaga

# Google OAuth 2.0
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GOOGLE_REDIRECT_URI=https://your-qa-app.railway.app/login/callback

# Answer Service (Rutabaga Backend)
ANSWER_SERVICE_URL=https://your-backend.railway.app/v2/answer
ANSWER_SERVICE_API_KEY=<optional-api-key>
```

#### Optional Variables

```bash
# Python version (if needed)
PYTHON_VERSION=3.11
```

### 4. Generate SECRET_KEY

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Copy the output and use it as `SECRET_KEY` in Railway.

### 5. Configure Google OAuth

1. Go to https://console.cloud.google.com/apis/credentials
2. Edit your OAuth 2.0 Client ID
3. Add to **Authorized redirect URIs**:
   - Development: `http://localhost:9000/login/callback`
   - Production: `https://your-qa-app.railway.app/login/callback`
4. Copy Client ID and Client Secret to Railway variables

### 6. Deploy

Railway will automatically deploy when:
- Environment variables are set
- Code is pushed to GitHub

Monitor deployment in Railway logs.

### 7. Verify Deployment

Once deployed, test these endpoints:

```bash
# Health check
curl https://your-qa-app.railway.app/health

# Should return: {"status": "healthy", "service": "qa-review-website"}
```

### 8. Add Custom Domain (Optional)

1. In Railway dashboard, go to **Settings**
2. Click **Generate Domain** or add custom domain
3. Update `GOOGLE_REDIRECT_URI` to match new domain

---

## Database Setup

The QA website uses the **same database** as Rutabaga Backend (`rutabaga`).

### Verify Required Schemas Exist

Connect to your production database and verify:

```sql
-- Check schemas exist
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('qa_reviews', 'public', 'content');

-- Check qa_reviews tables
\dt qa_reviews.*

-- Should show:
-- qa_reviews.response_queue
-- qa_reviews.reviews
-- qa_reviews.review_sessions
-- qa_reviews.production_updates
-- qa_reviews.reviewers
-- qa_reviews.rereview_requests
```

If schemas are missing, run migrations from the Backend repo.

---

## Environment Variables Summary

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `FLASK_ENV` | Yes | `production` | Set to production |
| `SECRET_KEY` | Yes | `<64-char-hex>` | Generate with `secrets.token_hex(32)` |
| `DATABASE_URL` | Yes | `postgresql://...` | Use existing Rutabaga database |
| `GOOGLE_CLIENT_ID` | Yes | `xxxxx.apps.googleusercontent.com` | From Google Console |
| `GOOGLE_CLIENT_SECRET` | Yes | `GOCSPX-xxxxx` | From Google Console |
| `GOOGLE_REDIRECT_URI` | Yes | `https://qa.railway.app/login/callback` | Match Railway domain |
| `ANSWER_SERVICE_URL` | Yes | `https://backend.railway.app/v2/answer` | Rutabaga Backend URL |
| `ANSWER_SERVICE_API_KEY` | No | `optional-key` | If backend requires auth |

---

## Post-Deployment Tasks

### 1. Create Initial Reviewers

Connect to database and add approved reviewers:

```sql
-- Add reviewers to qa_reviews.reviewers table
INSERT INTO qa_reviews.reviewers (email, name, is_active)
VALUES
  ('stephen.dominick@gmail.com', 'Stephen Dominick', true),
  ('manandhar001@gmail.com', 'Reviewername', true);
```

Or use the admin dashboard after first login (if you're an approved email).

### 2. Verify Queue Population

Check that responses are queued:

```sql
SELECT COUNT(*), status, intent
FROM qa_reviews.response_queue
GROUP BY status, intent;
```

Should show ~224 interaction queries pending.

### 3. Test Login Flow

1. Visit `https://your-qa-app.railway.app`
2. Click "Sign in with Google"
3. Authorize with approved Google account
4. Should redirect to review page

### 4. Test Review Workflow

1. Select intent (e.g., "Interaction")
2. Score segments
3. Submit review
4. Verify production database updated:

```sql
SELECT * FROM qa_reviews.production_updates
ORDER BY updated_at DESC LIMIT 5;

-- Check corresponding DDI record updated
SELECT subject_drug, object_drug, effect_s1, guidance, effect_complete
FROM public.document_ddi_pairs
WHERE subject_drug = 'warfarin' AND object_drug = 'aspirin';
```

---

## Troubleshooting

### Issue: 500 Error on Load

**Check:**
- Database URL is correct and accessible
- All required environment variables set
- Railway logs for detailed error

```bash
# View logs in Railway dashboard or CLI
railway logs
```

### Issue: OAuth Login Fails

**Check:**
- `GOOGLE_REDIRECT_URI` matches Google Console settings exactly
- Email is in approved list (`config.py:42-45`)
- Google OAuth consent screen configured

### Issue: Database Connection Fails

**Check:**
- DATABASE_URL format: `postgresql://user:pass@host:port/database`
- Database allows connections from Railway IPs
- Firewall rules allow Railway

### Issue: Can't See Reviews

**Check:**
- User email exists in `qa_reviews.reviewers` table
- User is marked as `is_active = true`
- Response queue has items: `SELECT COUNT(*) FROM qa_reviews.response_queue WHERE status = 'pending'`

---

## Architecture Overview

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │
         ↓ HTTPS
┌─────────────────────────┐
│  QA Website (Railway)   │
│  - Flask App            │
│  - Port from $PORT      │
│  - Gunicorn (2 workers) │
└────────┬────────────────┘
         │
         ├──→ PostgreSQL (Railway/Existing)
         │    - qa_reviews schema
         │    - public.document_ddi_pairs
         │
         └──→ Rutabaga Backend (Railway)
              - /v2/answer endpoint
```

---

## Monitoring

### Key Metrics to Track

1. **Response Times**
   - Review page load: Should be <2s
   - Submit review: Should be <500ms

2. **Database Performance**
   - Connection pool usage
   - Query execution times

3. **User Activity**
   - Reviews submitted per day
   - Average review scores
   - Flagged items count

### Railway Monitoring

- Use Railway **Metrics** tab to monitor:
  - CPU usage
  - Memory usage
  - Request volume
  - Error rate

---

## Scaling Considerations

### Current Configuration

```
Procfile: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

### If You Need More Capacity

1. **Increase Workers**
   ```
   web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
   ```

2. **Upgrade Railway Plan**
   - Free tier: Suitable for <5 reviewers
   - Hobby: 5-10 reviewers
   - Pro: 10+ reviewers

3. **Database Connection Pool**
   - Current: 10 connections (`config.py:21`)
   - Increase if needed: `pool_size: 20`

---

## Security Checklist

- [x] `SECRET_KEY` is random and secret
- [x] `SESSION_COOKIE_SECURE = True` in production
- [x] `SESSION_COOKIE_HTTPONLY = True`
- [x] Database credentials not in code
- [x] `.env` file in `.gitignore`
- [x] HTTPS enforced by Railway
- [x] OAuth redirect URI matches exactly
- [x] Only approved emails can access

---

## Backup Strategy

### Database Backups

Railway automatically backs up PostgreSQL databases.

**Manual Backup:**

```bash
# Backup to local file
pg_dump -h <railway-host> -U <user> -d rutabaga \
  --schema=qa_reviews > qa_reviews_backup_$(date +%Y%m%d).sql

# Restore if needed
psql -h <railway-host> -U <user> -d rutabaga < qa_reviews_backup_YYYYMMDD.sql
```

---

## Cost Estimate

### Railway Pricing (as of 2025)

- **Free Tier**: $0/month
  - 500 hours/month
  - Suitable for dev/testing

- **Hobby**: $5/month
  - Unlimited hours
  - Suitable for small team (5-10 reviewers)

- **Pro**: $20/month
  - Higher limits
  - Suitable for production (10+ reviewers)

**Estimated Cost for Production:**
- QA Website: $5-20/month (Hobby or Pro)
- Database: Already covered by Backend
- Total: $5-20/month

---

## Support

### Railway Support

- Documentation: https://docs.railway.app
- Discord: https://discord.gg/railway
- Status: https://status.railway.app

### Application Issues

- GitHub Issues: https://github.com/piiopah-aardvark/Rutabaga_QA_Website/issues
- Check logs: `railway logs`
- Database console: Railway dashboard > Database > Console

---

## Quick Reference

### Common Commands

```bash
# View logs
railway logs

# Connect to database
railway run psql

# Set environment variable
railway variables set KEY=value

# Redeploy
git push origin main

# Run locally with production config
FLASK_ENV=production python app.py
```

### Important URLs

- Railway Dashboard: https://railway.app/dashboard
- Google OAuth Console: https://console.cloud.google.com/apis/credentials
- QA Website Repo: https://github.com/piiopah-aardvark/Rutabaga_QA_Website

---

## Next Steps After Deployment

1. ✅ Deploy to Railway
2. ✅ Configure environment variables
3. ✅ Test login flow
4. ✅ Add reviewers to database
5. ✅ Test review submission
6. ✅ Verify production updates
7. ✅ Monitor for 24 hours
8. ✅ Invite team to start reviewing
9. ✅ Monitor review quality metrics
10. ✅ Iterate based on feedback

---

**Deployment Checklist Complete!** 🚀

The QA website is production-ready and can improve your DDI data quality starting today.
