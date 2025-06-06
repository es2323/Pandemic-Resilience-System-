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

    # Fetch all merchant IDs and their current plain-text passwords
    cursor.execute("SELECT Merchant_Id, Password FROM Merchant")
    merchant_passwords = cursor.fetchall()

    updated_count = 0
    for merchant_id, plain_password in merchant_passwords:
        if plain_password:  # Only hash if there's a password present
            hashed_password_bytes = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
            hashed_password_string = hashed_password_bytes.decode('utf-8')

            # Update the Password column with the hashed password
            cursor.execute("UPDATE Merchant SET Password = ? WHERE Merchant_Id = ?", (hashed_password_string, merchant_id))
            updated_count += 1

    conn.commit()
    print(f"Successfully hashed and updated {updated_count} merchant passwords.")

except pyodbc.Error as ex:
    sqlstate = ex.args[0]
    print(f"Database error occurred: {sqlstate}")
    conn.rollback()

finally:
    if conn:
        conn.close()