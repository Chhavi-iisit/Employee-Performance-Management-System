from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid


app = Flask(__name__)

# ==================================================
# FLASK SESSION
# ==================================================

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "appraisex-secret-key"
)


# ==================================================
# FILE UPLOAD CONFIGURATION
# ==================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "documents"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# ==================================================
# DATABASE CONNECTION
# ==================================================
def get_db_connection():

    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME", "employee_appraisal")
    )


# ==================================================
# AUDIT LOG HELPER
# ==================================================

def create_audit_log(
    cursor,
    user_id,
    action,
    entity_type,
    entity_id,
    description
):

    cursor.execute("""
        INSERT INTO audit_logs
        (
            user_id,
            action,
            entity_type,
            entity_id,
            description
        )
        VALUES
        (%s, %s, %s, %s, %s)
    """, (
        user_id,
        action,
        entity_type,
        entity_id,
        description
    ))


# ==================================================
# SESSION HELPERS
# ==================================================

def is_logged_in():
    return bool(session.get("user_id"))


def require_role(allowed_roles):

    if not session.get("user_id"):
        return jsonify({
            "success": False,
            "message": "User not logged in"
        }), 401

    if session.get("role") not in allowed_roles:
        return jsonify({
            "success": False,
            "message": "Access denied"
        }), 403

    return None


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    return render_template("login.html")


@app.route("/register")
def registration_page():
    if session.get("user_id"):
        return redirect(url_for("employee_dashboard" if session.get("role") == "employee" else "manager_dashboard" if session.get("role") == "manager" else "admin_dashboard"))
    return render_template("register.html")


# ==================================================
# EMPLOYEE DASHBOARD
# ==================================================

@app.route("/employee-dashboard")
def employee_dashboard():

    if not session.get("user_id"):
        return render_template("login.html")

    if session.get("role") != "employee":
        return "Access denied", 403

    return render_template("dashboard.html")


# ==================================================
# MANAGER DASHBOARD
# ==================================================

@app.route("/manager-dashboard")
def manager_dashboard():

    if not session.get("user_id"):
        return render_template("login.html")

    if session.get("role") != "manager":
        return "Access denied", 403

    return render_template("manager_dashboard.html")


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin-dashboard")
def admin_dashboard():

    if not session.get("user_id"):
        return render_template("login.html")

    if session.get("role") != "admin":
        return "Access denied", 403

    return render_template("admin_dashboard.html")


# ==================================================
# GET ALL EMPLOYEES
# ==================================================

