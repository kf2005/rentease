"""Admin bootstrap and demo seed data."""
import logging

from flask import current_app

from .auth import hash_password
from .db import commit, execute, query

log = logging.getLogger("rentease.bootstrap")

DEMO_PASSWORD = "Password123!"


def ensure_admin():
    """Create the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if none exists."""
    cfg = current_app.config["RENTEASE"]
    if not (cfg.ADMIN_EMAIL and cfg.ADMIN_PASSWORD):
        return
    email = cfg.ADMIN_EMAIL.strip().lower()
    if query("SELECT id FROM users WHERE email = %s", (email,), one=True):
        return
    execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
        (cfg.ADMIN_NAME, email, hash_password(cfg.ADMIN_PASSWORD)),
    )
    commit()
    log.info("Created admin account %s", email)


DEMO_USERS = [
    ("Ahmed Raza", "ahmed.owner@rentease.pk", "owner", "0300-1234567"),
    ("Sana Malik", "sana.owner@rentease.pk", "owner", "0321-7654321"),
    ("Bilal Khan", "bilal.owner@rentease.pk", "owner", "0333-1122334"),
    ("Ayesha Tariq", "ayesha.tenant@rentease.pk", "tenant", "0345-9988776"),
    ("Usman Ali", "usman.tenant@rentease.pk", "tenant", "0312-5566778"),
    ("Demo Admin", "admin@rentease.pk", "admin", None),
]

# (owner_index, title, type, city, area, rent, beds, baths, sqft, furnished, status, description)
DEMO_PROPERTIES = [
    (0, "Spacious 3-bed upper portion near F-10 Markaz", "portion", "Islamabad", "F-10/2", 120000, 3, 3, 1800, False, "approved",
     "Bright upper portion with separate entrance, gas and electricity sub-meters, and a covered car porch. Walking distance to F-10 Markaz and Fatima Jinnah Park."),
    (0, "Furnished 1-bed flat in E-11", "flat", "Islamabad", "E-11/3", 75000, 1, 1, 650, True, "approved",
     "Fully furnished apartment on the 4th floor with lift, backup generator and 24/7 security. Ideal for working professionals."),
    (1, "Family house with lawn in G-11", "house", "Islamabad", "G-11/1", 210000, 5, 4, 3200, False, "approved",
     "Double-storey house on a 10 marla plot with front lawn, servant quarter and two kitchens. Close to schools and the G-11 Markaz."),
    (1, "Studio apartment in Bahria Town Phase 7", "studio", "Rawalpindi", "Bahria Town Phase 7", 45000, 0, 1, 450, True, "approved",
     "Compact furnished studio with kitchenette, close to Spring North commercial. Maintenance included in rent."),
    (2, "2-bed flat in DHA Phase 2", "flat", "Islamabad", "DHA Phase 2", 95000, 2, 2, 1100, False, "approved",
     "Corner apartment with balcony, park view and dedicated parking. Gated community with mosque and play area."),
    (2, "Room for students near NUST", "room", "Islamabad", "H-12", 22000, 1, 1, 200, True, "approved",
     "Furnished room with attached bath in a shared house. Wi-Fi, electricity and cleaning included. Female students preferred."),
    (0, "Luxury 4-bed house in DHA Phase 6", "house", "Lahore", "DHA Phase 6", 350000, 4, 5, 4500, True, "approved",
     "Modern 1 kanal house with basement, home theatre, solar panels and a landscaped garden. Corporate lease preferred."),
    (1, "Ground portion in Gulberg III", "portion", "Lahore", "Gulberg III", 110000, 3, 2, 1600, False, "approved",
     "Ground floor portion with separate gate, close to MM Alam Road. Suitable for small families."),
    (2, "Sea-view 3-bed apartment in Clifton", "flat", "Karachi", "Clifton Block 2", 180000, 3, 3, 2000, False, "approved",
     "High-rise apartment with sea view, gym, swimming pool and standby generator. Two reserved parking spaces."),
    (0, "2-bed flat in Gulshan-e-Iqbal", "flat", "Karachi", "Gulshan-e-Iqbal Block 13", 60000, 2, 2, 950, False, "approved",
     "Well-maintained apartment near Maskan Chowrangi with water supply from the main line and lift access."),
    (1, "Upper portion in Satellite Town", "portion", "Rawalpindi", "Satellite Town", 55000, 2, 2, 1200, False, "approved",
     "Upper portion near Commercial Market with roof access and separate meters."),
    (2, "Furnished 2-bed in Bahria Enclave", "flat", "Islamabad", "Bahria Enclave", 85000, 2, 2, 1050, True, "approved",
     "Furnished apartment with mountain views, close to the Bahria Enclave main boulevard."),
    (0, "New 5 marla house in Johar Town", "house", "Lahore", "Johar Town", 90000, 3, 3, 1350, False, "pending",
     "Brand new house near Emporium Mall, never lived in. Awaiting admin approval."),
    (1, "Room in shared flat, Blue Area", "room", "Islamabad", "Blue Area", 30000, 1, 1, 180, True, "pending",
     "Room in a shared executive flat in Blue Area. Awaiting admin approval."),
]


def seed_demo_data():
    """Insert demo users, listings and inquiries. Skips if already seeded."""
    if query("SELECT id FROM users WHERE email = %s", (DEMO_USERS[0][1],), one=True):
        return False
    password_hash = hash_password(DEMO_PASSWORD)
    user_ids = []
    for name, email, role, phone in DEMO_USERS:
        if query("SELECT id FROM users WHERE email = %s", (email,), one=True):
            user_ids.append(query("SELECT id FROM users WHERE email = %s", (email,), one=True)["id"])
            continue
        row = execute(
            "INSERT INTO users (name, email, password_hash, role, phone) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, email, password_hash, role, phone),
            returning=True,
        )
        user_ids.append(row["id"])

    property_ids = []
    for (owner, title, ptype, city, area, rent, beds, baths, sqft, furnished, status, desc) in DEMO_PROPERTIES:
        row = execute(
            """INSERT INTO properties (owner_id, title, description, property_type, city, area, rent,
                                       bedrooms, bathrooms, size_sqft, furnished, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (user_ids[owner], title, desc, ptype, city, area, rent, beds, baths, sqft, furnished, status),
            returning=True,
        )
        property_ids.append(row["id"])

    tenant_a, tenant_b = user_ids[3], user_ids[4]
    execute(
        "INSERT INTO inquiries (property_id, tenant_id, message, contact_phone) VALUES (%s, %s, %s, %s)",
        (property_ids[0], tenant_a, "Assalam o Alaikum, is the portion still available from next month? Can I visit on Saturday?", "0345-9988776"),
    )
    execute(
        """INSERT INTO inquiries (property_id, tenant_id, message, contact_phone, status, reply, replied_at)
           VALUES (%s, %s, %s, %s, 'replied', %s, CURRENT_TIMESTAMP)""",
        (property_ids[1], tenant_b, "Is the rent negotiable for a 1-year contract?", "0312-5566778",
         "Yes, we can do 70,000 for a 12-month agreement. Please call to arrange a visit."),
    )
    commit()
    log.info("Seeded demo data: %d users, %d properties", len(user_ids), len(property_ids))
    return True
