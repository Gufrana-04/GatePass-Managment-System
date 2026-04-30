import oracledb
from flask import Flask, jsonify
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import config

app = Flask(__name__)
app.secret_key = "my_super_secret_key_123"

# thick mode using config
try:
    oracledb.init_oracle_client(lib_dir=config.ORACLE_CLIENT_PATH)
except Exception as e:
    print(f"Oracle Client already initialized or path error: {e}")

# Use config values instead of hardcoding
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_DSN = config.DB_DSN

def check_db_connection():
    """Attempts to connect to the Oracle database and returns a status."""
    connection = None
    try:
        connection = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM v$database")
        db_name = cursor.fetchone()[0]
        return True, f"Connection successful! Database: {db_name}, Database version: {connection.version}"
    except oracledb.Error as error:
        return False, f"Connection failed: {error}"
    finally:
        if connection:
            connection.close()


def get_db_connection():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN
    )


# GENERALIZING
@app.context_processor
def inject_global_variables():
    return {
        "SYSTEM_NAME": config.SYSTEM_NAME,
    }


@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    connection = None
    cursor = None
    site_codes = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT DISTINCT TRIM(site_code) AS site_code
            FROM site
            ORDER BY site_code
        """)
        site_codes = [row[0] for row in cursor.fetchall()]

    except Exception as e:
        return render_template("login.html", error=f"Error fetching site codes: {e}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        site_code = request.form.get("site_code")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                SELECT TRIM(password)
                FROM ztmp_user
                WHERE TRIM(Login_name) = :username
                AND TRIM(site_code) = :site_code
            """
            cursor.execute(query, {"username": username, "site_code": site_code})
            user = cursor.fetchone()

            if user is None:
                return render_template(
                    "login.html",
                    error="Invalid username or site code",
                    username=username,
                    site_code=site_code,
                    site_codes=site_codes
                )

            db_password = user[0]

            if db_password != password:
                return render_template(
                    "login.html",
                    error="Invalid password",
                    username=username,
                    site_code=site_code,
                    site_codes=site_codes
                )

            session["user"] = username
            session["site_code"] = site_code
            return redirect(url_for("dashboard"))

        except Exception as e:
            return render_template(
                "login.html",
                error=f"Error during login: {e}",
                username=username,
                site_code=site_code,
                site_codes=site_codes
            )

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template("login.html", site_codes=site_codes)