@app.route("/api/employees", methods=["GET"])
def get_employees():

    check = require_role(["manager", "admin"])

    if check:
        return check

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        if session.get("role") == "manager":

            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.user_id,
                    u.name,
                    u.email,
                    e.employee_code,
                    e.department,
                    e.designation,
                    e.joining_date,
                    e.manager_id

                FROM employees e

                JOIN users u
                    ON e.user_id = u.user_id

                WHERE e.manager_id = %s

                ORDER BY e.employee_id
            """, (session.get("user_id"),))

        else:

            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.user_id,
                    u.name,
                    u.email,
                    e.employee_code,
                    e.department,
                    e.designation,
                    e.joining_date,
                    e.manager_id

                FROM employees e

                JOIN users u
                    ON e.user_id = u.user_id

                ORDER BY e.employee_id
            """)

        employees = cursor.fetchall()

        return jsonify({
            "success": True,
            "value": employees,
            "Count": len(employees)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "value": [],
            "Count": 0,
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET PENDING DOCUMENT COUNT
# ==================================================

@app.route("/api/pending-documents", methods=["GET"])
def get_pending_documents():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT COUNT(*)

            FROM documents d

            JOIN employees e
                ON d.employee_id = e.employee_id

            WHERE
                e.manager_id = %s

                AND d.status IN (
                    'pending',
                    'resubmitted'
                )
        """, (user_id,))

        result = cursor.fetchone()

        return jsonify({
            "success": True,
            "count": result[0] if result else 0
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "count": 0,
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET PENDING DOCUMENTS LIST
# ==================================================

@app.route("/api/pending-documents-list", methods=["GET"])
def get_pending_documents_list():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                d.document_id,
                d.employee_id,

                u.name AS employee_name,
                u.email AS employee_email,

                d.document_type,
                d.document_name,
                d.document_path,
                d.status,
                d.manager_comments,
                d.submitted_at,
                d.updated_at

            FROM documents d

            JOIN employees e
                ON d.employee_id = e.employee_id

            JOIN users u
                ON e.user_id = u.user_id

            WHERE
                e.manager_id = %s

                AND d.status IN (
                    'pending',
                    'resubmitted'
                )

            ORDER BY d.submitted_at DESC
        """, (user_id,))

        documents = cursor.fetchall()

        return jsonify({
            "success": True,
            "documents": documents,
            "count": len(documents)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET LOGGED-IN EMPLOYEE DOCUMENTS
# ==================================================

@app.route("/api/my-documents", methods=["GET"])
def get_my_documents():

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                d.document_id,
                d.employee_id,
                d.document_type,
                d.document_name,
                d.document_path,
                d.status,
                d.manager_comments,
                d.submitted_at,
                d.updated_at

            FROM documents d

            JOIN employees e
                ON d.employee_id = e.employee_id

            WHERE e.user_id = %s

            ORDER BY d.submitted_at DESC
        """, (user_id,))

        documents = cursor.fetchall()

        return jsonify({
            "success": True,
            "documents": documents,
            "count": len(documents)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# RESUBMIT REJECTED DOCUMENT
# ==================================================

@app.route(
    "/api/resubmit-document/<int:document_id>",
    methods=["POST"]
)
def resubmit_document(document_id):

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    uploaded_file = request.files.get("document")

    if not uploaded_file:
        return jsonify({
            "success": False,
            "message": "Please select a document"
        }), 400

    original_filename = secure_filename(
        uploaded_file.filename
    )

    if not original_filename:
        return jsonify({
            "success": False,
            "message": "Invalid file name"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                d.document_id,
                d.employee_id,
                d.status

            FROM documents d

            JOIN employees e
                ON d.employee_id = e.employee_id

            WHERE
                d.document_id = %s
                AND e.user_id = %s
        """, (
            document_id,
            user_id
        ))

        document = cursor.fetchone()

        if not document:
            return jsonify({
                "success": False,
                "message": "Document not found"
            }), 404

        if document["status"] != "rejected":
            return jsonify({
                "success": False,
                "message": "Only rejected documents can be resubmitted"
            }), 400

        unique_filename = (
            uuid.uuid4().hex
            + "_"
            + original_filename
        )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            unique_filename
        )

        uploaded_file.save(file_path)

        database_path = (
            "uploads/documents/"
            + unique_filename
        )

        cursor.execute("""
            UPDATE documents

            SET
                document_name = %s,
                document_path = %s,
                status = 'pending',
                manager_comments = NULL,
                updated_at = CURRENT_TIMESTAMP

            WHERE document_id = %s
        """, (
            original_filename,
            database_path,
            document_id
        ))

        create_audit_log(
            cursor,
            user_id,
            "DOCUMENT_RESUBMITTED",
            "document",
            document_id,
            "Employee resubmitted a rejected document."
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Document resubmitted successfully",
            "document_id": document_id,
            "status": "pending"
        })

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    except Exception as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "File upload failed",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# REVIEW DOCUMENT
# ==================================================

