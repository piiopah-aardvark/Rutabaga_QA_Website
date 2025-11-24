# QA Website Workflow Testing Guide

## Test Setup Complete ✅

**Test Interaction ID**: 609 (clearly marked test item)
**Test Query**: "🧪 TEST ITEM - SAFE TO DELETE - Can I take TestDrugA with TestDrugB?"
**Your Reviewer Account**: stephen.dominick@gmail.com (admin)

---

## Testing Workflow

### 1. Sign In
- Go to: https://rutabagaqawebsite-production.up.railway.app
- Sign in with: `stephen.dominick@gmail.com`

### 2. Start Reviewing
- The first item in your queue should be: **"🧪 TEST ITEM - SAFE TO DELETE - Can I take TestDrugA with TestDrugB?"**
- This is queue item **#609** (clearly marked test data, safe to delete)

---

## Test 1: Info Button

**Action**: Click the **ℹ️ Info** button

**Expected Behavior**:
- Modal opens showing interaction details
- Shows drug pairs: TestDrugA + TestDrugB
- Shows 3 segments (S1, S2, S3)

**Verification**: Visual inspection - modal displays correctly

---

## Test 2: Save as Draft

**Action**:
1. Score segment S1 as **4**
2. Add suggestion: "Could be clearer about severity"
3. Click **💾 Save Draft**

**Expected Behavior**:
- Success message appears
- Counter updates: "Drafts: 1"
- Item moves out of queue

**Database Verification**:
```bash
# Run this to verify draft was saved
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
SELECT
    r.id,
    r.status,
    r.segment_scores,
    rq.status as queue_status
FROM qa_reviews.reviews r
JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
WHERE r.response_queue_id = 609;"
```

**Expected Result**:
- 1 row returned
- `r.status` = 'draft'
- `rq.status` = 'draft'
- `segment_scores` contains your scores

---

## Test 3: Flag for Review

**Action**:
1. Go to your **Review History** tab
2. Find the draft for item #609
3. Click **Re-review**
4. Click **🚩 Flag for Review**
5. Enter reason: "Test flag - needs clinical expert review"

**Expected Behavior**:
- Flag modal opens
- After submitting: Success message
- Counter updates: "Flagged: 1"

**Database Verification**:
```bash
# Verify flag was recorded
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
SELECT
    r.id,
    r.status,
    r.flag_reason,
    rq.status as queue_status
FROM qa_reviews.reviews r
JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
WHERE r.response_queue_id = 609
ORDER BY r.version DESC
LIMIT 1;"
```

**Expected Result**:
- `r.status` = 'flagged'
- `rq.status` = 'flagged'
- `flag_reason` = "Test flag - needs clinical expert review"

---

## Test 4: Submit Review

**Action**:
1. Go to **Review History** → Find item #609
2. Click **Re-review**
3. Score all segments:
   - S1: 5
   - S2: 4
   - S3: 5
4. Add overall notes: "Test review - all segments clear and accurate"
5. Click **✅ Submit Review**

**Expected Behavior**:
- Success message appears
- Counter updates: "Submitted: 1"
- Item removed from your queue permanently

**Database Verification**:
```bash
# Verify submission
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
SELECT
    r.id,
    r.version,
    r.status,
    r.submitted_at,
    r.segment_scores,
    r.overall_notes,
    rq.status as queue_status
FROM qa_reviews.reviews r
JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
WHERE r.response_queue_id = 609
ORDER BY r.version DESC;"
```

**Expected Result**:
- Multiple rows (one per version)
- Latest version: `r.status` = 'submitted'
- Latest version: `submitted_at` is not NULL
- `rq.status` = 'submitted'
- All 3 segment scores present

---

## Test 5: Audit Trail

**Verification**: Check that all actions were logged

```bash
# View complete audit trail
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
SELECT
    action,
    previous_status,
    new_status,
    timestamp
FROM qa_reviews.review_audit_log
WHERE review_id IN (
    SELECT id FROM qa_reviews.reviews WHERE response_queue_id = 609
)
ORDER BY timestamp;"
```

**Expected Result**:
- Multiple entries showing:
  1. 'created' (draft creation)
  2. 'saved_draft' (draft save)
  3. 'flagged' (flag action)
  4. 'submitted' (final submission)

---

## Test 6: Session Counters

**Verification**: Check your session stats

```bash
# View session counters
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
SELECT
    session_start,
    reviews_completed,
    reviews_flagged,
    reviews_drafted
FROM qa_reviews.review_sessions
WHERE reviewer_id = (SELECT id FROM qa_reviews.reviewers WHERE email = 'stephen.dominick@gmail.com')
ORDER BY session_start DESC
LIMIT 1;"
```

**Expected Result**:
- `reviews_drafted` ≥ 1
- `reviews_flagged` ≥ 1
- `reviews_completed` ≥ 1

---

## Cleanup (After Testing)

Once you've verified everything works, clean up the test data:

```bash
# Delete test interaction and all related records
docker exec -e PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG rutabaga_backend_postgres_1 psql -h centerbeam.proxy.rlwy.net -p 26383 -U postgres -d railway -c "
-- Delete audit logs
DELETE FROM qa_reviews.review_audit_log
WHERE review_id IN (SELECT id FROM qa_reviews.reviews WHERE response_queue_id = 609);

-- Delete reviews
DELETE FROM qa_reviews.reviews WHERE response_queue_id = 609;

-- Delete from queue (test item #609 - safe to delete)
DELETE FROM qa_reviews.response_queue WHERE id = 609;

SELECT 'Test data cleaned up' as status;"
```

---

## Success Criteria

✅ **All tests pass if**:
1. Draft saves and appears in database with status='draft'
2. Flag creates new review version with status='flagged' and reason populated
3. Submit creates final version with status='submitted' and submitted_at timestamp
4. All actions logged in audit trail
5. Session counters increment correctly
6. UI shows correct success messages and counter updates

---

## Why This Approach?

**Real database testing** is superior because:
- ✅ Tests actual code paths (not mocks)
- ✅ Catches schema mismatches and constraint violations
- ✅ Verifies foreign keys and database triggers work
- ✅ Confirms data is persisted correctly
- ✅ Tests exactly what happens in production

**Mock testing** would give false confidence - the buttons might "work" but fail to actually write to the database.

---

## Quick Test Commands Summary

```bash
# After each action, run the corresponding verification query above

# Draft → Check reviews table for status='draft'
# Flag → Check reviews table for status='flagged' and flag_reason
# Submit → Check reviews table for status='submitted' and submitted_at
# Audit → Check audit_log for all actions
# Session → Check session counters
```