# GET SITECODE FROM DB
@app.route("/api/sitecodes")
def api_sitecodes():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT DISTINCT TRIM(site_code) AS site_code
            FROM site
            ORDER BY site_code
        """)

        columns = [col[0].lower() for col in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close()
        connection.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Dashboard Routing
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html",
                           username=session["user"],
                           site_code=session["site_code"])


@app.route("/transaction/Gatepass Data Entry")
def gatepass_entry():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
    "data_entry.html",
    site_code=session.get("site_code"),
    emp_code=session.get("emp_code")   # or whatever key you store emp_code under
)


@app.route("/transaction/Gatepass In Out Entry")
def gatepass_in_out_entry():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "in_out.html",
        user=session.get("user"),
        site_code=session.get("site_code"),
        site_name=session.get("site_name"),
        department=session.get("department")
    )


# ─────────────────────────────────────────
# API: Supplier / Employee list for autocomplete
# ─────────────────────────────────────────
@app.route("/api/supplier/list")
def api_supplier_list():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    type_ = request.args.get("type", "OUTSIDE").strip().upper()
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if type_ == "OUTSIDE":
            cursor.execute("""
                SELECT TRIM(supp_code)  AS code,
                       TRIM(supp_name)  AS name,
                       TRIM(addr1)      AS addr1,
                       TRIM(addr2)      AS addr2,
                       TRIM(addr3)      AS addr3,
                       TRIM(city)       AS city,
                       TRIM(tele1)       AS phone,
                       TRIM(pin)        AS pin,
                       TRIM(email_addr) AS email
                FROM supplier
                WHERE TRIM(black_list) = 'N'
                ORDER BY supp_code
            """)
        else:
            # INTER UNIT — employee table
            cursor.execute("""
                SELECT TRIM(emp_code)                          AS code,
                       TRIM(emp_fname) || ' ' || TRIM(emp_lname) AS name,
                       TRIM(cur_add1)                          AS addr1,
                       TRIM(cur_add2)                          AS addr2,
                       TRIM(cur_add3)                          AS addr3,
                       TRIM(cur_city)                          AS city,
                       TRIM(cur_tel1)                          AS phone,
                       TRIM(cur_pin)                           AS pin,
                       TRIM(email_id_off)                      AS email
                FROM employee
                WHERE relieve_date IS NULL
                ORDER BY emp_code, emp_fname
            """)

        columns = [col[0].lower() for col in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Replace None with empty string
        for row in data:
            for k in row:
                if row[k] is None:
                    row[k] = ""

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@app.route("/api/gatepass/list")
def api_gatepass_list():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        site_code = request.args.get("site_code") or session["site_code"]
        if not site_code:
            site_code = "ALL"

        # Accept year + month (1-based) from the month navigator
        try:
            year  = int(request.args.get("year",  datetime.today().year))
            month = int(request.args.get("month", datetime.today().month))
        except (ValueError, TypeError):
            year  = datetime.today().year
            month = datetime.today().month

        # First and last day of the selected month
        from_date_str     = f"01/{month:02d}/{str(year)[-2:]}"
        # Last day: use first day of next month minus 1
        if month == 12:
            last_day_str  = f"31/12/{str(year)[-2:]}"
        else:
            import calendar as _cal
            last_day      = _cal.monthrange(year, month)[1]
            last_day_str  = f"{last_day:02d}/{month:02d}/{str(year)[-2:]}"

        query = """
            SELECT confirmed, site_code, gp_no, gp_date,
                   gp_type, supp_code, supp_name, addr1, addr2, addr3, city, pin, phone,
                   trans_type, vehicle_no, valid_date, carry_out_by, sec_remark, prep_by, dept_code, email_addr,
                   dept_cd_metr, courier_nm, docket_no, conf_by, conf_date,
                   tc1, tc2, tc3, tc4, tc5, tc6, cst_tin_no, cst_tin_date, vat_tin_no, vat_tin_date, ecc_reg_no
            FROM zgima_gatepass_TEMP
            WHERE site_code = :site_code
              AND TRUNC(TO_DATE(gp_date,'DD/MM/YY')) BETWEEN
                  TO_DATE(:from_date, 'DD/MM/YY')
                  AND TO_DATE(:last_date, 'DD/MM/YY')
            ORDER BY gp_no DESC
        """

        cursor.execute(query, {
            "site_code": site_code,
            "from_date": from_date_str,
            "last_date": last_day_str
        })

        columns = [col[0].lower() for col in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ── Material Dept: all departments ──────────────────────────
@app.route("/api/department/list")
def get_department_list():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dept_code, descr 
            FROM department 
            ORDER BY dept_code, descr
        """)
        rows = cursor.fetchall()
        result = [{"dept_code": r[0], "department": r[1]} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

#____________________________________________________________
#------------------ TO BE DONE LATER-------------------------
#____________________________________________________________
'''# ── Department Code: filtered by logged-in employee ────────
@app.route("/api/department/by_employee")
def get_dept_by_employee():
    emp_code = request.args.get("emp_code", "").strip()
    if not emp_code:
        return jsonify({"error": "emp_code is required"}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
                SELECT d.dept_code, d.description
    FROM department d
    WHERE d.dept_code IN (
        SELECT dept_code 
        FROM employee 
        WHERE emp_code = :emp_code
    )
    ORDER BY d.dept_codee
        """, {"emp_code": emp_code})
        rows = cursor.fetchall()
        result = [{"dept_code": r[0], "description": r[1]} for r in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()'''

@app.route("/api/gatepass/details")
def get_gatepass_details():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    gp_no = request.args.get("gp_no")

    if not gp_no:
        return jsonify([])

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM zgima_gatepass_det_TEMP
            WHERE gp_no = :gp_no
            ORDER BY sr_no
        """

        cursor.execute(query, {"gp_no": gp_no})

        columns = [col[0].lower() for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Serialize datetime objects → ISO string so JS regex can parse correctly
        for row in rows:
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.strftime("%Y-%m-%dT%H:%M:%S")

        return jsonify(rows)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/gatepass/header")
def get_gatepass_header():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    gp_no = request.args.get("gp_no")

    if not gp_no:
        return jsonify({"error": "GP No required"}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Query TEMP table where all entries are saved
        query = """
            SELECT *
            FROM zgima_gatepass_TEMP
            WHERE gp_no = :gp_no
        """

        cursor.execute(query, {"gp_no": gp_no})

        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Gatepass not found"}), 404

        columns = [col[0].lower() for col in cursor.description]
        data = dict(zip(columns, row))

        # Convert datetime/date objects → "DD/MM/YYYY" string so jsonify doesn't crash
        from datetime import datetime, date
        for k, v in data.items():
            if isinstance(v, (datetime, date)):
                data[k] = v.strftime("%d/%m/%Y")

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# Database status check
@app.route('/db-status')
def db_status():
    is_connected, message = check_db_connection()
    if is_connected:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500


# ─────────────────────────────────────────
# HELPER: Convert HTML date to Oracle format
# ─────────────────────────────────────────
def fmt_date(d):
    if not d:
        return None
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%y")
    except Exception:
        return None


# ─────────────────────────────────────────
# HELPER: Convert frontend datetime string to Oracle VARCHAR format
# Input:  "DD/MM/YYYY HH-MM AM/PM"  e.g. "25/03/2026 02-30 PM"
# Output: "DD/MON/YY HH:MM"         e.g. "25/MAR/26 14:30"
# ─────────────────────────────────────────
def fmt_in_dttime(val):
    if not val:
        return None
    try:
        dt = datetime.strptime(val.strip(), "%d/%m/%Y %I-%M %p")
        return dt.strftime("%d-%b-%y %H:%M").upper()   # e.g. 25/MAR/26 14:30
    except Exception:
        return val   # fallback: save as-is if parsing fails


# ─────────────────────────────────────────
# HELPER: Site code → 2-letter GP prefix
# ─────────────────────────────────────────
SITE_PREFIX_MAP = {
    "S0101": "GH", "S0100": "GK", "S0102": "GW", "S0103": "GF",
    "S0104": "GM", "S0105": "GI", "S0106": "GD", "S0107": "GA",
    "S0109": "GB", "S0110": "GS", "SSTPL": "ST", "HITPL": "HT",
    "BGTPL": "BG", "S0111": "GT", "SARA1": "SA", "GIPL1": "SR",
    "B0001": "BA", "B0002": "BB", "KKC01": "KK", "M0001": "MD",
    "M0002": "MH", "M0006": "MW", "O0001": "GO",
}

# Month number (1-12) → single letter A-L
MONTH_LETTER = {
    1: "A", 2: "B",  3: "C",  4: "D",
    5: "E", 6: "F",  7: "G",  8: "H",
    9: "I", 10: "J", 11: "K", 12: "L",
}


# ─────────────────────────────────────────
# HELPER: Generate next GP number
# Format: [SitePrefix2][YY][MonthLetter][00001]
# e.g.  GH25C00001
# ─────────────────────────────────────────
def generate_gp_no(site_code, year, month):
    site_prefix = SITE_PREFIX_MAP.get(site_code.strip().upper())
    if not site_prefix:
        raise ValueError(f"Unknown site code: {site_code}")

    yy          = str(year)[-2:]
    month_ltr   = MONTH_LETTER[int(month)]
    prefix5     = f"{site_prefix}{yy}{month_ltr}"   # e.g. GH25C

    connection = None
    cursor     = None
    try:
        connection = get_db_connection()
        cursor     = connection.cursor()

        cursor.execute(
            "SELECT NVL(MAX(TO_NUMBER(SUBSTR(gp_no, 6, 5))), 0) "
            "FROM zgima_gatepass_TEMP "
            "WHERE SUBSTR(gp_no, 1, 5) = :prefix",
            {"prefix": prefix5}
        )
        row    = cursor.fetchone()
        next_n = (row[0] if row and row[0] else 0) + 1

        return f"{prefix5}{str(next_n).zfill(5)}"

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Get next GP number (for frontend)
# Expects: ?site_code=S0101&year=2025&month=3
# ─────────────────────────────────────────
@app.route("/api/gatepass/next_gp_no")
def api_next_gp_no():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        site_code = request.args.get("site_code") or session.get("site_code")
        year      = int(request.args.get("year",  datetime.today().year))
        month     = int(request.args.get("month", datetime.today().month))

        if not site_code:
            return jsonify({"error": "site_code is required"}), 400

        return jsonify({"gp_no": generate_gp_no(site_code, year, month)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────
# API: Save Gatepass HEADER  (Next button)
# ─────────────────────────────────────────
@app.route("/api/gatepass/save_header", methods=["POST"])
def save_gatepass_header():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        site_code_val = data.get("site_code", "").strip() or session.get("site_code", "")
        now           = datetime.today()
        gp_no = data.get("gp_no") or generate_gp_no(site_code_val, now.year, now.month)

        # Check if header already exists (INSERT vs UPDATE)
        cursor.execute(
            "SELECT COUNT(*) FROM zgima_gatepass_TEMP WHERE gp_no = :gp_no",
            {"gp_no": gp_no}
        )
        exists = cursor.fetchone()[0]

        # Parse HTML date strings (YYYY-MM-DD) into Python datetime objects.
        # Passing datetime objects lets oracledb bind them as native Oracle DATEs
        # — no TO_DATE() needed in SQL, so None/empty values safely become NULL
        # and never trigger ORA-01036.
        def to_pydate(val):
            if not val:
                return None
            try:
                return datetime.strptime(str(val).strip()[:10], "%Y-%m-%d")
            except Exception:
                return None

        gp_date_val = to_pydate(data.get("gp_date"))
        if not gp_date_val:
            return jsonify({"error": "GP Date is required"}), 400

        params = {
            "site_code":    data.get("site_code", "").strip(),
            "gp_no":        gp_no,
            "gp_date":      gp_date_val,
            "gp_type":      data.get("gp_type", "").strip(),
            "supp_code":    data.get("supp_code", "").strip(),
            "supp_name":    data.get("supp_name", "").strip(),
            "addr1":        data.get("addr1", "").strip(),
            "addr2":        data.get("addr2", "").strip(),
            "addr3":        data.get("addr3", "").strip(),
            "city":         data.get("city", "").strip(),
            "pin":          data.get("pin", "").strip(),
            "phone":        data.get("phone", "").strip(),
            "trans_type":   data.get("trans_type", "").strip(),
            "vehicle_no":   data.get("vehicle_no", "").strip(),
            "valid_date":   to_pydate(data.get("valid_date")),
            "carry_out_by": data.get("carry_out_by", "").strip(),
            "sec_remark":   data.get("sec_remark", "").strip(),
            "prep_by":      session.get("user", "").strip(),
            "dept_code":    data.get("dept_code", "").strip(),
            "email_addr":   data.get("email_addr", "").strip(),
            "dept_cd_metr": data.get("dept_cd_metr", "").strip(),
            "courier_nm":   data.get("courier_nm", "").strip(),
            "tc1":          data.get("tc1", "").strip(),
            "tc2":          data.get("tc2", "").strip(),
            "tc3":          data.get("tc3", "").strip(),
            "tc4":          data.get("tc4", "").strip(),
            "tc5":          data.get("tc5", "").strip(),
            "tc6":          data.get("tc6", "").strip(),
            "cst_tin_no":   data.get("cst_tin_no", "").strip(),
            "cst_tin_date": to_pydate(data.get("cst_tin_date")),
            "vat_tin_no":   data.get("vat_tin_no", "").strip(),
            "vat_tin_date": to_pydate(data.get("vat_tin_date")),
            "ecc_reg_no":   data.get("ecc_reg_no", "").strip(),
            "confirmed":    "N",
            "conf_by":      None,
            "conf_date":    None,
            "gp_transit":   data.get("gp_transit", "").strip(),
        }

        # oracledb thick mode raises ORA-01036 if the params dict contains keys
        # that are not referenced in the SQL.  Use separate, exact dicts for
        # UPDATE and INSERT so there are no stray bind names.
        if exists:
            update_params = {
                "gp_no":        params["gp_no"],
                "gp_date":      params["gp_date"],
                "gp_type":      params["gp_type"],
                "supp_code":    params["supp_code"],
                "supp_name":    params["supp_name"],
                "addr1":        params["addr1"],
                "addr2":        params["addr2"],
                "addr3":        params["addr3"],
                "city":         params["city"],
                "pin":          params["pin"],
                "phone":        params["phone"],
                "trans_type":   params["trans_type"],
                "vehicle_no":   params["vehicle_no"],
                "valid_date":   params["valid_date"],
                "carry_out_by": params["carry_out_by"],
                "sec_remark":   params["sec_remark"],
                "dept_code":    params["dept_code"],
                "email_addr":   params["email_addr"],
                "dept_cd_metr": params["dept_cd_metr"],
                "courier_nm":   params["courier_nm"],
                "tc1": params["tc1"], "tc2": params["tc2"], "tc3": params["tc3"],
                "tc4": params["tc4"], "tc5": params["tc5"], "tc6": params["tc6"],
                "cst_tin_no":   params["cst_tin_no"],
                "cst_tin_date": params["cst_tin_date"],
                "vat_tin_no":   params["vat_tin_no"],
                "vat_tin_date": params["vat_tin_date"],
                "ecc_reg_no":   params["ecc_reg_no"],
            }
            cursor.execute("""
                UPDATE zgima_gatepass_TEMP SET
                    gp_date      = :gp_date,
                    gp_type      = :gp_type,
                    supp_code    = :supp_code,
                    supp_name    = :supp_name,
                    addr1        = :addr1,
                    addr2        = :addr2,
                    addr3        = :addr3,
                    city         = :city,
                    pin          = :pin,
                    phone        = :phone,
                    trans_type   = :trans_type,
                    vehicle_no   = :vehicle_no,
                    valid_date   = :valid_date,
                    carry_out_by = :carry_out_by,
                    sec_remark   = :sec_remark,
                    dept_code    = :dept_code,
                    email_addr   = :email_addr,
                    dept_cd_metr = :dept_cd_metr,
                    courier_nm   = :courier_nm,
                    tc1 = :tc1, tc2 = :tc2, tc3 = :tc3,
                    tc4 = :tc4, tc5 = :tc5, tc6 = :tc6,
                    cst_tin_no   = :cst_tin_no,
                    cst_tin_date = :cst_tin_date,
                    vat_tin_no   = :vat_tin_no,
                    vat_tin_date = :vat_tin_date,
                    ecc_reg_no   = :ecc_reg_no
                WHERE gp_no = :gp_no
            """, update_params)
        else:
            insert_params = {
                "site_code":    params["site_code"],
                "gp_no":        params["gp_no"],
                "gp_date":      params["gp_date"],
                "gp_type":      params["gp_type"],
                "supp_code":    params["supp_code"],
                "supp_name":    params["supp_name"],
                "addr1":        params["addr1"],
                "addr2":        params["addr2"],
                "addr3":        params["addr3"],
                "city":         params["city"],
                "pin":          params["pin"],
                "phone":        params["phone"],
                "trans_type":   params["trans_type"],
                "vehicle_no":   params["vehicle_no"],
                "valid_date":   params["valid_date"],
                "carry_out_by": params["carry_out_by"],
                "sec_remark":   params["sec_remark"],
                "prep_by":      params["prep_by"],
                "dept_code":    params["dept_code"],
                "email_addr":   params["email_addr"],
                "dept_cd_metr": params["dept_cd_metr"],
                "courier_nm":   params["courier_nm"],
                "tc1": params["tc1"], "tc2": params["tc2"], "tc3": params["tc3"],
                "tc4": params["tc4"], "tc5": params["tc5"], "tc6": params["tc6"],
                "cst_tin_no":   params["cst_tin_no"],
                "cst_tin_date": params["cst_tin_date"],
                "vat_tin_no":   params["vat_tin_no"],
                "vat_tin_date": params["vat_tin_date"],
                "ecc_reg_no":   params["ecc_reg_no"],
                "confirmed":    params["confirmed"],
                "conf_by":      params["conf_by"],
                "conf_date":    params["conf_date"],
                "gp_transit":   params["gp_transit"],
            }
            cursor.execute("""
                INSERT INTO zgima_gatepass_TEMP (
                    site_code, gp_no, gp_date, gp_type,
                    supp_code, supp_name, addr1, addr2, addr3,
                    city, pin, phone, trans_type, vehicle_no,
                    valid_date, carry_out_by, sec_remark, prep_by,
                    dept_code, email_addr, dept_cd_metr, courier_nm,
                    tc1, tc2, tc3, tc4, tc5, tc6,
                    cst_tin_no, cst_tin_date, vat_tin_no, vat_tin_date,
                    ecc_reg_no, confirmed, conf_by, conf_date, gp_transit
                ) VALUES (
                    :site_code, :gp_no, :gp_date, :gp_type,
                    :supp_code, :supp_name, :addr1, :addr2, :addr3,
                    :city, :pin, :phone, :trans_type, :vehicle_no,
                    :valid_date, :carry_out_by, :sec_remark, :prep_by,
                    :dept_code, :email_addr, :dept_cd_metr, :courier_nm,
                    :tc1, :tc2, :tc3, :tc4, :tc5, :tc6,
                    :cst_tin_no, :cst_tin_date, :vat_tin_no, :vat_tin_date,
                    :ecc_reg_no, :confirmed, :conf_by, :conf_date, :gp_transit
                )
            """, insert_params)

        connection.commit()
        return jsonify({"success": True, "gp_no": gp_no})

    except Exception as e:
        import traceback
        print("=== SAVE HEADER ERROR ===")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



# ─────────────────────────────────────────
# API: Confirm / Cancel Gatepass
# Sets confirmed = 'Y' (confirm) or 'X' (cancel)
# ─────────────────────────────────────────
@app.route("/api/gatepass/confirm", methods=["POST"])
def confirm_gatepass():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    gp_no  = data.get("gp_no", "").strip()
    status = data.get("status", "").strip().upper()

    if not gp_no:
        return jsonify({"error": "gp_no is required"}), 400
    if status not in ("Y", "X"):
        return jsonify({"error": "status must be Y or X"}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        conf_by   = session.get("user", "")
        conf_date = datetime.now()

        cursor.execute("""
            UPDATE zgima_gatepass_TEMP
               SET confirmed  = :status,
                   conf_by    = :conf_by,
                   conf_date  = :conf_date
             WHERE gp_no = :gp_no
        """, {"status": status, "conf_by": conf_by,
              "conf_date": conf_date, "gp_no": gp_no})

        connection.commit()
        return jsonify({"success": True, "gp_no": gp_no, "status": status})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



# ─────────────────────────────────────────
# API: Item list for detail autocomplete
# Query: select item_code,descr,unit from item where Active='Y' order by item_code,descr
# ─────────────────────────────────────────
@app.route("/api/item/list")
def api_item_list():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT TRIM(item_code) AS item_code,
                   TRIM(descr)     AS descr,
                   TRIM(unit)      AS unit
            FROM item
            WHERE Active = 'Y'
            ORDER BY item_code, descr
        """)
        columns = [col[0].lower() for col in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for row in data:
            for k in row:
                if row[k] is None:
                    row[k] = ""
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Machine code list for detail autocomplete
# Query: select mc_code,descr from machines where work_codn='Y' order by mc_code,descr
# ─────────────────────────────────────────
@app.route("/api/machine/list")
def api_machine_list():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT TRIM(mc_code) AS mc_code,
                   TRIM(descr)   AS descr
            FROM machines
            WHERE work_condn = 'Y'
            ORDER BY mc_code, descr
        """)
        columns = [col[0].lower() for col in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for row in data:
            for k in row:
                if row[k] is None:
                    row[k] = ""
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Save Gatepass DETAIL  (OK button)
# ─────────────────────────────────────────
@app.route("/api/gatepass/save_detail", methods=["POST"])
def save_gatepass_detail():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        gp_no          = data.get("gp_no", "").strip()
        sr_no          = data.get("sr_no")
        item_code      = data.get("item_code", "").strip()
        item_descr     = data.get("item_descr", "").strip()[:50]   # max 50 chars
        uom            = data.get("uom", "").strip()
        quantity       = data.get("quantity", 0)
        item_descr_add = data.get("item_descr_add", "").strip()
        rep_remark     = data.get("rep_remark", "").strip()
        mc_code        = data.get("mc_code", "").strip()

        if not gp_no:
            return jsonify({"error": "gp_no is required"}), 400

        if not sr_no:
            # ── Auto-generate: find MAX then loop until free slot found ──
            cursor.execute(
                "SELECT NVL(MAX(sr_no), 0) + 1 FROM zgima_gatepass_det_TEMP WHERE gp_no = :gp_no",
                {"gp_no": gp_no}
            )
            sr_no = cursor.fetchone()[0]

            while True:
                cursor.execute(
                    "SELECT COUNT(*) FROM zgima_gatepass_det_TEMP WHERE gp_no = :gp_no AND sr_no = :sr_no",
                    {"gp_no": gp_no, "sr_no": sr_no}
                )
                if cursor.fetchone()[0] == 0:
                    break
                sr_no += 1

            # Always INSERT for auto-generated sr_no (it's a brand new row)
            cursor.execute("""
                INSERT INTO zgima_gatepass_det_TEMP (
                    gp_no, sr_no, item_code, item_descr,
                    uom, quantity, out_qty, item_descr_add,
                    rep_remark, mc_code
                ) VALUES (
                    :gp_no, :sr_no, :item_code, :item_descr,
                    :uom, :quantity, :quantity, :item_descr_add,
                    :rep_remark, :mc_code
                )
            """, {
                "gp_no": gp_no, "sr_no": sr_no,
                "item_code": item_code, "item_descr": item_descr,
                "uom": uom, "quantity": quantity,
                "item_descr_add": item_descr_add,
                "rep_remark": rep_remark, "mc_code": mc_code
            })

        else:
            # sr_no provided → editing an existing row (UPDATE or INSERT)
            cursor.execute(
                "SELECT COUNT(*) FROM zgima_gatepass_det_TEMP WHERE gp_no = :gp_no AND sr_no = :sr_no",
                {"gp_no": gp_no, "sr_no": sr_no}
            )
            exists = cursor.fetchone()[0]

            if exists:
                cursor.execute("""
                    UPDATE zgima_gatepass_det_TEMP SET
                        item_code      = :item_code,
                        item_descr     = :item_descr,
                        uom            = :uom,
                        quantity       = :quantity,
                        out_qty        = :quantity,
                        item_descr_add = :item_descr_add,
                        rep_remark     = :rep_remark,
                        mc_code        = :mc_code
                    WHERE gp_no = :gp_no AND sr_no = :sr_no
                """, {
                    "gp_no": gp_no, "sr_no": sr_no,
                    "item_code": item_code, "item_descr": item_descr,
                    "uom": uom, "quantity": quantity,
                    "item_descr_add": item_descr_add,
                    "rep_remark": rep_remark, "mc_code": mc_code
                })
            else:
                cursor.execute("""
                    INSERT INTO zgima_gatepass_det_TEMP (
                        gp_no, sr_no, item_code, item_descr,
                        uom, quantity, out_qty, item_descr_add,
                        rep_remark, mc_code
                    ) VALUES (
                        :gp_no, :sr_no, :item_code, :item_descr,
                        :uom, :quantity, :quantity, :item_descr_add,
                        :rep_remark, :mc_code
                    )
                """, {
                    "gp_no": gp_no, "sr_no": sr_no,
                    "item_code": item_code, "item_descr": item_descr,
                    "uom": uom, "quantity": quantity,
                    "item_descr_add": item_descr_add,
                    "rep_remark": rep_remark, "mc_code": mc_code
                })

        connection.commit()
        return jsonify({"success": True, "gp_no": gp_no, "sr_no": int(sr_no)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Delete Gatepass DETAIL row
# ─────────────────────────────────────────
@app.route("/api/gatepass/delete_detail", methods=["POST"])
def delete_gatepass_detail():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    gp_no = data.get("gp_no", "").strip()
    sr_no = data.get("sr_no")

    if not gp_no:
        return jsonify({"error": "gp_no is required"}), 400
    if sr_no is None:
        return jsonify({"error": "sr_no is required"}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # 1. Delete the target row
        cursor.execute("""
            DELETE FROM zgima_gatepass_det_TEMP
            WHERE gp_no = :gp_no AND sr_no = :sr_no
        """, {"gp_no": gp_no, "sr_no": int(sr_no)})

        if cursor.rowcount == 0:
            return jsonify({"error": "Record not found"}), 404

        # 2. Renumber all rows with sr_no > deleted sr_no (shift down by 1)
        cursor.execute("""
            UPDATE zgima_gatepass_det_TEMP
               SET sr_no = sr_no - 1
             WHERE gp_no = :gp_no AND sr_no > :sr_no
        """, {"gp_no": gp_no, "sr_no": int(sr_no)})

        connection.commit()
        return jsonify({"success": True, "gp_no": gp_no, "sr_no": int(sr_no)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Save IN/OUT entry (Gatepass In Out Entry – OK button)
# Updates in_qty, in_dttime, inward_no, repair_chgs on a detail row.
# Mirrors VB: cmd_det_ok_Click → UPDATE zgima_gatepass_det_temp
# ─────────────────────────────────────────
@app.route("/api/gatepass/save_inout", methods=["POST"])
def save_gatepass_inout():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    gp_no       = data.get("gp_no", "").strip()
    sr_no       = data.get("sr_no")
    in_qty      = data.get("in_qty")
    # in_dttime: convert "DD/MM/YYYY HH-MM AM/PM" → "DD/MON/YY HH:MM" for DB storage
    in_dttime   = fmt_in_dttime(data.get("in_dttime", "").strip())
    inward_no   = data.get("inward_no", "").strip()
    repair_chgs = data.get("repair_chgs", "0").strip()

    if not gp_no:
        return jsonify({"error": "GP No is required"}), 400
    if sr_no is None:
        return jsonify({"error": "Please select a row from the grid"}), 400
    if not inward_no:
        return jsonify({"error": "Inward No cannot be empty"}), 400

    try:
        in_qty_val = float(in_qty) if in_qty not in (None, "", " ") else 0.0
    except (ValueError, TypeError):
        return jsonify({"error": "IN Quantity must be a number"}), 400

    if in_qty_val > 0 and not in_dttime:
        return jsonify({"error": "Please enter IN Date & Time to save the entry"}), 400

    try:
        repair_chgs_val = float(repair_chgs) if repair_chgs not in (None, "", " ") else 0.0
    except (ValueError, TypeError):
        repair_chgs_val = 0.0

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT NVL(quantity, 0)
            FROM zgima_gatepass_det_TEMP
            WHERE TRIM(gp_no) = :gp_no AND sr_no = :sr_no
        """, {"gp_no": gp_no, "sr_no": int(sr_no)})
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Detail row not found"}), 404

        max_qty = float(row[0]) if row[0] is not None else 0.0
        if in_qty_val > max_qty:
            return jsonify({"error": f"IN Quantity ({in_qty_val}) cannot exceed Out Quantity ({max_qty})"}), 400

        # in_dttime is VARCHAR — stored as "DD/MON/YY HH:MM" e.g. "25/MAR/26 14:30"
        cursor.execute("""
            UPDATE zgima_gatepass_det_TEMP
               SET in_qty      = :in_qty,
                   in_dttime   = :in_dttime,
                   inward_no   = :inward_no,
                   repair_chgs = :repair_chgs,
                   edit_user   = :edit_user
             WHERE TRIM(gp_no) = :gp_no
               AND sr_no = :sr_no
        """, {
            "in_qty":      in_qty_val,
            "in_dttime":   in_dttime,
            "inward_no":   inward_no,
            "repair_chgs": repair_chgs_val,
            "edit_user":   session.get("user", ""),
            "gp_no":       gp_no,
            "sr_no":       int(sr_no),
        })

        if cursor.rowcount == 0:
            return jsonify({"error": "No record updated – row not found"}), 404

        connection.commit()
        return jsonify({"success": True, "gp_no": gp_no, "sr_no": int(sr_no)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# API: Current server datetime
# Returns "formatted" as "DD/MM/YYYY HH-MM" for VARCHAR in_dttime field
# ─────────────────────────────────────────
@app.route("/api/now")
def api_now():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    now = datetime.now()
    return jsonify({
        "formatted": now.strftime("%d/%m/%Y %I-%M %p"),
        "date":      now.strftime("%Y-%m-%d"),
        "time":      now.strftime("%I:%M %p")
    })


# ─────────────────────────────────────────
# REPORT: Gatepass Print – filter page
# ─────────────────────────────────────────
@app.route("/report/gatepass_print")
def gatepass_print():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "gatepass_print.html",
        site_code=session.get("site_code"),
        username=session.get("user"),
    )


# ─────────────────────────────────────────
# API: Fetch gatepasses for printing
# Query params:
#   site_code, date_from, date_to,
#   dept_from, dept_to,
#   gp_from,   gp_to
# Returns list of {header, details} dicts
# ─────────────────────────────────────────
@app.route("/api/report/gatepass")
def api_report_gatepass():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    site_code = request.args.get("site_code", "").strip() or session.get("site_code", "")
    gp_from   = request.args.get("gp_from",   "").strip()
    gp_to     = request.args.get("gp_to",     "").strip()
    date_from = request.args.get("date_from", "").strip()   # DD/MM/YY
    date_to   = request.args.get("date_to",   "").strip()
    dept_from = request.args.get("dept_from", "").strip()
    dept_to   = request.args.get("dept_to",   "").strip()


    connection = None
    cursor     = None
    try:
        connection = get_db_connection()
        cursor     = connection.cursor()

        # ── build header WHERE clauses ──────────────────────────
        where  = ["TRIM(h.site_code) = :site_code"]
        params = {"site_code": site_code}
        
        if gp_from and gp_to:
            where.append("TRIM(h.gp_no) BETWEEN :gp_from AND :gp_to")
            params["gp_from"] = gp_from
            params["gp_to"]   = gp_to

        if date_from and date_to:
            where.append(
                "TRUNC(TO_DATE(h.gp_date,'DD/MM/YY')) BETWEEN "
                "TO_DATE(:date_from,'DD/MM/YY') AND TO_DATE(:date_to,'DD/MM/YY')"
            )
            params["date_from"] = date_from
            params["date_to"]   = date_to

        if dept_from and dept_to:
            where.append("TRIM(h.dept_code) BETWEEN :dept_from AND :dept_to")
            params["dept_from"] = dept_from
            params["dept_to"]   = dept_to


        header_sql = f"""
            SELECT h.gp_no, h.gp_date, h.gp_type, h.trans_type,
                   h.supp_code, h.supp_name, h.addr1, h.addr2, h.addr3,
                   h.city, h.pin, h.phone, h.email_addr,
                   h.dept_code, h.vehicle_no, h.valid_date,
                   h.carry_out_by, h.sec_remark, h.prep_by,
                   h.conf_by, h.conf_date,
                   h.tc1, h.tc2, h.tc3, h.tc4, h.tc5, h.tc6,
                   h.courier_nm, h.docket_no, h.confirmed,
                   h.dept_cd_metr
            FROM zgima_gatepass_TEMP h
            WHERE {' AND '.join(where)}
            ORDER BY h.gp_no
        """
        cursor.execute(header_sql, params)
        hcols   = [c[0].lower() for c in cursor.description]
        headers = [dict(zip(hcols, r)) for r in cursor.fetchall()]

        # Serialize dates
        for h in headers:
            for k, v in h.items():
                if isinstance(v, (datetime,)):
                    h[k] = v.strftime("%d/%m/%Y")
                elif v is None:
                    h[k] = ""

        # ── fetch details for every gp_no ──────────────────────
        result = []
        for h in headers:
            gp_no = h["gp_no"]
            cursor.execute("""
                SELECT sr_no, item_code, item_descr, item_descr_add,
                       uom, quantity, out_qty, in_qty,
                       rep_remark, mc_code,
                       inward_no, repair_chgs, in_dttime
                FROM zgima_gatepass_det_TEMP
                WHERE TRIM(gp_no) = :gp_no
                ORDER BY sr_no
            """, {"gp_no": gp_no})
            dcols   = [c[0].lower() for c in cursor.description]
            details = [dict(zip(dcols, r)) for r in cursor.fetchall()]
            for d in details:
                for k, v in d.items():
                    if isinstance(v, datetime):
                        d[k] = v.strftime("%d/%m/%Y %H:%M")
                    elif v is None:
                        d[k] = ""
            result.append({"header": h, "details": details})

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



# ─────────────────────────────────────────
# REPORT: Pending Item Register – filter page
# ─────────────────────────────────────────
@app.route("/report/pending_register")
def pending_register():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "pending_register.html",
        site_code=session.get("site_code"),
        username=session.get("user"),
    )


