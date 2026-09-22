import os
import sqlite3
from datetime import datetime
from google.auth import credentials as auth_credentials
from google.cloud import firestore

def migrate():
    # 1. Connect to SQLite
    sqlite_path = "focusguard.db"
    if not os.path.exists(sqlite_path):
        print(f"[MIGRATION] SQLite database not found at {sqlite_path}!")
        return
        
    print(f"[MIGRATION] Reading SQLite database from {sqlite_path}...")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # 2. Connect to Firestore emulator/production
    is_production = os.environ.get("MIGRATE_TO_PRODUCTION", "false").lower() == "true"
    if not is_production:
        if "FIRESTORE_EMULATOR_HOST" not in os.environ:
            os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
        if "FIREBASE_AUTH_EMULATOR_HOST" not in os.environ:
            os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
        print(f"[MIGRATION] Connecting to Firestore Emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}...")
        db = firestore.Client(
            project="focusguard-ai",
            credentials=auth_credentials.AnonymousCredentials()
        )
    else:
        print("[MIGRATION] Connecting to production Firestore...")
        db = firestore.Client()

    # Initialize firebase-admin for Auth migration
    import firebase_admin
    from firebase_admin import credentials, auth
    
    if not firebase_admin._apps:
        if not is_production:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": "focusguard-ai",
                "private_key_id": "dummy_id",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCgsllafKXQ3pOw\nZrYS3jfzwNSccVnn7bxTzPUHAC3zGG+NPUheeUDSTrLTZzlwLKEEb+hUkdL/9txo\nP2TjguhNGm8ffH0A6ZjZBwOpvduKZHsj32g1E5HwP5P9CNmYVQ3YDO48uozXkNna\naRxhY0vkQEtvpRTUugUDWeAi04J0+l7MGkIP/r0z4k3R/Xsncm8s/sgdOW+A9jyH\nyyRKIZpOHxnqVrxVQzMwMvzfPsBFectRp2WQm4B7kGo67x/GFAuTg1HOpg14Ivfz\n4/hpjC0kB00PXK2wQ4Ux2EA87HWnAtwGN+DC63aqUoJChRaocei9xfML5aWFxgfY\n1HIfoOFZAgMBAAECggEAMI7kEENFKdHwJ+hJkXcDykzVEjbwV3SPqXTv/78Oo3wZ\nTUEc6qtSKpqsT9RL13ks6LXWKyPrcfxLCtdJKbSHdLENriKEdW+hB8emVDbyLaYC\nTcs25n705PeZROdVNUJSThxOKxyl7YewRN7pPAZwytag1Oo52rQhSqtwXqWyMJ1y\nxdRNlPX1KpeE1duqLnGsd998xs/gUP2rGvQXG2C9BpKYceLgfpWhFtQoI0EOIQ29\nijatyW+dvClSeSwN1USRv588nAFEKbz50GSIaZ1vu2rJ4WlzyrMMdYBghkf0nnUz\nPyXeOX+46Rpc4GKQtRh5zgVIsk0mC2zSst55lUSBnwKBgQDPsPCmta+51/zV+i/q\nU/dgWMn4RKJ6Fz03Q6u9daCHF/k7SqroF/KCXcvyLt+MeQhiyPBxu0p+HIVvC3MM\nlsfcOOeiMU/aD1l+vipW5V0m5Qy4RTmJWuYTm+wpqV9nIKEyZGL1aWkmpiKzmCIL\nUB8jABVLJ5IPjJ22y3Hdqi8N6wKBgQDGExn/pmcovJ0keMobdDQ9Ctltz2p+mkHj\n9u0vmZDFCbJkdrbbeqihgqi5bKoIJi8ZGSHiei6qnNifTo3rrPgBDAMbA/jpMFiM\nhkZ5Iw1WrgPdi/KV4Dj31Pt261hUKfFbSjygvj5RUwFx4PcpKLlFnxc3RUzq4Hzt\nweiTT8SIywKBgF2YYXrfWceofDp5uuog2NREbxBA7e+TVXT4PAbvYV5AAYMkzQw2\n7oStfGExmnCVgp/x6dl3C8T1WXSHdltv/7VQt6IyEsg0LqKdVDtAtc/3XNoV6C3s\nFs8zbyP/Pg0deUdaUfZCgK54JB9HKeBrRPzi5rWtqXb0aYac/D1mmjntAoGAO2OK\nzg5Uq/AxpbfZ0XV8HDlejAA+zArwaquk3jrLH2kS5fB6T0Btw09ry3z7VkosoPfa\nIw/DYkB46vsgrmNEUPwLClSckz59rlSsWLHb0/uFCS5m4+1A534ij7ts1n9k8JxH\npWKlSLj8m+p58QtW0bsruNS8hUgd7SPQ2ip2oRUCgYBMDrxIEuHxHmAMLKjNGrBs\nZKutF8yjgWVw0B3DD6xDEX63RHhnl/jGeQy1y5aw+PP5OBNI2eWjByogF7HMws3X\nNsXlMcGy/r0pG6N+a0MjF0CXUdQVdlamYHMrzWwjnxpj0iQ/fNuE420elIi+LbuH\n2JDkrpAfFP6Xj+9ukur91Q==\n-----END PRIVATE KEY-----\n",
                "client_email": "firebase-adminsdk-dummy@focusguard-ai.iam.gserviceaccount.com",
                "client_id": "1234567890",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-dummy%40focusguard-ai.iam.gserviceaccount.com"
            })
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
            
    def get_auth_password(pw):
        if pw and len(str(pw)) < 6:
            return str(pw).ljust(6, '0')
        return str(pw)

    # --- Migrate 'classes' ---
    print("[MIGRATION] Migrating 'classes' table...")
    cursor.execute("SELECT id, class_name FROM classes")
    classes_rows = cursor.fetchall()
    for row in classes_rows:
        class_id, class_name = row
        db.collection("classes").document(str(class_id)).set({
            "id": int(class_id),
            "class_name": class_name
        })
    print(f"[MIGRATION] Migrated {len(classes_rows)} classes.")
    
    # --- Migrate 'users' ---
    print("[MIGRATION] Migrating 'users' table to Firestore and Firebase Auth...")
    cursor.execute("SELECT id, username, password, display_name, role, class_id, student_id FROM users")
    users_rows = cursor.fetchall()
    for row in users_rows:
        user_id, username, password, display_name, role, class_id, student_id = row
        # 1. Sync to Firestore
        db.collection("users").document(str(user_id)).set({
            "id": int(user_id),
            "username": username,
            "password": password,
            "display_name": display_name,
            "role": role,
            "class_id": int(class_id) if class_id is not None else None,
            "student_id": int(student_id) if student_id is not None else None
        })
        
        # 2. Sync to Firebase Auth
        uid = str(user_id)
        email = f"{username}@focusguard.ai"
        padded_pw = get_auth_password(password)
        try:
            auth.update_user(
                uid,
                email=email,
                password=padded_pw,
                display_name=display_name
            )
        except Exception:
            try:
                auth.create_user(
                    uid=uid,
                    email=email,
                    password=padded_pw,
                    display_name=display_name
                )
            except Exception as ce:
                print(f"[MIGRATION] Error creating Firebase Auth user {username}: {ce}")
        
        try:
            auth.set_custom_user_claims(uid, {
                "role": role,
                "display_name": display_name,
                "class_id": int(class_id) if class_id is not None else None
            })
        except Exception as ae:
            print(f"[MIGRATION] Error setting custom claims for {username}: {ae}")
            
    print(f"[MIGRATION] Migrated {len(users_rows)} users to Firestore and Firebase Auth.")
    
    # --- Migrate 'sessions' ---
    print("[MIGRATION] Migrating 'sessions' table...")
    cursor.execute("SELECT id, user_id, start_time, end_time, duration_seconds, final_score, total_distractions, history_json FROM sessions")
    sessions_rows = cursor.fetchall()
    for row in sessions_rows:
        s_id, u_id, start_time, end_time, duration, score, distractions, hist_json = row
        db.collection("sessions").document(str(s_id)).set({
            "id": int(s_id),
            "user_id": int(u_id) if u_id is not None else None,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": int(duration) if duration is not None else None,
            "final_score": int(score) if score is not None else None,
            "total_distractions": int(distractions) if distractions is not None else None,
            "history_json": hist_json
        })
    print(f"[MIGRATION] Migrated {len(sessions_rows)} sessions.")
    
    # --- Migrate 'focus_events' ---
    print("[MIGRATION] Migrating 'focus_events' table...")
    cursor.execute("SELECT id, session_id, type, timestamp FROM focus_events")
    events_rows = cursor.fetchall()
    for row in events_rows:
        e_id, s_id, event_type, timestamp = row
        db.collection("focus_events").document(str(e_id)).set({
            "id": int(e_id),
            "session_id": int(s_id) if s_id is not None else None,
            "type": event_type,
            "timestamp": timestamp
        })
    print(f"[MIGRATION] Migrated {len(events_rows)} focus events.")
    
    # --- Migrate 'class_sessions' ---
    print("[MIGRATION] Migrating 'class_sessions' table...")
    cursor.execute("SELECT id, class_id, started_at, ended_at FROM class_sessions")
    class_sess_rows = cursor.fetchall()
    for row in class_sess_rows:
        cs_id, c_id, started_at, ended_at = row
        db.collection("class_sessions").document(str(cs_id)).set({
            "id": int(cs_id),
            "class_id": int(c_id) if c_id is not None else None,
            "started_at": started_at,
            "ended_at": ended_at
        })
    print(f"[MIGRATION] Migrated {len(class_sess_rows)} class sessions.")
    
    conn.close()
    print("[MIGRATION] SQLite to Firestore migration completed successfully!")

if __name__ == "__main__":
    migrate()
