"""Database Seeder for BhuRaksha Property Document Verification System.

Populates real reference areas, reference cadastral records, PostGIS parcels,
role-based test users (Admin, Area Officer, Citizens), and reference registry records.
Does NOT create pre-existing uploaded citizen cases to ensure clean slate for real testing.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from geoalchemy2.elements import WKTElement

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.area import Area
from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.enums import UserRole
from app.models.user import User
from app.models.reference_property import ReferenceProperty


async def seed_database() -> None:
    """Seed the database with real reference data, users, areas, and cadastral records."""
    print("🌱 Starting database seeding...")

    async with async_session_factory() as db:
        # 1. Seed Users
        users_data = [
            {
                "email": "admin@example.com",
                "password": "Admin@12345678!",
                "full_name": "System Administrator",
                "role": UserRole.SUPER_ADMIN,
                "phone": "+919876543210",
            },
            {
                "email": "officer@example.com",
                "password": "Officer@12345678!",
                "full_name": "Officer Ramesh Ghosh",
                "role": UserRole.AREA_OFFICER,
                "phone": "+919876543211",
            },
            {
                "email": "ramesh@example.com",
                "password": "Officer@12345678!",
                "full_name": "Officer Ramesh Ghosh",
                "role": UserRole.AREA_OFFICER,
                "phone": "+919876543211",
            },
            {
                "email": "citizen@example.com",
                "password": "Citizen@12345678!",
                "full_name": "Citizen User",
                "role": UserRole.CIVILIAN,
                "phone": "+919876543212",
            },
            {
                "email": "anita@example.com",
                "password": "Citizen@12345678!",
                "full_name": "Anita Mondal",
                "role": UserRole.CIVILIAN,
                "phone": "+919876543213",
            },
        ]

        users_by_email: dict[str, User] = {}
        for u_info in users_data:
            existing = (
                await db.execute(select(User).where(User.email == u_info["email"]))
            ).scalar_one_or_none()
            if not existing:
                user = User(
                    email=u_info["email"],
                    password_hash=hash_password(u_info["password"]),
                    full_name=u_info["full_name"],
                    role=u_info["role"],
                    phone=u_info["phone"],
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
                await db.flush()
                users_by_email[u_info["email"]] = user
                print(f"  ✓ Created user: {user.email} ({user.role.value})")
            else:
                existing.role = u_info["role"]
                existing.full_name = u_info["full_name"]
                existing.password_hash = hash_password(u_info["password"])
                existing.is_active = True
                existing.is_verified = True
                await db.flush()
                users_by_email[u_info["email"]] = existing
                print(f"  ✓ Synced user: {existing.email} ({existing.role.value})")

        # 2. Seed Areas
        areas_data = [
            {
                "name": "Hatgacha District",
                "code": "HG-01",
                "description": "Hatgacha Revenue Jurisdiction & Cadastral Block",
            },
            {
                "name": "Bakultala Sub-division",
                "code": "BK-02",
                "description": "Bakultala Tehsil & Settlement Zone",
            },
            {
                "name": "Rautara Zone",
                "code": "RT-03",
                "description": "Rautara Cadastral Survey Division",
            },
        ]

        areas_by_code: dict[str, Area] = {}
        for a_info in areas_data:
            existing = (
                await db.execute(select(Area).where(Area.code == a_info["code"]))
            ).scalar_one_or_none()
            if not existing:
                area = Area(
                    name=a_info["name"],
                    code=a_info["code"],
                    description=a_info["description"],
                    geometry=WKTElement("POLYGON((88.35 22.50, 88.40 22.50, 88.40 22.55, 88.35 22.55, 88.35 22.50))", srid=4326),
                    is_active=True,
                )
                db.add(area)
                await db.flush()
                areas_by_code[a_info["code"]] = area
                print(f"  ✓ Created area: {area.name} ({area.code})")
            else:
                areas_by_code[a_info["code"]] = existing
                print(f"  - Area exists: {existing.name} ({existing.code})")

        # 3. Assign Officers to Hatgacha and Bakultala
        for off_email in ["officer@example.com", "ramesh@example.com"]:
            officer = users_by_email[off_email]
            for code in ["HG-01", "BK-02"]:
                area = areas_by_code[code]
                existing_assignment = (
                    await db.execute(
                        select(AreaOfficerAssignment).where(
                            AreaOfficerAssignment.officer_id == officer.id,
                            AreaOfficerAssignment.area_id == area.id,
                        )
                    )
                ).scalar_one_or_none()
                if not existing_assignment:
                    assignment = AreaOfficerAssignment(
                        officer_id=officer.id,
                        area_id=area.id,
                    )
                    db.add(assignment)
                    await db.flush()
                    print(f"  ✓ Assigned {off_email} to: {area.name}")

        # 4. Seed Reference Properties (Authoritative Registry Records)
        ref_props = [
            {
                "source_id": "WB_LAND_REGISTRY",
                "source_record_id": "REC-HG-142",
                "survey_number": "142/3-B",
                "village": "Hatgacha",
                "district": "North 24 Parganas",
                "property_area": 1.05,
                "area_unit": "acre",
            },
            {
                "source_id": "WB_LAND_REGISTRY",
                "source_record_id": "REC-BK-88",
                "survey_number": "88/1",
                "village": "Bakultala",
                "district": "South 24 Parganas",
                "property_area": 0.85,
                "area_unit": "acre",
            },
        ]
        for rp_info in ref_props:
            existing = (
                await db.execute(
                    select(ReferenceProperty).where(
                        ReferenceProperty.survey_number == rp_info["survey_number"],
                        ReferenceProperty.source_record_id == rp_info["source_record_id"],
                    )
                )
            ).scalar_one_or_none()
            if not existing:
                rp = ReferenceProperty(**rp_info)
                db.add(rp)
                await db.flush()
                print(f"  ✓ Created reference property: {rp.village} Plot {rp.survey_number}")

        await db.commit()
        print("✅ Database seeding completed successfully (Clean slate for citizen uploads)!")


if __name__ == "__main__":
    asyncio.run(seed_database())
