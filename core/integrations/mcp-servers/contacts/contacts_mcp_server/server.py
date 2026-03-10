"""Minimal contacts lookup MCP server."""
import logging
import os
import re
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("contacts")

# Constants
ADDRESSBOOK_BASE = Path.home() / "Library/Application Support/AddressBook"
CONTACT_ENTITY_TYPE = 22  # Apple's internal type for contact records
MIN_PHONE_DIGITS = 7  # Minimum to consider a phone number


def get_contact_databases() -> list[Path]:
    """Find all AddressBook databases (main + sources)."""
    dbs = []

    # Check main database
    main_db = ADDRESSBOOK_BASE / "AddressBook-v22.abcddb"
    if main_db.exists():
        dbs.append(main_db)

    # Check source databases (iCloud, Gmail, etc.)
    sources_dir = ADDRESSBOOK_BASE / "Sources"
    if sources_dir.exists():
        for source in sources_dir.iterdir():
            if source.is_dir():
                db = source / "AddressBook-v22.abcddb"
                if db.exists():
                    dbs.append(db)

    return dbs


def normalize_phone(phone: str) -> str:
    """Strip everything except digits."""
    return re.sub(r"\D", "", phone)


@mcp.tool()
def lookup_phone(phone: str) -> str:
    """
    Look up a contact name by phone number.

    Args:
        phone: Phone number in any format (e.g., "+1 510-847-4625")

    Returns:
        Contact name if found, or "Unknown" if not found.
    """
    digits = normalize_phone(phone)
    if len(digits) < MIN_PHONE_DIGITS:
        return f"Invalid phone: {phone}"

    # Use last 10 digits for matching (handles country code variations)
    search_digits = digits[-10:]

    databases = get_contact_databases()
    if not databases:
        return "No AddressBook databases found"

    for db_path in databases:
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                cursor = conn.execute(
                    """
                    SELECT c.ZFIRSTNAME, c.ZLASTNAME, c.ZORGANIZATION
                    FROM ZABCDRECORD c
                    JOIN ZABCDPHONENUMBER p ON p.ZOWNER = c.Z_PK
                    WHERE c.Z_ENT = ?
                      AND REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                          p.ZFULLNUMBER, ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE ?
                    LIMIT 1
                    """,
                    (CONTACT_ENTITY_TYPE, f"%{search_digits}%"),
                )
                row = cursor.fetchone()

                if row:
                    first, last, org = row
                    name = " ".join(p for p in [first, last] if p) or org or "Unknown"
                    return name

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning(f"Database locked: {db_path}")
                continue  # Try next database
            logger.error(f"Database error for {db_path}: {e}")
            continue
        except sqlite3.DatabaseError as e:
            logger.error(f"Failed to read {db_path}: {e}")
            continue

    return "Unknown"


@mcp.tool()
def lookup_name(name: str) -> list[dict]:
    """
    Search contacts by name and return matching phone numbers and emails.

    Args:
        name: Name to search for (first, last, or full name)

    Returns:
        List of matches with name, phone numbers, and email addresses.
    """
    if not name or len(name.strip()) < 2:
        return []

    search_term = f"%{name.strip()}%"
    databases = get_contact_databases()
    if not databases:
        return []

    # Collect all contact info by name
    contacts = {}  # name -> {"phones": set(), "emails": set()}

    for db_path in databases:
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                # Query phones
                cursor = conn.execute(
                    """
                    SELECT c.ZFIRSTNAME, c.ZLASTNAME, c.ZORGANIZATION, p.ZFULLNUMBER
                    FROM ZABCDRECORD c
                    JOIN ZABCDPHONENUMBER p ON p.ZOWNER = c.Z_PK
                    WHERE c.Z_ENT = ?
                      AND (
                        c.ZFIRSTNAME LIKE ? COLLATE NOCASE
                        OR c.ZLASTNAME LIKE ? COLLATE NOCASE
                        OR c.ZORGANIZATION LIKE ? COLLATE NOCASE
                        OR (c.ZFIRSTNAME || ' ' || c.ZLASTNAME) LIKE ? COLLATE NOCASE
                      )
                    """,
                    (CONTACT_ENTITY_TYPE, search_term, search_term, search_term, search_term),
                )

                for row in cursor.fetchall():
                    first, last, org, phone = row
                    display_name = " ".join(p for p in [first, last] if p) or org or "Unknown"
                    if display_name not in contacts:
                        contacts[display_name] = {"phones": set(), "emails": set()}
                    if phone:
                        contacts[display_name]["phones"].add(phone)

                # Query emails
                cursor = conn.execute(
                    """
                    SELECT c.ZFIRSTNAME, c.ZLASTNAME, c.ZORGANIZATION, e.ZADDRESS
                    FROM ZABCDRECORD c
                    JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = c.Z_PK
                    WHERE c.Z_ENT = ?
                      AND (
                        c.ZFIRSTNAME LIKE ? COLLATE NOCASE
                        OR c.ZLASTNAME LIKE ? COLLATE NOCASE
                        OR c.ZORGANIZATION LIKE ? COLLATE NOCASE
                        OR (c.ZFIRSTNAME || ' ' || c.ZLASTNAME) LIKE ? COLLATE NOCASE
                      )
                    """,
                    (CONTACT_ENTITY_TYPE, search_term, search_term, search_term, search_term),
                )

                for row in cursor.fetchall():
                    first, last, org, email = row
                    display_name = " ".join(p for p in [first, last] if p) or org or "Unknown"
                    if display_name not in contacts:
                        contacts[display_name] = {"phones": set(), "emails": set()}
                    if email:
                        contacts[display_name]["emails"].add(email.lower())

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning(f"Database locked: {db_path}")
                continue
            logger.error(f"Database error for {db_path}: {e}")
            continue
        except sqlite3.DatabaseError as e:
            logger.error(f"Failed to read {db_path}: {e}")
            continue

    # Convert to result list
    results = []
    for display_name, info in contacts.items():
        result = {"name": display_name}
        if info["phones"]:
            result["phone"] = list(info["phones"])[0]  # Primary phone
            if len(info["phones"]) > 1:
                result["phones"] = list(info["phones"])
        if info["emails"]:
            result["email"] = list(info["emails"])[0]  # Primary email
            if len(info["emails"]) > 1:
                result["emails"] = list(info["emails"])
        results.append(result)

    return results


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