@app.route("/api/document-review", methods=["POST"])
def review_document():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    document_id = data.get("document_id")
    action = data.get("action")
    comments = data.get("comments")

    if not document_id:
        return jsonify({
            "success": False,
            "message": "Document ID is required"
        }), 400

    if action not in [
        "verified",
        "rejected",
        "requested_resubmission"
    ]:
        return jsonify({
            "success": False,
            "message": "Invalid document review action"
        }), 400

    comments = (
        comments.strip()
        if isinstance(comments, str)
        else None
    )

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                d.document_id,
                d.employee_id,
                d.status,
                e.manager_id

            FROM documents d

            JOIN employees e
                ON d.employee_id = e.employee_id

            WHERE
                d.document_id = %s
                AND e.manager_id = %s
        """, (
            document_id,
            user_id
        ))

        document = cursor.fetchone()

        if not document:
            return jsonify({
                "success": False,
                "message": "Document not found or access denied"
            }), 404

        if document["status"] not in [
            "pending",
            "resubmitted"
        ]:
            return jsonify({
                "success": False,
                "message": "This document has already been reviewed"
            }), 400

        if action == "verified":
            new_status = "verified"
        elif action == "rejected":
            new_status = "rejected"
        else:
            new_status = "resubmitted"

        cursor.execute("""
            UPDATE documents

            SET
                status = %s,
                manager_comments = %s,
                updated_at = CURRENT_TIMESTAMP

            WHERE document_id = %s
        """, (
            new_status,
            comments,
            document_id
        ))

        cursor.execute("""
            INSERT INTO document_verification
            (
                document_id,
                manager_id,
                action,
                comments
            )
            VALUES
            (%s, %s, %s, %s)
        """, (
            document_id,
            user_id,
            action,
            comments
        ))

        create_audit_log(
            cursor,
            user_id,
            "DOCUMENT_REVIEWED",
            "document",
            document_id,
            f"Manager performed document action: {action}"
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Document reviewed successfully",
            "document_id": document_id,
            "status": new_status,
            "action": action
        })

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET PENDING APPRAISALS COUNT
# ==================================================

@app.route("/api/pending-appraisals", methods=["GET"])
def get_pending_appraisals():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT COUNT(*)

            FROM appraisals

            WHERE
                manager_id = %s

                AND status IN (
                    'submitted',
                    'under_review',
                    'resubmitted'
                )
        """, (user_id,))

        result = cursor.fetchone()

        return jsonify({
            "success": True,
            "count": result[0] if result else 0
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "count": 0,
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET PENDING APPRAISALS LIST
# ==================================================

@app.route("/api/pending-appraisals-list", methods=["GET"])
def get_pending_appraisals_list():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                a.appraisal_id,
                a.employee_id,
                a.manager_id,
                a.appraisal_period,
                a.overall_rating,
                a.employee_comments,
                a.manager_comments,
                a.status,
                a.created_at,
                a.updated_at,

                u.name AS employee_name,
                u.email AS employee_email,

                e.employee_code,
                e.department,
                e.designation

            FROM appraisals a

            JOIN employees e
                ON a.employee_id = e.employee_id

            JOIN users u
                ON e.user_id = u.user_id

            WHERE
                a.manager_id = %s

                AND a.status IN (
                    'submitted',
                    'under_review',
                    'resubmitted'
                )

            ORDER BY a.created_at ASC
        """, (user_id,))

        appraisals = cursor.fetchall()

        return jsonify({
            "success": True,
            "appraisals": appraisals,
            "count": len(appraisals)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# MANAGER REVIEW APPRAISAL
# ==================================================

@app.route("/api/appraisal-review", methods=["POST"])
def review_appraisal():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    appraisal_id = data.get("appraisal_id")
    action = data.get("action")
    manager_comments = data.get("manager_comments")

    if not appraisal_id:
        return jsonify({
            "success": False,
            "message": "Appraisal ID is required"
        }), 400

    if action not in [
        "approved",
        "rejected"
    ]:
        return jsonify({
            "success": False,
            "message": "Action must be approved or rejected"
        }), 400

    if (
        not manager_comments
        or not manager_comments.strip()
    ):
        return jsonify({
            "success": False,
            "message": "Manager comments are required"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                appraisal_id,
                employee_id,
                manager_id,
                status

            FROM appraisals

            WHERE
                appraisal_id = %s
                AND manager_id = %s
        """, (
            appraisal_id,
            user_id
        ))

        appraisal = cursor.fetchone()

        if not appraisal:
            return jsonify({
                "success": False,
                "message": "Appraisal not found or access denied"
            }), 404

        if appraisal["status"] not in [
            "submitted",
            "under_review",
            "resubmitted"
        ]:
            return jsonify({
                "success": False,
                "message": "This appraisal has already been reviewed"
            }), 400

        cursor.execute("""
            UPDATE appraisals

            SET
                status = %s,
                manager_comments = %s,
                updated_at = CURRENT_TIMESTAMP

            WHERE appraisal_id = %s
        """, (
            action,
            manager_comments.strip(),
            appraisal_id
        ))

        create_audit_log(
            cursor,
            user_id,
            "APPRAISAL_REVIEWED",
            "appraisal",
            appraisal_id,
            f"Manager marked appraisal as {action}."
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": (
                "Appraisal approved successfully"
                if action == "approved"
                else "Appraisal rejected successfully"
            ),
            "appraisal_id": appraisal_id,
            "status": action
        })

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# SUBMIT EMPLOYEE APPEAL
# ==================================================

