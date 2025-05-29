from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pyodbc
from datetime import date
from datetime import datetime, timedelta
from pymongo import MongoClient
import bcrypt


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# SQL Server connection
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=INSPIRON15E\\SQLEXPRESS;"
    "DATABASE=PandemicResilienceDB;"
    "Trusted_Connection=yes;"
)

# ====== CONFIGURATION ======
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "PRS"
MONGO_COLLECTION = "Access_Logs"

# ====== CONNECT TO MONGODB ======
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]
access_logs = mongo_db[MONGO_COLLECTION]

def log_access(user_type, action_performed, affected_entity=None, entity_id=None):
    """Logs an access event to MongoDB."""
    log_entry = {
        "User_Type": user_type.upper(),
        "Action_Performed": action_performed,
        "Timestamp": datetime.utcnow(),
        "IP_Address": request.remote_addr,
        "Affected_Entity": affected_entity,
        "Entity_Id": entity_id,
        "Government_Official_Id": None,
        "Merchant_Id": None,
       "Retention_Expiry_Date": datetime.utcnow() + timedelta(days=90) # Example retention
    }

    if user_type.upper() == 'GOV':
        log_entry["Government_Official_Id"] = current_user.id
    elif user_type.upper() == 'MERCHANT':
        log_entry["Merchant_Id"] = current_user.id

    try:
        access_logs.insert_one(log_entry)
        print(f"✅ Logged '{action_performed}' by {user_type} (ID: {current_user.id if current_user.is_authenticated else 'N/A'})")
    except Exception as e:
        print(f"❌ Failed to log '{action_performed}': {e}")

# Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class
class User(UserMixin):
    def __init__(self, id, email, user_type):
        self.id = id
        self.email = email
        self.user_type = user_type  # gov, merchant, or public

# Load user session
@login_manager.user_loader
def load_user(user_id):
    cursor = conn.cursor() 
    # Try government official
    try:
        cursor.execute("SELECT Official_Id, Email FROM Government_Official WHERE Official_Id = ?", (user_id,))
        gov_user = cursor.fetchone()
        if gov_user:
            return User(id=gov_user[0], email=gov_user[1], user_type='gov')

        # Try merchant
        cursor.execute("SELECT Merchant_Id, Email FROM Merchant WHERE Merchant_Id = ?", (user_id,))
        merch_user = cursor.fetchone()
        if merch_user:
            return User(id=merch_user[0], email=merch_user[1], user_type='merchant')

        # Try public individual
        cursor.execute("SELECT PRS_ID, Email FROM Individual WHERE PRS_ID = ?", (user_id,))
        public_user = cursor.fetchone()
        if public_user:
            return User(id=public_user[0], email=public_user[1], user_type='public')

        return None
    finally:
        cursor.close() 

from flask_login import login_user
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        cursor = None  # Initialize cursor variable
        try:
            cursor = conn.cursor()
            
            # 1. Government login
            cursor.execute("SELECT Official_Id, Email, Password FROM Government_Official WHERE Email = ?", (email,))
            row = cursor.fetchone()
            if row and row[2]:
                hashed_password_from_db = row[2].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password_from_db):
                    user = User(id=row[0], email=row[1], user_type='gov')
                    login_user(user)
                    log_access('gov', 'Logged In')
                    flash("Government login successful!", "success")
                    return redirect(url_for('gov_dashboard'))

            # 2. Merchant login
            cursor.execute("SELECT Merchant_Id, Email, Password FROM Merchant WHERE Email = ?", (email,))
            merch_row = cursor.fetchone()
            if merch_row and merch_row[2]:
                hashed_password_from_db = merch_row[2].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password_from_db):
                    user = User(id=merch_row[0], email=merch_row[1], user_type='merchant')
                    login_user(user)
                    log_access('merchant', 'Logged In')
                    flash("Merchant login successful!", "success")
                    return redirect(url_for('merchant_dashboard'))

            # 3. Public user login
            cursor.execute("SELECT PRS_ID, Email, Password FROM Individual WHERE Email = ?", (email,))
            pub_row = cursor.fetchone()
            if pub_row and pub_row[2]:
                hashed_password_from_db = pub_row[2].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), hashed_password_from_db):
                    user = User(id=pub_row[0], email=pub_row[1], user_type='public')
                    login_user(user)
                    flash("Public login successful!", "success")
                    return redirect(url_for('dashboard'))

            flash("Invalid email or password.", "danger")
        except Exception as e:
            flash("An error occurred during login.", "danger")
            app.logger.error(f"Login error: {str(e)}")
        finally:
            if cursor:  # Only close if cursor exists
                cursor.close()
    
    return render_template("login.html")


# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ----------------------
# Public Dashboard Routes
# ----------------------

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type != 'public':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/dashboard/identity')
@login_required
def view_prs_info():
    if current_user.user_type != 'public':
        return redirect(url_for('login'))

    cursor = conn.cursor()  # Add this line
    try:
        cursor.execute("""
            SELECT PRS_Id, National_Identifier, Name, Date_of_Birth, Email,
                   Emergency_Contact_Name, Emergency_Contact_Phone
            FROM Individual WHERE PRS_Id = ?
        """, (current_user.id,))
        row = cursor.fetchone()
        prs_info = dict(zip(["PRS_Id", "National_Identifier", "Name", "Date_of_Birth", "Email",
                             "Emergency_Contact_Name", "Emergency_Contact_Phone"], row))
        return render_template("identity.html", prs_info=prs_info)
    finally:
        cursor.close()  # Ensure cursor is closed

@app.route('/dashboard/supplies')
@login_required
def view_supplies():
    print("DEBUG: Supplies route accessed")  # Check console for this
    if current_user.user_type != 'public':
        flash("Access denied. Public account required.", "danger")
        return redirect(url_for('login'))

    cursor = conn.cursor()
    try:
        # Debug store query
        cursor.execute("SELECT COUNT(*) FROM Store WHERE Operational_Status = 'Open'")
        store_count = cursor.fetchone()[0]
        print(f"DEBUG: Found {store_count} open stores")
        
        cursor.execute("""
            SELECT Store_Id, Address, Store_Type, Operational_Hours 
            FROM Store
            WHERE Operational_Status = 'Open'
            ORDER BY Store_Type, Address
        """)
        stores = [dict(zip(["Store_Id", "Address", "Store_Type", "Operational_Hours"], row)) 
                 for row in cursor.fetchall()]
        print(f"DEBUG: Stores data: {stores}")

        # Debug items query
        cursor.execute("SELECT COUNT(*) FROM Critical_Item")
        item_count = cursor.fetchone()[0]
        print(f"DEBUG: Found {item_count} critical items")
        
        cursor.execute("""
            SELECT Name, Category, Daily_Limit_Per_Person, Weekly_Limit_Per_Person 
            FROM Critical_Item
            ORDER BY Category, Name
        """)
        items = [dict(zip(["Name", "Category", "Daily_Limit", "Weekly_Limit"], row)) 
                for row in cursor.fetchall()]
        print(f"DEBUG: Items data: {items}")

        return render_template("supplies.html", 
                            stores=stores, 
                            items=items,
                            current_date=datetime.now().strftime('%Y-%m-%d'))

    except pyodbc.Error as e:
        print(f"ERROR: Database error: {str(e)}")
        flash("Error retrieving supplies information. Please try again later.", "danger")
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()

@app.route('/dashboard/vaccinations', methods=['GET', 'POST'])
@login_required
def view_vaccinations():
    if current_user.user_type != 'public':
        return redirect(url_for('login'))

    cursor = conn.cursor()
    prs_id = current_user.id
    cursor.execute("SELECT Vaccination_Status FROM Individual WHERE PRS_Id = ?", (prs_id,))
    row = cursor.fetchone()
    vaccination_status = row[0] if row else "Unknown"

    # MongoDB connection
    mongo_client = MongoClient("mongodb://localhost:27017/")
    mongo_db = mongo_client["PRS"]
    collection = mongo_db["PatientsWithImmunizations"]

    if request.method == 'POST':
        vaccine = request.form.get('vaccine')
        manufacturer = request.form.get('manufacturer')
        vax_date = request.form.get('date')
        lot = request.form.get('lot')

        cursor.execute("SELECT 1 FROM Approved_Vaccines WHERE Vaccine_Name = ? AND Manufacturer = ?", (vaccine, manufacturer))
        if cursor.fetchone():
            new_vax = {
                "vaccine": vaccine,
                "manufacturer": manufacturer,
                "date": vax_date,
                "lotNumber": lot
            }
            mongo_doc = collection.find_one({"PRS_ID": prs_id})
            if mongo_doc:
                collection.update_one({"PRS_ID": prs_id}, {"$push": {"immunizations": new_vax}})
            else:
                collection.insert_one({"PRS_ID": prs_id, "patient": {"name": current_user.email}, "immunizations": [new_vax]})
            flash("Vaccination added successfully!", "success")
        else:
            flash("Invalid vaccine/manufacturer combination.", "danger")

    mongo_doc = collection.find_one({"PRS_ID": prs_id})
    immunizations = mongo_doc.get("immunizations", []) if mongo_doc else []

    cursor.execute("SELECT Vaccine_Name, Manufacturer FROM Approved_Vaccines")
    approved_vaccines = cursor.fetchall()

    return render_template("vaccinations.html",
                           vaccination_status=vaccination_status,
                           immunizations=immunizations,
                           approved_vaccines=approved_vaccines,
                           current_date=date.today().isoformat())

