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

    # Fetch all government official IDs and their current plain-text passwords
    cursor.execute("SELECT Official_Id, Password FROM Government_Official")
    gov_official_passwords = cursor.fetchall()

    updated_count = 0
    for official_id, plain_password in gov_official_passwords:
        if plain_password:  # Only hash if there's a password present
            hashed_password_bytes = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
            hashed_password_string = hashed_password_bytes.decode('utf-8')

            # Update the Password column with the hashed password
            cursor.execute("UPDATE Government_Official SET Password = ? WHERE Official_Id = ?", (hashed_password_string, official_id))
            updated_count += 1

    conn.commit()
    print(f"Successfully hashed and updated {updated_count} government official passwords.")

except pyodbc.Error as ex:
    sqlstate = ex.args[0]
    print(f"Database error occurred: {sqlstate}")
    conn.rollback()

finally:
    if conn:
        conn.close()