# ─────────────────────────────────────────
# API: Pending Item Register data
# Query params:
#   as_gp_date_to  – DD/MM/YY  (required)
#   dept_code_fr   – department from (optional, defaults to first dept)
#   dept_code_to   – department to   (optional, defaults to last dept)
# Returns list of pending gatepass rows (RETURNABLE, pending qty > 0)
# ─────────────────────────────────────────
@app.route("/api/report/pending_register")
def api_report_pending_register():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    site_code      = session.get("site_code", "")
    as_gp_date_to  = request.args.get("as_gp_date_to", "").strip()   # DD/MM/YY
    dept_code_fr   = request.args.get("dept_code_fr",  "").strip()
    dept_code_to   = request.args.get("dept_code_to",  "").strip()

    if not as_gp_date_to:
        return jsonify({"error": "as_gp_date_to is required"}), 400

    # Default dept range to cover everything
    if not dept_code_fr:
        dept_code_fr = " "          # low sentinel
    if not dept_code_to:
        dept_code_to = "ZZZZZZZZZZ" # high sentinel

    connection = None
    cursor     = None
    try:
        connection = get_db_connection()
        cursor     = connection.cursor()

        sql = """
    SELECT
        A.GP_NO,
        A.GP_DATE,
        A.SUPP_NAME,
        'SYSTEMS'                                            AS DEPT_DESCR,
        A.TRANS_TYPE,
        A.CARRY_OUT_BY,
        A.VALID_DATE,
        B.SR_NO,
        NVL(B.ITEM_CODE,' ')                                         AS ITEM_CODE,
        NVL(B.ITEM_DESCR,' ')                                        AS ITEM_DESCR,
        B.UOM,
        NVL(B.QUANTITY,0)                                            AS QUANTITY,
        NVL(B.IN_QTY,0)                                              AS IN_QTY,
        SITE.DESCR                                                   AS SITE_DESCR,
        A.SITE_CODE,
        A.GP_TYPE,
        A.DEPT_CODE,
        TO_DATE(:AS_GP_DATE_TO,'DD/MM/RR') - TO_DATE(A.VALID_DATE,'DD/MM/RR')  AS DAYS_VALID,
        TO_DATE(:AS_GP_DATE_TO,'DD/MM/RR') - TO_DATE(A.GP_DATE,'DD/MM/RR')     AS DAYS_GP
    FROM ZGIMA_GATEPASS_TEMP A
    LEFT JOIN ZGIMA_GATEPASS_DET_TEMP B ON A.GP_NO = B.GP_NO
    LEFT JOIN SITE       ON A.SITE_CODE  = SITE.SITE_CODE
    WHERE UPPER(TRIM(A.GP_TYPE)) IN ('R-OUT', 'RETURNABLE', 'RETURNABLE OUTSIDE')
     AND UPPER(TRIM(A.CONFIRMED))   = 'Y'
      AND ( NVL(B.QUANTITY,0) - NVL(B.IN_QTY,0) ) > 0
      AND A.SITE_CODE  = :SITE_CODE
      AND TO_DATE(A.GP_DATE,'DD/MM/RR') <= TO_DATE(:AS_GP_DATE_TO,'DD/MM/RR')

    ORDER BY A.GP_NO
"""
        cursor.execute(sql, {
            "AS_GP_DATE_TO": as_gp_date_to,
            "SITE_CODE":     site_code
            #"DEPT_CODE_FR":  dept_code_fr,
           # "DEPT_CODE_TO":  dept_code_to,
        })

        columns = [col[0].lower() for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Serialise any remaining datetime / Decimal objects
        from decimal import Decimal
        for row in rows:
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.strftime("%d/%m/%Y")
                elif isinstance(v, Decimal):
                    row[k] = float(v)
                elif v is None:
                    row[k] = ""

        return jsonify(rows)

    except Exception as e:
        import traceback
        print("=== PENDING REGISTER ERROR ===")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ─────────────────────────────────────────
# REPORT: Department Wise Pending Item Register – filter page
# ─────────────────────────────────────────
@app.route("/report/dept_pending_register")
def dept_pending_register():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "dept_pending_register.html",
        site_code=session.get("site_code"),
        username=session.get("user"),
    )