# ----------------------
# Government Dashboard Routes
# ----------------------

@app.route('/gov_dashboard')
@login_required
def gov_dashboard():
    if current_user.user_type != 'gov':
        return redirect(url_for('login'))
    log_access('gov', 'Viewed Dashboard')
    return render_template("gov_dashboard.html")

@app.route('/gov/inventory')
@login_required
def inventory():
    if current_user.user_type != 'gov':
        return redirect(url_for('login'))

    # Fetch inventory data (as before)
    LOW_STOCK_THRESHOLD = 50
    cursor = conn.cursor()
    cursor.execute("""
        SELECT I.Inventory_Id, I.Store_Id, S.Address, I.Item_Id, C.Name, I.Current_Stock, I.Last_Restocked_Date
        FROM Inventory I
        JOIN Store S ON I.Store_Id = S.Store_Id
        JOIN Critical_Item C ON I.Item_Id = C.Item_Id
    """)
    inventory_rows = cursor.fetchall()
    inventory_data = [{
        "Inventory_Id": r[0],
        "Store_Id": r[1],
        "Address": r[2],
        "Item_Id": r[3],
        "Item_Name": r[4],
        "Current_Stock": r[5],
        "Last_Restocked_Date": r[6],
        "Low_Stock": r[5] < LOW_STOCK_THRESHOLD
    } for r in inventory_rows]

    # Fetch critical items data
    cursor.execute("SELECT Item_Id, Name, Category, Daily_Limit_Per_Person, Weekly_Limit_Per_Person FROM Critical_Item")
    critical_item_rows = cursor.fetchall()
    critical_items = [{
        "Item_Id": row[0],
        "Name": row[1],
        "Category": row[2],
        "Daily_Limit": row[3],
        "Weekly_Limit": row[4]
    } for row in critical_item_rows]
    cursor.close()

    return render_template("gov_inventory.html", inventory=inventory_data, critical_items=critical_items)

