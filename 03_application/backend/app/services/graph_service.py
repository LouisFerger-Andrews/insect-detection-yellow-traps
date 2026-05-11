from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from neo4j import GraphDatabase

from app.core.config import get_settings


class GraphService:
    def __init__(self) -> None:
        settings = get_settings()
        self.driver = None
        try:
            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            driver.verify_connectivity()
            self.driver = driver
        except Exception:
            self.driver = None

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def initialize(self) -> None:
        if self.driver is None:
            return
        with self.driver.session() as session:
            session.run('CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE')
            session.run('CREATE CONSTRAINT field_id_unique IF NOT EXISTS FOR (f:Field) REQUIRE f.id IS UNIQUE')

    def ensure_user_node(self, user_id: int, email: str, full_name: str) -> None:
        if self.driver is None:
            return
        query = (
            'MERGE (u:User {user_id: $user_id}) '
            'SET u.email = $email, u.full_name = $full_name'
        )
        with self.driver.session() as session:
            session.run(query, user_id=user_id, email=email, full_name=full_name)

    def create_field(self, user_id: int, field_id: str, name: str, location: str) -> Dict[str, Any]:
        if self.driver is None:
            return {'id': field_id, 'name': name, 'location': location, 'owner_user_id': user_id}
        query = (
            'MATCH (u:User {user_id: $user_id}) '
            'CREATE (f:Field {id: $field_id, name: $name, location: $location}) '
            'CREATE (u)-[:OWNS]->(f) '
            'RETURN f.id AS id, f.name AS name, f.location AS location, u.user_id AS owner_user_id'
        )
        with self.driver.session() as session:
            result = session.run(query, user_id=user_id, field_id=field_id, name=name, location=location).single()
            return dict(result) if result else {}

    def list_fields_for_user(self, user_id: int, is_admin: bool = False) -> List[Dict[str, Any]]:
        if self.driver is None:
            return []
        if is_admin:
            query = (
                'MATCH (u:User)-[:OWNS]->(f:Field) '
                'RETURN f.id AS id, f.name AS name, f.location AS location, u.user_id AS owner_user_id '
                'ORDER BY f.name ASC'
            )
            params = {}
        else:
            query = (
                'MATCH (u:User {user_id: $user_id})-[:OWNS]->(f:Field) '
                'RETURN f.id AS id, f.name AS name, f.location AS location, u.user_id AS owner_user_id '
                'ORDER BY f.name ASC'
            )
            params = {'user_id': user_id}

        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def link_upload_to_field(self, field_id: str, upload_id: int, capture_date: date, detection_count: int) -> None:
        if self.driver is None:
            return
        query = (
            'MATCH (f:Field {id: $field_id}) '
            'MERGE (u:Upload {upload_id: $upload_id}) '
            'SET u.capture_date = $capture_date, u.detection_count = $detection_count '
            'MERGE (f)-[:HAS_UPLOAD]->(u)'
        )
        with self.driver.session() as session:
            session.run(
                query,
                field_id=field_id,
                upload_id=upload_id,
                capture_date=capture_date.isoformat(),
                detection_count=detection_count,
            )

    def seed_example_field(self, user_id: int) -> None:
        if self.driver is None:
            return
        query = (
            'MATCH (u:User {user_id: $user_id}) '
            'MERGE (f:Field {id: $field_id}) '
            'SET f.name = $name, f.location = $location '
            'MERGE (u)-[:OWNS]->(f)'
        )
        with self.driver.session() as session:
            session.run(
                query,
                user_id=user_id,
                field_id='field-demo-blueberry-01',
                name='Demo Blueberry Field',
                location='North Block',
            )
