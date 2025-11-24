"""
Production Update Service.

Handles updating production database tables when QA reviews are submitted.
Maps reviewed segments back to source database fields based on intent.
"""
from typing import Dict, Any, Optional
from flask import current_app
from sqlalchemy import text
from app import db
from app.models import ProductionUpdate, ResponseQueue


class ProductionUpdateService:
    """Service for updating production database from QA reviews."""

    # Intent to table mapping
    INTENT_TABLE_MAPPING = {
        'interaction': {
            'schema': 'public',
            'table': 'document_ddi_pairs',
            'lookup_fields': ['subject_drug', 'object_drug'],
            'segment_field_mapping': {
                'S1': 'effect_s1',         # Headline answer
                'S2': 'guidance',          # Clinical guidance
                'S3': 'effect_complete',   # Complete explanation
                'S4': None                 # Source attribution (not stored)
            }
        },
        'dosing': {
            'schema': 'content',
            'table': 'drug_dosing',
            'lookup_fields': ['drug_id', 'indication'],
            'segment_field_mapping': {
                'S1': 'dose_value',        # Dose headline
                'S2': 'frequency',         # Frequency/administration
                'S3': 'special_considerations',  # Additional context
                'S4': None                 # Source (not stored)
            }
        },
        # Future intents can be added here
    }

    @staticmethod
    def update_production(
        response_queue: ResponseQueue,
        segment_scores: Dict[str, Any],
        reviewer_id: int
    ) -> Optional[ProductionUpdate]:
        """
        Update production database based on QA review.

        Args:
            response_queue: The response that was reviewed
            segment_scores: Dict of {segment_id: {score, suggestion}}
            reviewer_id: Reviewer who submitted the review

        Returns:
            ProductionUpdate record or None if update failed
        """
        intent = response_queue.intent

        if intent not in ProductionUpdateService.INTENT_TABLE_MAPPING:
            current_app.logger.warning(
                f"No production update mapping for intent: {intent}"
            )
            return None

        mapping = ProductionUpdateService.INTENT_TABLE_MAPPING[intent]
        schema = mapping['schema']
        table = mapping['table']
        full_table_name = f"{schema}.{table}"

        try:
            # Build updated data from segment scores
            updated_fields = {}
            original_fields = {}

            # Get lookup values from slots
            lookup_values = {}
            for field in mapping['lookup_fields']:
                slot_key = field.replace('drug_id', 'drug').replace('subject_drug', 'drug_a').replace('object_drug', 'drug_b')
                lookup_values[field] = response_queue.slots.get(slot_key)

            # Fetch current record first
            current_record = ProductionUpdateService._fetch_current_record(
                full_table_name,
                mapping['lookup_fields'],
                lookup_values
            )

            if not current_record:
                current_app.logger.error(
                    f"Could not find production record for {intent} with lookup: {lookup_values}"
                )
                return None

            # Store original values
            for segment_id, db_field in mapping['segment_field_mapping'].items():
                if db_field and db_field in current_record:
                    original_fields[db_field] = current_record[db_field]

            # Build update values from reviewed segments
            for segment_id, seg_data in segment_scores.items():
                db_field = mapping['segment_field_mapping'].get(segment_id)

                if not db_field:
                    continue  # Skip unmapped segments (like S4)

                # Use suggestion if provided, otherwise use original segment text
                if seg_data.get('suggestion'):
                    updated_fields[db_field] = seg_data['suggestion']
                else:
                    # Find original segment text
                    original_segment = next(
                        (s for s in response_queue.segments if s['id'] == segment_id),
                        None
                    )
                    if original_segment:
                        updated_fields[db_field] = original_segment['text']

            # Only update if there are changes
            if not updated_fields:
                current_app.logger.info("No fields to update (no suggestions provided)")
                return None

            # Execute update
            success = ProductionUpdateService._execute_update(
                full_table_name,
                mapping['lookup_fields'],
                lookup_values,
                updated_fields
            )

            if not success:
                return None

            # Create production update log
            prod_update = ProductionUpdate(
                review_id=None,  # Will be set by caller
                intent=intent,
                target_table=full_table_name,
                target_record_id=None,  # Composite key, no single ID
                original_data=original_fields,
                updated_data=updated_fields,
                updated_by=reviewer_id
            )

            current_app.logger.info(
                f"Successfully updated {full_table_name} for {intent}",
                extra={'updated_fields': list(updated_fields.keys())}
            )

            return prod_update

        except Exception as e:
            current_app.logger.error(f"Error updating production database: {e}")
            return None

    @staticmethod
    def _fetch_current_record(
        table: str,
        lookup_fields: list,
        lookup_values: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch current record from production table.

        Args:
            table: Full table name (schema.table)
            lookup_fields: Fields to use for lookup
            lookup_values: Values for lookup fields

        Returns:
            Dict of current field values or None
        """
        # Build WHERE clause
        where_conditions = [f"{field} = :{field}" for field in lookup_fields]
        where_clause = " AND ".join(where_conditions)

        query = text(f"SELECT * FROM {table} WHERE {where_clause} LIMIT 1")

        try:
            result = db.session.execute(query, lookup_values)
            row = result.first()

            if row:
                return dict(row._mapping)
            return None

        except Exception as e:
            current_app.logger.error(f"Error fetching current record: {e}")
            return None

    @staticmethod
    def _execute_update(
        table: str,
        lookup_fields: list,
        lookup_values: dict,
        update_fields: dict
    ) -> bool:
        """
        Execute UPDATE statement on production table.

        Args:
            table: Full table name (schema.table)
            lookup_fields: Fields to use in WHERE clause
            lookup_values: Values for WHERE clause
            update_fields: Dict of {field: new_value}

        Returns:
            Success boolean
        """
        # Build SET clause
        set_clauses = [f"{field} = :{field}" for field in update_fields.keys()]
        set_clause = ", ".join(set_clauses)

        # Build WHERE clause
        where_conditions = [f"{field} = :lookup_{field}" for field in lookup_fields]
        where_clause = " AND ".join(where_conditions)

        query = text(f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {where_clause}
        """)

        # Combine parameters (prefix lookup values to avoid collision)
        params = {**update_fields}
        for field, value in lookup_values.items():
            params[f'lookup_{field}'] = value

        try:
            result = db.session.execute(query, params)
            db.session.commit()

            if result.rowcount > 0:
                current_app.logger.info(
                    f"Updated {result.rowcount} row(s) in {table}"
                )
                return True
            else:
                current_app.logger.warning(
                    f"No rows updated in {table}. Lookup: {lookup_values}"
                )
                return False

        except Exception as e:
            current_app.logger.error(f"Error executing update: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def get_source_data(response_queue: ResponseQueue) -> Optional[Dict[str, Any]]:
        """
        Get clinician-friendly FDA source data for display.

        Args:
            response_queue: The response queue item

        Returns:
            Dict with formatted FDA source data or None
        """
        intent = response_queue.intent

        # For interactions, show FDA DailyMed source quotes
        if intent == 'interaction':
            return ProductionUpdateService._get_fda_interaction_source(response_queue)

        # For other intents, fall back to raw database record
        if intent not in ProductionUpdateService.INTENT_TABLE_MAPPING:
            return None

        mapping = ProductionUpdateService.INTENT_TABLE_MAPPING[intent]

        # Build lookup values
        lookup_values = {}
        for field in mapping['lookup_fields']:
            slot_key = field.replace('drug_id', 'drug').replace('subject_drug', 'drug_a').replace('object_drug', 'drug_b')
            lookup_values[field] = response_queue.slots.get(slot_key)

        full_table_name = f"{mapping['schema']}.{mapping['table']}"

        return ProductionUpdateService._fetch_current_record(
            full_table_name,
            mapping['lookup_fields'],
            lookup_values
        )

    @staticmethod
    def _get_fda_interaction_source(response_queue: ResponseQueue) -> Optional[Dict[str, Any]]:
        """
        Get FDA DailyMed source quotes for drug-drug interactions.

        Returns:
            Dict with FDA source quotes and metadata
        """
        drug_a = response_queue.slots.get('drug_a')
        drug_b = response_queue.slots.get('drug_b')

        if not drug_a or not drug_b:
            return None

        # Fetch DDI record with FDA quotes
        query = text("""
            SELECT
                subject_drug,
                object_drug,
                set_id,
                version,
                quotes,
                effect,
                guidance,
                severity,
                mechanism,
                evidence,
                source_anchor
            FROM public.document_ddi_pairs
            WHERE subject_drug = :drug_a AND object_drug = :drug_b
            LIMIT 1
        """)

        try:
            result = db.session.execute(query, {'drug_a': drug_a, 'drug_b': drug_b})
            row = result.first()

            if not row:
                return None

            # Format for clinician review
            source_data = {
                'Drug Pair': f"{row.subject_drug} + {row.object_drug}",
                'FDA Set ID': row.set_id,
                'Version': row.version,
                'Severity': row.severity or 'Not specified',
                'Mechanism': row.mechanism or 'Not specified',
                'Evidence Level': row.evidence or 'Not specified',
            }

            # Add FDA source quotes if available
            if row.quotes:
                quotes_list = row.quotes if isinstance(row.quotes, list) else []
                if quotes_list:
                    source_data['FDA Source Quotes'] = [
                        {
                            'text': q.get('span_text', ''),
                            'section': q.get('section_key', 'Unknown'),
                            'position': f"Characters {q.get('start', '?')}-{q.get('end', '?')}"
                        }
                        for q in quotes_list
                    ]

            # Add current response content for reference
            source_data['_separator_1'] = '--- Current Response Content ---'
            source_data['Effect (S1)'] = row.effect or ''
            source_data['Guidance (S2)'] = row.guidance or ''

            return source_data

        except Exception as e:
            current_app.logger.error(f"Error fetching FDA source data: {e}")
            return None