@app.route('/gov/inventory/critical_item/add', methods=['POST'])
@login_required
def add_critical_item():
    if current_user.user_type != 'gov':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    name = request.form.get('name')
    category = request.form.get('category')
    daily_limit = request.form.get('daily_limit')
    weekly_limit = request.form.get('weekly_limit')

    if not all([name, category, daily_limit, weekly_limit]):
        flash("All fields are required to add a new item.", "warning")
        return redirect(url_for('inventory'))

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Critical_Item (Name, Category, Daily_Limit_Per_Person, Weekly_Limit_Per_Person) VALUES (?, ?, ?, ?)",
            (name, category, int(daily_limit), int(weekly_limit)))
        conn.commit()
        
        # Get the inserted item ID for logging
        cursor.execute("SELECT SCOPE_IDENTITY()")
        item_id = cursor.fetchone()[0]
        
        flash(f"Item '{name}' added successfully.", "success")
        log_access('gov', 'Added Critical Item', 'Critical_Item', item_id, 
                  {'name': name, 'category': category})
    except pyodbc.Error as ex:
        conn.rollback()
        flash(f"Error adding item: {str(ex)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('inventory'))




@app.route('/gov/inventory/critical_item/edit/<item_id>', methods=['POST'])
@login_required
def edit_critical_item(item_id):
    if current_user.user_type != 'gov':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    daily_limit = request.form.get('daily_limit')
    weekly_limit = request.form.get('weekly_limit')

    if not all([daily_limit, weekly_limit]):
        flash("Daily and Weekly limits are required to edit an item.", "warning")
        return redirect(url_for('inventory'))

    cursor = conn.cursor()
    try:
        # First get the item details for logging
        cursor.execute("SELECT Name FROM Critical_Item WHERE Item_Id = ?", (item_id,))
        item = cursor.fetchone()
        if not item:
            flash("Item not found.", "danger")
            return redirect(url_for('inventory'))
            
        item_name = item[0]

        # Perform the update
        cursor.execute(
            "UPDATE Critical_Item SET Daily_Limit_Per_Person = ?, Weekly_Limit_Per_Person = ? WHERE Item_Id = ?",
            (int(daily_limit), int(weekly_limit), item_id))
        conn.commit()
        
        flash(f"Item '{item_name}' updated successfully.", "success")
    except pyodbc.Error as ex:
        conn.rollback()
        flash(f"Error updating item: {str(ex)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('inventory'))



@app.route('/gov/inventory/critical_item/remove/<item_id>', methods=['POST'])
@login_required
def remove_critical_item(item_id):
    if current_user.user_type != 'gov':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    cursor = conn.cursor()
    try:
        # First get the item details for logging
        cursor.execute("SELECT Name FROM Critical_Item WHERE Item_Id = ?", (item_id,))
        item = cursor.fetchone()
        if not item:
            flash("Item not found.", "danger")
            return redirect(url_for('inventory'))
            
        item_name = item[0]

        # Check if item is referenced in inventory
        cursor.execute("SELECT COUNT(*) FROM Inventory WHERE Item_Id = ?", (item_id,))
        if cursor.fetchone()[0] > 0:
            flash("Cannot remove item - it exists in inventory records.", "danger")
            return redirect(url_for('inventory'))

        # Perform the deletion
        cursor.execute("DELETE FROM Critical_Item WHERE Item_Id = ?", (item_id,))
        conn.commit()
        
        flash(f"Item '{item_name}' removed successfully.", "success")
        log_access('gov', 'Removed Critical Item', 'Critical_Item', item_id,
                  {'name': item_name})
    except pyodbc.Error as ex:
        conn.rollback()
        flash(f"Error removing item: {str(ex)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('inventory'))



@app.route('/gov/vaccination', methods=['GET', 'POST'])
@login_required
def gov_vaccination():
    if current_user.user_type != 'gov':
        return redirect(url_for('login'))
    global conn  # Ensure the global connection object is accessible

    if request.method == 'POST':
        if 'add_vaccine' in request.form:
            vaccine_name = request.form['vaccine_name']
            manufacturer = request.form['manufacturer']
            if vaccine_name and manufacturer:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO Approved_Vaccines (Vaccine_Name, Manufacturer) VALUES (?, ?)",
                        (vaccine_name, manufacturer)
                    )
                    conn.commit()
                    cursor.close()  # It's good practice to close cursors when you're done with them

                    flash(f"Vaccine '{vaccine_name}' by '{manufacturer}' added successfully.", "success")
                except pyodbc.Error as ex:
                    sqlstate = ex.args[0]
                    flash(f"Error adding vaccine: {sqlstate}", "danger")
            else:
                flash("Please fill in both fields for adding a vaccine.", "warning")
            return redirect(url_for('gov_vaccination'))
        elif 'remove_vaccine' in request.form:
            vaccine_to_remove = request.form['approved_vaccine']
            try:
                cursor = conn.cursor()  # Create a new cursor using the global connection
                cursor.execute("DELETE FROM Approved_Vaccines WHERE Vaccine_Name = ?", (vaccine_to_remove,))
                conn.commit()
                cursor.close()  # It's good practice to close cursors when you're done with them

                flash(f"Vaccine '{vaccine_to_remove}' removed successfully.", "success")
            except pyodbc.Error as ex:
                sqlstate = ex.args[0]
                flash(f"Error removing vaccine: {sqlstate}", "danger")
            return redirect(url_for('gov_vaccination'))

    # SQL part for summary
    cursor = conn.cursor()  # Create a new cursor for fetching data
    cursor.execute("SELECT Vaccination_Status, COUNT(*) FROM Individual GROUP BY Vaccination_Status")
    status_counts = cursor.fetchall()
    vaccination_summary = {row[0]: row[1] for row in status_counts}
    cursor.close() # Close the cursor after use


    # Mongo part for dose counts
    mongo_client = MongoClient("mongodb://localhost:27017/")
    mongo_db = mongo_client["PRS"]
    collection = mongo_db["PatientsWithImmunizations"]
    pipeline = [
        {"$unwind": "$immunizations"},
        {"$group": {
            "_id": "$immunizations.vaccine",
            "count": {"$sum": 1}
        }}
    ]
    mongo_results = list(collection.aggregate(pipeline))
    dose_counts = [(doc['_id'], doc['count']) for doc in mongo_results]

    # Fetch approved vaccines for display and removal
    cursor = conn.cursor()  # Create another new cursor
    cursor.execute("SELECT Vaccine_Name, Manufacturer FROM Approved_Vaccines")
    approved_vaccines = cursor.fetchall()
    cursor.close() # Close this cursor as well

    log_access('gov', 'Viewed Vaccination Dashboard')
    return render_template("gov_vaccination.html",
                           vaccination_summary=vaccination_summary,
                           dose_counts=dose_counts,
                           approved_vaccines=approved_vaccines)

# Route: Compliance Monitoring
@app.route('/gov/compliance')
@login_required
def gov_compliance():
    if current_user.user_type != 'gov':
        return redirect(url_for('login'))
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT T.Transaction_Id, T.PRS_Id, I.Name, I.Date_of_Birth, 
                   T.Store_Id, T.Item_Id, C.Name AS Item_Name, 
                   T.Quantity_Purchased, T.Purchase_Date, T.Compliance_Status
            FROM Purchase_Transaction T
            JOIN Individual I ON T.PRS_Id = I.PRS_Id
            JOIN Critical_Item C ON T.Item_Id = C.Item_Id
            ORDER BY T.Purchase_Date DESC
        """)

        transactions = cursor.fetchall()

        compliance_data = []
        for row in transactions:
            status = row[9]
            status_style = ""
            if status == "Over_Limit" or status == "Invalid_Day":
                status_style = "color: red;"
            compliance_data.append({
                "Transaction_Id": row[0],
                "PRS_Id": row[1],
                "Name": row[2],
                "DOB": row[3],
                "Store_Id": row[4],
                "Item_Id": row[5],
                "Item_Name": row[6],
                "Quantity_Purchased": row[7],
                "Purchase_Date": row[8],
                "Compliance_Status": mark_compliance_status(status),
                "status_style": status_style
            })

        return render_template("gov_compliance.html", compliance=compliance_data)
    finally:
        cursor.close()

def mark_compliance_status(status):
    if status == "Over_Limit" or status == "Invalid_Day":
        return f'<span style="color: red;">{status}</span>'
    return status


# MERCHANT DASH
@app.route('/merchant_dashboard')
@login_required
def merchant_dashboard():
    log_access('merchant', 'Viewed Dashboard')
    return render_template("merchant_dashboard.html")

@app.route('/merchant/inventory', methods=['GET', 'POST'])
@login_required
def merchant_inventory():
    merchant_id = current_user.id
    cursor = conn.cursor()

    try:
        # GET request - display inventory
        if request.method == 'GET':
            try:
                # Get merchant's inventory
                cursor.execute("""
                    SELECT I.Inventory_Id, I.Store_Id, S.Address, I.Item_Id, C.Name AS Item_Name,
                           I.Current_Stock, I.Last_Restocked_Date
                    FROM Inventory I
                    JOIN Store S ON I.Store_Id = S.Store_Id
                    JOIN Critical_Item C ON I.Item_Id = C.Item_Id
                    WHERE S.Merchant_Id = ?
                """, (merchant_id,))
                inventory_data = cursor.fetchall()

                # Get available items for dropdown
                cursor.execute("SELECT Item_Id, Name FROM Critical_Item")
                critical_items = cursor.fetchall()

                log_access('merchant', 'Viewed Inventory Page')
                return render_template("merchant_inventory.html", 
                                    inventory=inventory_data, 
                                    critical_items=critical_items)

            except pyodbc.Error as e:
                flash(f"Database error while loading inventory: {str(e)}", "danger")
                return redirect(url_for('merchant_dashboard'))

        # POST request - add inventory
        elif request.method == 'POST':
            item_id_to_add = request.form.get('item_to_add')
            quantity_to_add = request.form.get('quantity_to_add')

            # Validate input
            if not (item_id_to_add and quantity_to_add and quantity_to_add.isdigit() and int(quantity_to_add) > 0):
                flash("Please select an item and enter a valid positive quantity.", "warning")
                return redirect(url_for('merchant_inventory'))

            try:
                # Get merchant's store
                cursor.execute("SELECT Store_Id FROM Store WHERE Merchant_Id = ?", (merchant_id,))
                store_row = cursor.fetchone()
                
                if not store_row:
                    flash("No store associated with your merchant account.", "danger")
                    return redirect(url_for('merchant_inventory'))

                store_id = store_row[0]

                # Get item name for logging
                cursor.execute("SELECT Name FROM Critical_Item WHERE Item_Id = ?", (item_id_to_add,))
                item_name_row = cursor.fetchone()
                item_name = item_name_row[0] if item_name_row else f"ID:{item_id_to_add}"

                # Check for existing inventory
                cursor.execute("""
                    SELECT Inventory_Id, Current_Stock 
                    FROM Inventory 
                    WHERE Store_Id = ? AND Item_Id = ?
                """, (store_id, item_id_to_add))
                existing_inventory = cursor.fetchone()

                if existing_inventory:
                    # Update existing inventory
                    inventory_id = existing_inventory[0]
                    new_stock = existing_inventory[1] + int(quantity_to_add)
                    
                    cursor.execute("""
                        UPDATE Inventory 
                        SET Current_Stock = ?, Last_Restocked_Date = ?
                        WHERE Inventory_Id = ?
                    """, (new_stock, datetime.now().date(), inventory_id))
                    
                    action = "Updated"
                else:
                    # Create new inventory entry
                    cursor.execute("""
                        INSERT INTO Inventory (Store_Id, Item_Id, Current_Stock, Last_Restocked_Date)
                        VALUES (?, ?, ?, ?)
                    """, (store_id, item_id_to_add, int(quantity_to_add), datetime.now().date()))
                    
                    cursor.execute("SELECT SCOPE_IDENTITY()")
                    inventory_id = cursor.fetchone()[0]
                    action = "Added"

                conn.commit()
                
                # Log the action with details
                log_access('merchant', f'{action} Inventory Stock', 
                          'Inventory', inventory_id,
                          {
                              'item_id': item_id_to_add,
                              'item_name': item_name,
                              'quantity_added': quantity_to_add,
                              'store_id': store_id
                          })
                
                flash(f"Successfully {action.lower()} {quantity_to_add} units of {item_name} to inventory.", "success")
                return redirect(url_for('merchant_inventory'))

            except pyodbc.Error as e:
                conn.rollback()
                flash(f"Database error while updating inventory: {str(e)}", "danger")
                return redirect(url_for('merchant_inventory'))

    finally:
        cursor.close()

@app.route('/merchant/compliance')
@login_required
def merchant_compliance():
    merchant_id = current_user.id
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT T.Transaction_Id, T.PRS_Id, I.Name, T.Store_Id, T.Item_Id, C.Name AS Item_Name,
                   T.Quantity_Purchased, T.Purchase_Date, T.Compliance_Status
            FROM Purchase_Transaction T
            JOIN Individual I ON T.PRS_Id = I.PRS_Id
            JOIN Critical_Item C ON T.Item_Id = C.Item_Id
            JOIN Store S ON T.Store_Id = S.Store_Id
            WHERE S.Merchant_Id = ?
            AND T.Compliance_Status != 'Valid'
            ORDER BY T.Purchase_Date DESC
        """, (merchant_id,))

        compliance_data = cursor.fetchall()
        return render_template("merchant_compliance.html", transactions=compliance_data)
    finally:
        cursor.close()

# Before (incorrect - missing route decorator)
def merchant_sales():
    merchant_id = current_user.id
    cursor = conn.cursor()
    # ... rest of the function ...

# After (correct)
@app.route('/merchant/sales')
@login_required
def merchant_sales():


    merchant_id = current_user.id
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT T.Transaction_Id, T.PRS_Id, I.Name, T.Store_Id, C.Name AS Item_Name,
                   T.Quantity_Purchased, T.Purchase_Date
            FROM Purchase_Transaction T
            JOIN Individual I ON T.PRS_Id = I.PRS_Id
            JOIN Critical_Item C ON T.Item_Id = C.Item_Id
            JOIN Store S ON T.Store_Id = S.Store_Id
            WHERE S.Merchant_Id = ?
            ORDER BY T.Purchase_Date DESC
        """, (merchant_id,))

        sales_data = cursor.fetchall()
        log_access('merchant', 'Viewed Sales Records')
        return render_template("merchant_sales.html", sales=sales_data)
    except pyodbc.Error as e:
        flash("Error retrieving sales data.", "danger")
        app.logger.error(f"Database error in merchant_sales: {str(e)}")
        return redirect(url_for('merchant_dashboard'))
    finally:
        cursor.close()

if __name__ == '__main__':
    app.run(debug=True)