@app.route("/api/appeals", methods=["POST"])
def submit_appeal():

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    appraisal_id = data.get("appraisal_id")
    reason = data.get("reason")

    if not appraisal_id:
        return jsonify({
            "success": False,
            "message": "Appraisal ID is required"
        }), 400

    if not reason or not reason.strip():
        return jsonify({
            "success": False,
            "message": "Appeal reason is required"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT employee_id

            FROM employees

            WHERE user_id = %s
        """, (user_id,))

        employee = cursor.fetchone()

        if not employee:
            return jsonify({
                "success": False,
                "message": "Employee record not found"
            }), 404

        employee_id = employee["employee_id"]

        cursor.execute("""
            SELECT
                appraisal_id,
                employee_id,
                manager_id,
                status

            FROM appraisals

            WHERE
                appraisal_id = %s
                AND employee_id = %s
        """, (
            appraisal_id,
            employee_id
        ))

        appraisal = cursor.fetchone()

        if not appraisal:
            return jsonify({
                "success": False,
                "message": "Appraisal not found for this employee"
            }), 404

        if appraisal["status"] != "rejected":
            return jsonify({
                "success": False,
                "message": "Only rejected appraisals can be appealed"
            }), 400

        cursor.execute("""
            SELECT appeal_id

            FROM appeals

            WHERE
                appraisal_id = %s
                AND employee_id = %s
                AND status = 'pending'
        """, (
            appraisal_id,
            employee_id
        ))

        existing_appeal = cursor.fetchone()

        if existing_appeal:
            return jsonify({
                "success": False,
                "message": (
                    "You already have a pending appeal "
                    "for this appraisal"
                ),
                "appeal_id": existing_appeal["appeal_id"]
            }), 400

        cursor.execute("""
            INSERT INTO appeals
            (
                appraisal_id,
                employee_id,
                reason,
                status
            )

            VALUES
            (
                %s,
                %s,
                %s,
                'pending'
            )
        """, (
            appraisal_id,
            employee_id,
            reason.strip()
        ))

        appeal_id = cursor.lastrowid

        create_audit_log(
            cursor,
            user_id,
            "APPEAL_SUBMITTED",
            "appeal",
            appeal_id,
            "Employee submitted an appraisal appeal."
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Appeal submitted successfully",
            "appeal_id": appeal_id,
            "appraisal_id": appraisal_id,
            "employee_id": employee_id,
            "status": "pending"
        }), 201

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET MY APPEALS
# ==================================================

@app.route("/api/my-appeals", methods=["GET"])
def get_my_appeals():

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                ap.appeal_id,
                ap.appraisal_id,
                ap.employee_id,
                ap.reason,
                ap.status,
                ap.manager_response,
                ap.created_at,
                ap.updated_at,

                a.appraisal_period,
                a.overall_rating,
                a.manager_comments

            FROM appeals ap

            JOIN appraisals a
                ON ap.appraisal_id = a.appraisal_id

            JOIN employees e
                ON ap.employee_id = e.employee_id

            WHERE e.user_id = %s

            ORDER BY ap.created_at DESC
        """, (user_id,))

        appeals = cursor.fetchall()

        return jsonify({
            "success": True,
            "appeals": appeals,
            "count": len(appeals)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error"
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# GET PENDING APPEALS FOR MANAGER
# ==================================================

@app.route("/api/pending-appeals", methods=["GET"])
def get_pending_appeals():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                ap.appeal_id,
                ap.appraisal_id,
                ap.employee_id,

                u.name AS employee_name,
                u.email AS employee_email,

                ap.reason,
                ap.status,
                ap.manager_response,
                ap.created_at,
                ap.updated_at,

                a.appraisal_period,
                a.overall_rating,
                a.manager_comments

            FROM appeals ap

            JOIN employees e
                ON ap.employee_id = e.employee_id

            JOIN users u
                ON e.user_id = u.user_id

            JOIN appraisals a
                ON ap.appraisal_id = a.appraisal_id

            WHERE
                ap.status = 'pending'
                AND a.manager_id = %s

            ORDER BY ap.created_at ASC
        """, (user_id,))

        appeals = cursor.fetchall()

        return jsonify({
            "success": True,
            "appeals": appeals,
            "count": len(appeals)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error"
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# MANAGER REVIEW APPEAL
# ==================================================

@app.route("/api/appeal-review", methods=["POST"])
def review_appeal():

    check = require_role(["manager"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    appeal_id = data.get("appeal_id")
    action = data.get("action")
    manager_response = data.get("manager_response")

    if not appeal_id:
        return jsonify({
            "success": False,
            "message": "Appeal ID is required"
        }), 400

    if action not in [
        "approved",
        "rejected"
    ]:
        return jsonify({
            "success": False,
            "message": "Action must be approved or rejected"
        }), 400

    if (
        not manager_response
        or not manager_response.strip()
    ):
        return jsonify({
            "success": False,
            "message": "Manager response is required"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                ap.appeal_id,
                ap.appraisal_id,
                ap.employee_id,
                ap.status,
                a.manager_id

            FROM appeals ap

            JOIN appraisals a
                ON ap.appraisal_id = a.appraisal_id

            WHERE
                ap.appeal_id = %s
                AND a.manager_id = %s
        """, (
            appeal_id,
            user_id
        ))

        appeal = cursor.fetchone()

        if not appeal:
            return jsonify({
                "success": False,
                "message": "Appeal not found or access denied"
            }), 404

        if appeal["status"] != "pending":
            return jsonify({
                "success": False,
                "message": "This appeal has already been reviewed"
            }), 400

        cursor.execute("""
            UPDATE appeals

            SET
                status = %s,
                manager_response = %s,
                updated_at = CURRENT_TIMESTAMP

            WHERE appeal_id = %s
        """, (
            action,
            manager_response.strip(),
            appeal_id
        ))

        create_audit_log(
            cursor,
            user_id,
            "APPEAL_REVIEWED",
            "appeal",
            appeal_id,
            f"Manager marked appeal as {action}."
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": (
                "Appeal approved successfully"
                if action == "approved"
                else "Appeal rejected successfully"
            ),
            "appeal_id": appeal_id,
            "status": action
        })

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# INVESTIGATION MODULE
# ==================================================
# SINGLE, CLEAN VERSION
# ==================================================


