#!/bin/bash
# Quick verification script for QA workflow testing

PGPASSWORD=wrUUIZSBwuHRHKCuQvUmvkvQUJVeWhCG
HOST=centerbeam.proxy.rlwy.net
PORT=26383
USER=postgres
DB=railway
TEST_ITEM_ID=609  # Clearly marked test item - safe to delete

echo "===================================="
echo "QA Workflow Test Verification"
echo "===================================="
echo ""

case "$1" in
    draft)
        echo "📝 Checking DRAFT status..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            r.id as review_id,
            r.status,
            r.version,
            rq.status as queue_status,
            jsonb_pretty(r.segment_scores) as scores
        FROM qa_reviews.reviews r
        JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
        WHERE r.response_queue_id = $TEST_ITEM_ID
        ORDER BY r.version DESC;"
        ;;

    flag)
        echo "🚩 Checking FLAG status..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            r.id as review_id,
            r.status,
            r.flag_reason,
            r.version,
            rq.status as queue_status
        FROM qa_reviews.reviews r
        JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
        WHERE r.response_queue_id = $TEST_ITEM_ID
        ORDER BY r.version DESC;"
        ;;

    submit)
        echo "✅ Checking SUBMITTED status..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            r.id as review_id,
            r.status,
            r.version,
            r.submitted_at,
            r.overall_notes,
            rq.status as queue_status
        FROM qa_reviews.reviews r
        JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
        WHERE r.response_queue_id = $TEST_ITEM_ID
        ORDER BY r.version DESC;"
        ;;

    audit)
        echo "📋 Checking AUDIT TRAIL..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            action,
            previous_status,
            new_status,
            timestamp
        FROM qa_reviews.review_audit_log
        WHERE review_id IN (
            SELECT id FROM qa_reviews.reviews WHERE response_queue_id = $TEST_ITEM_ID
        )
        ORDER BY timestamp;"
        ;;

    session)
        echo "📊 Checking SESSION COUNTERS..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            session_start,
            reviews_completed,
            reviews_flagged,
            reviews_drafted,
            reviews_skipped
        FROM qa_reviews.review_sessions
        WHERE reviewer_id = (SELECT id FROM qa_reviews.reviewers WHERE email = 'stephen.dominick@gmail.com')
        ORDER BY session_start DESC
        LIMIT 1;"
        ;;

    all)
        echo "🔍 Checking ALL REVIEWS for test item..."
        docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
        SELECT
            r.id,
            r.version,
            r.status,
            r.created_at,
            r.submitted_at,
            rq.status as queue_status
        FROM qa_reviews.reviews r
        JOIN qa_reviews.response_queue rq ON r.response_queue_id = rq.id
        WHERE r.response_queue_id = $TEST_ITEM_ID
        ORDER BY r.version;"
        ;;

    cleanup)
        echo "🧹 CLEANING UP test data..."
        read -p "Are you sure you want to delete test item #$TEST_ITEM_ID? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            docker exec -e PGPASSWORD=$PGPASSWORD rutabaga_backend_postgres_1 psql -h $HOST -p $PORT -U $USER -d $DB -c "
            -- Delete audit logs
            DELETE FROM qa_reviews.review_audit_log
            WHERE review_id IN (SELECT id FROM qa_reviews.reviews WHERE response_queue_id = $TEST_ITEM_ID);

            -- Delete reviews
            DELETE FROM qa_reviews.reviews WHERE response_queue_id = $TEST_ITEM_ID;

            -- Delete from queue
            DELETE FROM qa_reviews.response_queue WHERE id = $TEST_ITEM_ID;

            SELECT 'Test data cleaned up successfully' as status;"
            echo "✅ Cleanup complete!"
        else
            echo "❌ Cleanup cancelled"
        fi
        ;;

    *)
        echo "Usage: ./verify_test.sh [command]"
        echo ""
        echo "Commands:"
        echo "  draft    - Check if draft was saved correctly"
        echo "  flag     - Check if item was flagged correctly"
        echo "  submit   - Check if review was submitted correctly"
        echo "  audit    - View complete audit trail"
        echo "  session  - View session counters"
        echo "  all      - View all review versions"
        echo "  cleanup  - Delete test data"
        echo ""
        echo "Example: ./verify_test.sh draft"
        ;;
esac