# ─────────────────────────────────────────
# API: Department Wise Pending Item Register data
# Query params:
#   as_gp_date_to  – DD/MM/YY  (required)
#   dept_code_fr   – department from (optional)
#   dept_code_to   – department to   (optional)
# Returns list of pending gatepass rows ordered by DEPT_CODE, GP_NO
# ─────────────────────────────────────────
@app.route("/api/report/dept_pending_register")
def api_report_dept_pending_register():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    site_code     = session.get("site_code", "")
    as_gp_date_to = request.args.get("as_gp_date_to", "").strip()   # DD/MM/YY
    dept_code_fr  = request.args.get("dept_code_fr",  "").strip()
    dept_code_to  = request.args.get("dept_code_to",  "").strip()

    if not as_gp_date_to:
        return jsonify({"error": "as_gp_date_to is required"}), 400

    # Default dept range to cover everything
    if not dept_code_fr:
        dept_code_fr = " "           # low sentinel
    if not dept_code_to:
        dept_code_to = "ZZZZZZZZZZ"  # high sentinel

    connection = None
    cursor     = None
    try:
        connection = get_db_connection()
        cursor     = connection.cursor()

        sql = """
    SELECT
        A.GP_NO,
        A.GP_DATE,
        A.SUPP_NAME,
        DEPARTMENT.DESCR                                             AS DEPT_DESCR,
        A.TRANS_TYPE,
        A.CARRY_OUT_BY,
        A.VALID_DATE,
        B.SR_NO,
        NVL(B.ITEM_CODE,  ' ')                                       AS ITEM_CODE,
        NVL(B.ITEM_DESCR, ' ')                                       AS ITEM_DESCR,
        B.UOM,
        NVL(B.QUANTITY, 0)                                           AS QUANTITY,
        NVL(B.IN_QTY,   0)                                          AS IN_QTY,
        B.IN_DTTIME,
        SITE.DESCR                                                   AS SITE_DESCR,
        A.SITE_CODE,
        A.GP_TYPE,
        A.DEPT_CODE,
        TO_DATE(:AS_GP_DATE_TO,'DD/MM/RR') - TO_DATE(A.VALID_DATE,'DD/MM/RR') AS DAYS_VALID,
        TO_DATE(:AS_GP_DATE_TO,'DD/MM/RR') - TO_DATE(A.GP_DATE,  'DD/MM/RR') AS DAYS_GP
    FROM  ZGIMA_GATEPASS_TEMP     A
    LEFT JOIN ZGIMA_GATEPASS_DET_TEMP B ON A.GP_NO      = B.GP_NO
    LEFT JOIN SITE                      ON A.SITE_CODE  = SITE.SITE_CODE
    LEFT JOIN DEPARTMENT                ON A.DEPT_CODE  = DEPARTMENT.DEPT_CODE
    WHERE UPPER(TRIM(A.GP_TYPE)) IN ('R-OUT', 'RETURNABLE', 'RETURNABLE OUTSIDE')
          AND UPPER(TRIM(A.CONFIRMED))   = 'Y'
      AND ( NVL(B.QUANTITY,0) - NVL(B.IN_QTY,0) ) > 0
      AND A.SITE_CODE  = :SITE_CODE
      AND TO_DATE(A.GP_DATE,'DD/MM/RR') <= SYSDATE
    ORDER BY A.DEPT_CODE, A.GP_NO
"""
        cursor.execute(sql, {
            "AS_GP_DATE_TO": as_gp_date_to,
            "SITE_CODE":     site_code,
            #"DEPT_CODE_FR":  dept_code_fr,
            #"DEPT_CODE_TO":  dept_code_to,
        })

        columns = [col[0].lower() for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Serialise datetime / Decimal objects
        from decimal import Decimal
        for row in rows:
            for k, v in row.items():
                if isinstance(v, datetime):
                    row[k] = v.strftime("%d/%m/%Y")
                elif isinstance(v, Decimal):
                    row[k] = float(v)
                elif v is None:
                    row[k] = ""

        return jsonify(rows)

    except Exception as e:
        import traceback
        print("=== DEPT PENDING REGISTER ERROR ===")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ─────────────────────────────────────────
# REPORT: GP Type Wise Pending Item Register – filter page
# ─────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# ADD THESE TWO BLOCKS TO app.py  (paste before the  if __name__ == '__main__':
# line at the very end)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────
# REPORT: Gatepass In-Out Register – filter page
# ─────────────────────────────────────────
@app.route("/report/gp_inout_register")
def gp_inout_register():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template(
        "gp_inout_register.html",
        site_code=session.get("site_code"),
        username=session.get("user"),
    )


# ─────────────────────────────────────────
# API: Gatepass In-Out Register data
#
# Query params:
#   date_from   – DD/MM/YY   (required)  – GP Date from
#   date_to     – DD/MM/YY   (required)  – GP Date to
#   gp_from     – text       (optional)  – GP No from
#   gp_to       – text       (optional)  – GP No to
#   dept_from   – text       (optional)  – Department from
#   dept_to     – text       (optional)  – Department to
#
# Returns list of {header, details} dicts ordered by gp_type then gp_no,
# matching the PDF grouping: Non Returnable first, then Returnable.
# Only confirmed gatepasses (confirmed = 'Y') are included — same as the PDF.
# ─────────────────────────────────────────
@app.route("/api/report/gp_inout_register")
def api_report_gp_inout_register():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    site_code = request.args.get("site_code", "").strip() or session.get("site_code", "")
    date_from = request.args.get("date_from", "").strip()   # DD/MM/YY
    date_to   = request.args.get("date_to",   "").strip()
    gp_from   = request.args.get("gp_from",   "").strip()
    gp_to     = request.args.get("gp_to",     "").strip()
    dept_from = request.args.get("dept_from", "").strip()
    dept_to   = request.args.get("dept_to",   "").strip()

    if not date_from or not date_to:
        return jsonify({"error": "date_from and date_to are required"}), 400

    connection = None
    cursor     = None
    try:
        connection = get_db_connection()
        cursor     = connection.cursor()

        # ── Build WHERE clauses ──────────────────────────────────────────────
        where  = [
            "TRIM(h.site_code) = :site_code",
            "UPPER(TRIM(h.confirmed)) = 'Y'",
            "TRUNC(TO_DATE(h.gp_date,'DD/MM/YY')) BETWEEN "
            "TO_DATE(:date_from,'DD/MM/YY') AND TO_DATE(:date_to,'DD/MM/YY')",
        ]
        params = {
            "site_code": site_code,
            "date_from": date_from,
            "date_to":   date_to,
        }

        if gp_from and gp_to:
            where.append("TRIM(h.gp_no) BETWEEN :gp_from AND :gp_to")
            params["gp_from"] = gp_from
            params["gp_to"]   = gp_to

        if dept_from and dept_to:
            where.append("TRIM(h.dept_code) BETWEEN :dept_from AND :dept_to")
            params["dept_from"] = dept_from
            params["dept_to"]   = dept_to

        # ── Header query — ordered by gp_type then gp_no so the PDF grouping
        #    (Non Returnable → Returnable) is naturally preserved server-side ─
        header_sql = f"""
            SELECT
                h.gp_no, h.gp_date, h.gp_type,
                h.supp_code, h.supp_name,
                h.dept_code,
                h.trans_type, h.vehicle_no,
                h.carry_out_by, h.valid_date,
                h.confirmed
            FROM zgima_gatepass_TEMP h
            WHERE {' AND '.join(where)}
            ORDER BY h.gp_type, h.gp_no
        """
        cursor.execute(header_sql, params)
        hcols   = [c[0].lower() for c in cursor.description]
        headers = [dict(zip(hcols, r)) for r in cursor.fetchall()]

        # Serialise date objects
        for h in headers:
            for k, v in h.items():
                if isinstance(v, datetime):
                    h[k] = v.strftime("%d/%m/%Y")
                elif v is None:
                    h[k] = ""

        # ── Fetch detail rows for every gp_no ────────────────────────────────
        result = []
        for h in headers:
            gp_no = h["gp_no"]
            cursor.execute("""
                SELECT sr_no, item_code, item_descr, item_descr_add,
                       uom, quantity, out_qty, in_qty,
                       rep_remark, mc_code, inward_no, repair_chgs, in_dttime
                FROM zgima_gatepass_det_TEMP
                WHERE TRIM(gp_no) = :gp_no
                ORDER BY sr_no
            """, {"gp_no": gp_no})
            dcols   = [c[0].lower() for c in cursor.description]
            details = [dict(zip(dcols, r)) for r in cursor.fetchall()]
            for d in details:
                for k, v in d.items():
                    if isinstance(v, datetime):
                        d[k] = v.strftime("%d/%m/%Y %H:%M")
                    elif v is None:
                        d[k] = ""
            result.append({"header": h, "details": details})

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)