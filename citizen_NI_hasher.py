import pyodbc
import bcrypt

# SQL Server connection details
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=INSPIRON15E\\SQLEXPRESS;"
    "DATABASE=PandemicResilienceDB;"
    "Trusted_Connection=yes;"
)

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Fetch all citizen IDs and their National Identifiers
    cursor.execute("SELECT PRS_ID, National_Identifier FROM Individual")
    citizen_nids = cursor.fetchall()

    updated_count = 0
    for prs_id, national_identifier in citizen_nids:
        if national_identifier:
            hashed_nid_bytes = bcrypt.hashpw(national_identifier.encode('utf-8'), bcrypt.gensalt())
            hashed_nid_string = hashed_nid_bytes.decode('utf-8')

            # Update the new Hashed_National_Identifier column
            cursor.execute("UPDATE Individual SET Hashed_National_Identifier = ? WHERE PRS_ID = ?", (hashed_nid_string, prs_id))
            updated_count += 1

    conn.commit()
    print(f"Successfully hashed and updated {updated_count} National Identifiers.")

except pyodbc.Error as ex:
    sqlstate = ex.args[0]
    print(f"Database error occurred: {sqlstate}")
    conn.rollback()

finally:
    if conn:
        conn.close()