# ==================================================
# EMPLOYEE — SUBMIT INVESTIGATION
# ==================================================

@app.route("/api/investigations", methods=["POST"])
def submit_investigation():

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    issue_type = data.get("issue_type")
    subject = data.get("subject")
    description = data.get("description")
    evidence_details = data.get("evidence_details")

    if not issue_type:
        return jsonify({
            "success": False,
            "message": "Issue type is required"
        }), 400

    if not subject or not subject.strip():
        return jsonify({
            "success": False,
            "message": "Subject is required"
        }), 400

    if not description or not description.strip():
        return jsonify({
            "success": False,
            "message": "Description is required"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                employee_id,
                manager_id

            FROM employees

            WHERE user_id = %s
        """, (user_id,))

        employee = cursor.fetchone()

        if not employee:
            return jsonify({
                "success": False,
                "message": "Employee record not found"
            }), 404

        employee_id = employee["employee_id"]
        manager_id = employee["manager_id"]

        # Find the configured higher authority.
        # In the current system this is the first admin.

        cursor.execute("""
            SELECT user_id

            FROM users

            WHERE role = 'admin'

            ORDER BY user_id

            LIMIT 1
        """)

        authority = cursor.fetchone()

        if not authority:
            return jsonify({
                "success": False,
                "message": "No higher authority is configured"
            }), 500

        higher_authority_id = authority["user_id"]

        cursor.execute("""
            INSERT INTO investigations
            (
                employee_id,
                manager_id,
                higher_authority_id,
                issue_type,
                subject,
                description,
                evidence_details,
                status
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'pending'
            )
        """, (
            employee_id,
            manager_id,
            higher_authority_id,
            issue_type,
            subject.strip(),
            description.strip(),
            (
                evidence_details.strip()
                if isinstance(evidence_details, str)
                else None
            )
        ))

        investigation_id = cursor.lastrowid

        create_audit_log(
            cursor,
            user_id,
            "INVESTIGATION_SUBMITTED",
            "investigation",
            investigation_id,
            "Employee submitted an issue for higher-authority investigation."
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Investigation submitted successfully",
            "investigation_id": investigation_id,
            "status": "pending"
        }), 201

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# EMPLOYEE — MY INVESTIGATIONS
# ==================================================

@app.route("/api/my-investigations", methods=["GET"])
def get_my_investigations():

    check = require_role(["employee"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                i.investigation_id,
                i.employee_id,
                i.manager_id,
                i.higher_authority_id,

                i.issue_type,
                i.subject,
                i.description,
                i.evidence_details,

                i.status,
                i.authority_response,

                i.created_at,
                i.updated_at,
                i.resolved_at,

                m.name AS manager_name,
                h.name AS authority_name

            FROM investigations i

            JOIN employees e
                ON i.employee_id = e.employee_id

            LEFT JOIN users m
                ON i.manager_id = m.user_id

            LEFT JOIN users h
                ON i.higher_authority_id = h.user_id

            WHERE e.user_id = %s

            ORDER BY i.created_at DESC
        """, (user_id,))

        investigations = cursor.fetchall()

        return jsonify({
            "success": True,
            "investigations": investigations,
            "count": len(investigations)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# ADMIN — PENDING INVESTIGATION COUNT
# ==================================================

@app.route("/api/pending-investigations", methods=["GET"])
def pending_investigations():

    check = require_role(["admin"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT COUNT(*)

            FROM investigations

            WHERE
                higher_authority_id = %s

                AND status IN (
                    'pending',
                    'under_investigation'
                )
        """, (user_id,))

        result = cursor.fetchone()

        return jsonify({
            "success": True,
            "count": result[0] if result else 0
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "count": 0,
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# ADMIN — INVESTIGATION LIST
# ==================================================

@app.route("/api/investigations", methods=["GET"])
def get_investigations_for_authority():

    check = require_role(["admin"])

    if check:
        return check

    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                i.investigation_id,
                i.employee_id,
                i.manager_id,
                i.higher_authority_id,

                i.issue_type,
                i.subject,
                i.description,
                i.evidence_details,

                i.status,
                i.authority_response,

                i.created_at,
                i.updated_at,
                i.resolved_at,

                eu.name AS employee_name,
                eu.email AS employee_email,

                mu.name AS manager_name,
                mu.email AS manager_email

            FROM investigations i

            JOIN employees e
                ON i.employee_id = e.employee_id

            JOIN users eu
                ON e.user_id = eu.user_id

            LEFT JOIN users mu
                ON i.manager_id = mu.user_id

            WHERE
                i.higher_authority_id = %s

            ORDER BY
                CASE
                    WHEN i.status = 'pending'
                        THEN 1

                    WHEN i.status = 'under_investigation'
                        THEN 2

                    ELSE 3
                END,

                i.created_at ASC
        """, (user_id,))

        investigations = cursor.fetchall()

        return jsonify({
            "success": True,
            "investigations": investigations,
            "count": len(investigations)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# ADMIN — REVIEW INVESTIGATION
# ==================================================

@app.route("/api/investigation-review", methods=["POST"])
def review_investigation():

    check = require_role(["admin"])

    if check:
        return check

    user_id = session.get("user_id")

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    investigation_id = data.get("investigation_id")
    action = data.get("action")
    authority_response = data.get("authority_response")

    if not investigation_id:
        return jsonify({
            "success": False,
            "message": "Investigation ID is required"
        }), 400

    allowed_actions = [
        "under_investigation",
        "resolved_upheld",
        "resolved_rejected"
    ]

    if action not in allowed_actions:
        return jsonify({
            "success": False,
            "message": "Invalid investigation action"
        }), 400

    if (
        not authority_response
        or not authority_response.strip()
    ):
        return jsonify({
            "success": False,
            "message": "Authority response is required"
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                investigation_id,
                employee_id,
                manager_id,
                higher_authority_id,
                status

            FROM investigations

            WHERE
                investigation_id = %s
                AND higher_authority_id = %s
        """, (
            investigation_id,
            user_id
        ))

        investigation = cursor.fetchone()

        if not investigation:
            return jsonify({
                "success": False,
                "message": "Investigation not found or access denied"
            }), 404

        if investigation["status"] in [
            "resolved_upheld",
            "resolved_rejected"
        ]:
            return jsonify({
                "success": False,
                "message": "This investigation has already been resolved"
            }), 400

        if action == "under_investigation":

            cursor.execute("""
                UPDATE investigations

                SET
                    status = 'under_investigation',
                    authority_response = %s,
                    updated_at = CURRENT_TIMESTAMP

                WHERE investigation_id = %s
            """, (
                authority_response.strip(),
                investigation_id
            ))

        else:

            cursor.execute("""
                UPDATE investigations

                SET
                    status = %s,
                    authority_response = %s,
                    reviewed_by = %s,
                    resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP

                WHERE investigation_id = %s
            """, (
                action,
                authority_response.strip(),
                user_id,
                investigation_id
            ))

        create_audit_log(
            cursor,
            user_id,
            "INVESTIGATION_REVIEWED",
            "investigation",
            investigation_id,
            (
                "Higher authority changed investigation "
                f"status to {action}."
            )
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Investigation updated successfully",
            "investigation_id": investigation_id,
            "status": action
        })

    except mysql.connector.Error as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# ADMIN — AUDIT LOGS
# ==================================================

@app.route("/api/audit-logs", methods=["GET"])
def get_audit_logs():

    check = require_role(["admin"])

    if check:
        return check

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                al.log_id,
                al.user_id,
                u.name,
                u.email,
                u.role,

                al.action,
                al.entity_type,
                al.entity_id,
                al.description,
                al.created_at

            FROM audit_logs al

            LEFT JOIN users u
                ON al.user_id = u.user_id

            ORDER BY al.created_at DESC

            LIMIT 200
        """)

        logs = cursor.fetchall()

        return jsonify({
            "success": True,
            "logs": logs,
            "count": len(logs)
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        connection.close()


# ==================================================
# EMPLOYEE PROFILE / SESSION
# ==================================================

@app.route("/api/me", methods=["GET"])
def current_user():
    if not session.get("user_id"):
        return jsonify({"success": False, "message": "User not logged in"}), 401

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT u.user_id, u.name, u.email, u.role,
                   e.employee_id, e.employee_code, e.department,
                   e.designation, e.joining_date, e.manager_id
            FROM users u
            LEFT JOIN employees e ON e.user_id = u.user_id
            WHERE u.user_id = %s
        """, (session["user_id"],))
        user = cursor.fetchone()
        return jsonify({"success": True, "user": user})
    except mysql.connector.Error as error:
        return jsonify({"success": False, "message": "Database error", "error": str(error)}), 500
    finally:
        cursor.close(); db.close()


# ==================================================
# EMPLOYEE — UPLOAD NEW DOCUMENT
# ==================================================

@app.route("/api/upload-document", methods=["POST"])
def upload_document():
    check = require_role(["employee"])
    if check:
        return check

    uploaded_file = request.files.get("document")
    document_type = (request.form.get("document_type") or "other").strip()
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"success": False, "message": "Please select a document"}), 400

    allowed = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}
    original = secure_filename(uploaded_file.filename)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if not original or ext not in allowed:
        return jsonify({"success": False, "message": "Allowed files: PDF, DOC, DOCX, JPG, JPEG, PNG"}), 400

    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT employee_id FROM employees WHERE user_id=%s", (session["user_id"],))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({"success": False, "message": "Employee record not found"}), 404

        unique = uuid.uuid4().hex + "_" + original
        uploaded_file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique))
        database_path = "uploads/documents/" + unique

        cursor.execute("""
            INSERT INTO documents
            (employee_id, document_type, document_name, document_path, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (employee["employee_id"], document_type, original, database_path))
        document_id = cursor.lastrowid
        create_audit_log(cursor, session["user_id"], "DOCUMENT_SUBMITTED", "document", document_id,
                          "Employee uploaded a document for manager verification.")
        db.commit()
        return jsonify({"success": True, "message": "Document submitted successfully", "document_id": document_id}), 201
    except mysql.connector.Error as error:
        db.rollback()
        return jsonify({"success": False, "message": "Database error", "error": str(error)}), 500
    except Exception as error:
        db.rollback()
        return jsonify({"success": False, "message": "File upload failed", "error": str(error)}), 500
    finally:
        cursor.close(); db.close()


# ==================================================
# EMPLOYEE — APPRAISALS
# ==================================================

@app.route("/api/my-appraisals", methods=["GET"])
def my_appraisals():
    check = require_role(["employee"])
    if check:
        return check
    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT a.appraisal_id, a.employee_id, a.manager_id, a.appraisal_period,
                   a.overall_rating, a.self_rating, a.employee_comments,
                   a.manager_comments, a.status, a.created_at, a.updated_at
            FROM appraisals a
            JOIN employees e ON a.employee_id=e.employee_id
            WHERE e.user_id=%s
            ORDER BY a.created_at DESC
        """, (session["user_id"],))
        rows = cursor.fetchall()
        return jsonify({"success": True, "appraisals": rows, "count": len(rows)})
    except mysql.connector.Error as error:
        return jsonify({"success": False, "message": "Database error", "error": str(error)}), 500
    finally:
        cursor.close(); db.close()


@app.route("/api/appraisals", methods=["POST"])
def create_appraisal():
    check = require_role(["employee"])
    if check:
        return check
    data = request.get_json() or {}
    period = str(data.get("appraisal_period") or "").strip()
    comments = str(data.get("employee_comments") or "").strip()
    try:
        self_rating = float(data.get("self_rating", 0))
        overall_rating = float(data.get("overall_rating", self_rating))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Ratings must be numbers"}), 400
    if not period or not comments:
        return jsonify({"success": False, "message": "Appraisal period and comments are required"}), 400
    if not (0 <= self_rating <= 5 and 0 <= overall_rating <= 5):
        return jsonify({"success": False, "message": "Ratings must be between 0 and 5"}), 400

    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT employee_id, manager_id FROM employees WHERE user_id=%s", (session["user_id"],))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({"success": False, "message": "Employee record not found"}), 404
        if not employee["manager_id"]:
            return jsonify({"success": False, "message": "No manager is assigned to this employee"}), 400
        cursor.execute("""
            SELECT appraisal_id FROM appraisals
            WHERE employee_id=%s AND appraisal_period=%s
            AND status IN ('submitted','under_review','resubmitted')
        """, (employee["employee_id"], period))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "A pending appraisal already exists for this period"}), 409
        cursor.execute("""
            INSERT INTO appraisals
            (employee_id, manager_id, appraisal_period, overall_rating, self_rating,
             employee_comments, status)
            VALUES (%s,%s,%s,%s,%s,%s,'submitted')
        """, (employee["employee_id"], employee["manager_id"], period, overall_rating, self_rating, comments))
        appraisal_id = cursor.lastrowid
        create_audit_log(cursor, session["user_id"], "APPRAISAL_SUBMITTED", "appraisal", appraisal_id,
                          "Employee submitted a performance appraisal.")
        db.commit()
        return jsonify({"success": True, "message": "Appraisal submitted successfully", "appraisal_id": appraisal_id}), 201
    except mysql.connector.Error as error:
        db.rollback(); return jsonify({"success": False, "message": "Database error", "error": str(error)}), 500
    finally:
        cursor.close(); db.close()

# ==================================================
# REGISTER
# ==================================================

@app.route("/api/register", methods=["POST"])
def register():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    employee_code = data.get("employee_code")
    department = data.get("department")
    designation = data.get("designation")
    joining_date = data.get("joining_date")

    if not all([
        name,
        email,
        password,
        employee_code
    ]):
        return jsonify({
            "success": False,
            "message": (
                "Name, email, password and "
                "employee code are required"
            )
        }), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:

        cursor.execute("""
            SELECT user_id

            FROM users

            WHERE email = %s
        """, (email,))

        if cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Email already registered"
            }), 409

        password_hash = generate_password_hash(password)

        cursor.execute("""
            INSERT INTO users
            (
                name,
                email,
                password_hash,
                role
            )

            VALUES
            (
                %s,
                %s,
                %s,
                'employee'
            )
        """, (
            name,
            email,
            password_hash
        ))

        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO employees
            (
                user_id,
                employee_code,
                department,
                designation,
                joining_date
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            user_id,
            employee_code,
            department,
            designation,
            joining_date
        ))

        db.commit()

        return jsonify({
            "success": True,
            "message": "Employee registered successfully",
            "user_id": user_id,
            "employee_code": employee_code,
            "role": "employee"
        }), 201

    except mysql.connector.Error as error:

        db.rollback()

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        db.close()


# ==================================================
# LOGIN
# ==================================================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "Request data is required"
        }), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:

        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                user_id,
                name,
                email,
                password_hash,
                role

            FROM users

            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        if not user:

            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        if not check_password_hash(
            user["password_hash"],
            password
        ):

            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        create_audit_log(
            cursor,
            user["user_id"],
            "LOGIN",
            "user",
            user["user_id"],
            f"{user['role']} logged into AppraiseX."
        )

        db.commit()

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        })

    except mysql.connector.Error as error:

        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(error)
        }), 500

    finally:

        cursor.close()
        db.close()


# ==================================================
# LOGOUT
# ==================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


# ==================================================
# RUN FLASK
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )