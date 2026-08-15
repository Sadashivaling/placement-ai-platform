from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import re
import hashlib
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Placement AI Platform",
    description="AI-powered placement and job readiness platform",
    version="4.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sadashivaling.github.io"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not configured."
    )


def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def init_db():

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # -------------------------------------------------
            # USERS
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,

                    username VARCHAR(30)
                        UNIQUE NOT NULL,

                    name VARCHAR(100)
                        NOT NULL,

                    email VARCHAR(255)
                        UNIQUE NOT NULL,

                    password_hash TEXT
                        NOT NULL,

                    role VARCHAR(30)
                        NOT NULL
                        CHECK (
                            role IN (
                                'career_seeker',
                                'recruiter',
                                'owner'
                            )
                        ),

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # -------------------------------------------------
            # JOBS
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,

                    recruiter_id INTEGER
                        NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    title VARCHAR(200)
                        NOT NULL,

                    description TEXT
                        NOT NULL,

                    skills TEXT,

                    location VARCHAR(200),

                    salary VARCHAR(100),

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # -------------------------------------------------
            # APPLICATIONS
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id SERIAL PRIMARY KEY,

                    job_id INTEGER
                        NOT NULL
                        REFERENCES jobs(id)
                        ON DELETE CASCADE,

                    candidate_id INTEGER
                        NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    status VARCHAR(30)
                        DEFAULT 'applied',

                    applied_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(job_id, candidate_id)
                )
            """)

            # -------------------------------------------------
            # RESUMES
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,

                    user_id INTEGER
                        UNIQUE
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    filename VARCHAR(255),

                    resume_text TEXT,

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # -------------------------------------------------
            # OWNER SESSION LOG
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS owner_sessions (
                    id SERIAL PRIMARY KEY,

                    owner_id INTEGER
                        NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    login_time TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP,

                    logout_time TIMESTAMP
                )
            """)

            # -------------------------------------------------
            # OWNER USER
            # -------------------------------------------------

            owner_username = os.getenv(
                "OWNER_USERNAME",
                "admin"
            )

            owner_password = os.getenv(
                "OWNER_PASSWORD",
                "admin123"
            )

            owner_name = os.getenv(
                "OWNER_NAME",
                "Placement AI Owner"
            )

            owner_email = os.getenv(
                "OWNER_EMAIL",
                "owner@placementai.local"
            )

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE username = %s
                """,
                (owner_username,)
            )

            existing_owner = cursor.fetchone()

            if not existing_owner:

                password_hash = hashlib.sha256(
                    owner_password.encode("utf-8")
                ).hexdigest()

                cursor.execute(
                    """
                    INSERT INTO users
                    (
                        username,
                        name,
                        email,
                        password_hash,
                        role
                    )
                    VALUES (%s, %s, %s, %s, 'owner')
                    """,
                    (
                        owner_username,
                        owner_name,
                        owner_email,
                        password_hash
                    )
                )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup():

    init_db()


# =========================================================
# PASSWORD HELPERS
# =========================================================

def hash_password(password: str):

    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def verify_password(
    password: str,
    password_hash: str
):

    return secrets.compare_digest(
        hash_password(password),
        password_hash
    )


# =========================================================
# VALIDATION HELPERS
# =========================================================

def validate_username(username: str):

    if not re.fullmatch(
        r"[A-Za-z0-9_]{3,30}",
        username
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Username must be 3-30 characters "
                "and contain only letters, numbers "
                "and underscores."
            )
        )


def validate_email(email: str):

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid email address."
        )


# =========================================================
# MODELS
# =========================================================

class RegisterRequest(BaseModel):

    username: str
    name: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):

    username: str
    password: str


class JobCreateRequest(BaseModel):

    recruiter_id: int
    title: str
    description: str
    skills: str = ""
    location: str = ""
    salary: str = ""


class ApplicationCreateRequest(BaseModel):

    job_id: int
    candidate_id: int


class ResumeRequest(BaseModel):

    user_id: int
    filename: str
    resume_text: str


class OwnerLogoutRequest(BaseModel):

    session_id: int


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "success": True,
        "message": "Placement AI Platform API is running.",
        "version": "4.0.0"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "success": True,
        "status": "healthy"
    }


# =========================================================
# REGISTER
# =========================================================

@app.post("/api/v1/auth/register")
def register(request: RegisterRequest):

    username = request.username.strip()
    name = request.name.strip()
    email = request.email.strip().lower()
    password = request.password

    role = request.role.strip().lower()

    validate_username(username)
    validate_email(email)

    if len(password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters."
        )

    if role not in [
        "career_seeker",
        "recruiter"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Invalid registration role."
        )

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE username = %s
                OR email = %s
                """,
                (
                    username,
                    email
                )
            )

            existing = cursor.fetchone()

            if existing:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Username or email already exists."
                    )
                )

            password_hash = hash_password(password)

            cursor.execute(
                """
                INSERT INTO users
                (
                    username,
                    name,
                    email,
                    password_hash,
                    role
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING
                    id,
                    username,
                    name,
                    email,
                    role,
                    created_at
                """,
                (
                    username,
                    name,
                    email,
                    password_hash,
                    role
                )
            )

            user = cursor.fetchone()

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not create account."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Account created successfully.",
        "user": user
    }


# =========================================================
# LOGIN
# =========================================================

@app.post("/api/v1/auth/login")
def login(request: LoginRequest):

    username = request.username.strip()

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    password_hash,
                    role
                FROM users
                WHERE username = %s
                """,
                (username,)
            )

            user = cursor.fetchone()

            if not user:

                raise HTTPException(
                    status_code=401,
                    detail="Invalid username or password."
                )

            if not verify_password(
                request.password,
                user["password_hash"]
            ):

                raise HTTPException(
                    status_code=401,
                    detail="Invalid username or password."
                )

            user.pop("password_hash", None)

        conn.commit()

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Login successful.",
        "user": user
    }


# =========================================================
# USERS
# =========================================================

@app.get("/api/v1/users")
def get_users():

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    role,
                    created_at
                FROM users
                ORDER BY created_at DESC
                """
            )

            users = cursor.fetchall()

    finally:

        conn.close()

    return {
        "success": True,
        "users": users
    }


# =========================================================
# USER BY ID
# =========================================================

@app.get("/api/v1/users/{user_id}")
def get_user(user_id: int):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    role,
                    created_at
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            user = cursor.fetchone()

    finally:

        conn.close()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    return {
        "success": True,
        "user": user
    }


# =========================================================
# CREATE JOB
# =========================================================

@app.post("/api/v1/jobs")
def create_job(request: JobCreateRequest):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s
                AND role = 'recruiter'
                """,
                (request.recruiter_id,)
            )

            recruiter = cursor.fetchone()

            if not recruiter:

                raise HTTPException(
                    status_code=403,
                    detail="Recruiter account required."
                )

            if not request.title.strip():

                raise HTTPException(
                    status_code=400,
                    detail="Job title is required."
                )

            if not request.description.strip():

                raise HTTPException(
                    status_code=400,
                    detail="Job description is required."
                )

            cursor.execute(
                """
                INSERT INTO jobs
                (
                    recruiter_id,
                    title,
                    description,
                    skills,
                    location,
                    salary
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    request.recruiter_id,
                    request.title.strip(),
                    request.description.strip(),
                    request.skills.strip(),
                    request.location.strip(),
                    request.salary.strip()
                )
            )

            job = cursor.fetchone()

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not create job."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Job created successfully.",
        "job": job
    }


# =========================================================
# GET JOBS
# =========================================================

@app.get("/api/v1/jobs")
def get_jobs():

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    jobs.id,
                    jobs.title,
                    jobs.description,
                    jobs.skills,
                    jobs.location,
                    jobs.salary,
                    jobs.created_at,
                    jobs.recruiter_id,
                    users.username AS recruiter_username,
                    users.name AS recruiter_name
                FROM jobs
                JOIN users
                    ON users.id = jobs.recruiter_id
                ORDER BY jobs.created_at DESC
                """
            )

            jobs = cursor.fetchall()

    finally:

        conn.close()

    return {
        "success": True,
        "jobs": jobs
    }


# =========================================================
# JOB BY ID
# =========================================================

@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: int):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    jobs.id,
                    jobs.title,
                    jobs.description,
                    jobs.skills,
                    jobs.location,
                    jobs.salary,
                    jobs.created_at,
                    jobs.recruiter_id,
                    users.username AS recruiter_username,
                    users.name AS recruiter_name
                FROM jobs
                JOIN users
                    ON users.id = jobs.recruiter_id
                WHERE jobs.id = %s
                """,
                (job_id,)
            )

            job = cursor.fetchone()

    finally:

        conn.close()

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return {
        "success": True,
        "job": job
    }


# =========================================================
# APPLY FOR JOB
# =========================================================

@app.post("/api/v1/applications")
def apply_for_job(
    request: ApplicationCreateRequest
):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # Candidate check
            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s
                AND role = 'career_seeker'
                """,
                (request.candidate_id,)
            )

            candidate = cursor.fetchone()

            if not candidate:

                raise HTTPException(
                    status_code=403,
                    detail="Career seeker account required."
                )

            # Job check
            cursor.execute(
                """
                SELECT id
                FROM jobs
                WHERE id = %s
                """,
                (request.job_id,)
            )

            job = cursor.fetchone()

            if not job:

                raise HTTPException(
                    status_code=404,
                    detail="Job not found."
                )

            # Duplicate application check
            cursor.execute(
                """
                SELECT id
                FROM applications
                WHERE job_id = %s
                AND candidate_id = %s
                """,
                (
                    request.job_id,
                    request.candidate_id
                )
            )

            existing = cursor.fetchone()

            if existing:

                raise HTTPException(
                    status_code=409,
                    detail="You have already applied for this job."
                )

            cursor.execute(
                """
                INSERT INTO applications
                (
                    job_id,
                    candidate_id
                )
                VALUES (%s, %s)
                RETURNING *
                """,
                (
                    request.job_id,
                    request.candidate_id
                )
            )

            application = cursor.fetchone()

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not submit application."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Application submitted successfully.",
        "application": application
    }


# =========================================================
# GET APPLICATIONS
# =========================================================

@app.get("/api/v1/applications")
def get_applications():

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    applications.id,
                    applications.job_id,
                    applications.candidate_id,
                    applications.status,
                    applications.applied_at,
                    jobs.title AS job_title,
                    users.username AS candidate_username,
                    users.name AS candidate_name,
                    users.email AS candidate_email
                FROM applications
                JOIN jobs
                    ON jobs.id = applications.job_id
                JOIN users
                    ON users.id = applications.candidate_id
                ORDER BY applications.applied_at DESC
                """
            )

            applications = cursor.fetchall()

    finally:

        conn.close()

    return {
        "success": True,
        "applications": applications
    }


# =========================================================
# SAVE RESUME
# =========================================================

@app.post("/api/v1/resumes")
def save_resume(request: ResumeRequest):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE id = %s
                AND role = 'career_seeker'
                """,
                (request.user_id,)
            )

            user = cursor.fetchone()

            if not user:

                raise HTTPException(
                    status_code=403,
                    detail="Career seeker account required."
                )

            cursor.execute(
                """
                INSERT INTO resumes
                (
                    user_id,
                    filename,
                    resume_text
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    filename = EXCLUDED.filename,
                    resume_text = EXCLUDED.resume_text,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (
                    request.user_id,
                    request.filename,
                    request.resume_text
                )
            )

            resume = cursor.fetchone()

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not save resume."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Resume saved successfully.",
        "resume": resume
    }


# =========================================================
# GET RESUME
# =========================================================

@app.get("/api/v1/resumes/{user_id}")
def get_resume(user_id: int):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM resumes
                WHERE user_id = %s
                """,
                (user_id,)
            )

            resume = cursor.fetchone()

    finally:

        conn.close()

    if not resume:

        return {
            "success": True,
            "resume": None
        }

    return {
        "success": True,
        "resume": resume
    }


# =========================================================
# OWNER LOGIN
# =========================================================

@app.post("/api/v1/owner/login")
def owner_login(request: LoginRequest):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    password_hash,
                    role
                FROM users
                WHERE username = %s
                AND role = 'owner'
                """,
                (request.username.strip(),)
            )

            owner = cursor.fetchone()

            if not owner:

                raise HTTPException(
                    status_code=401,
                    detail="Invalid owner username or password."
                )

            if not verify_password(
                request.password,
                owner["password_hash"]
            ):

                raise HTTPException(
                    status_code=401,
                    detail="Invalid owner username or password."
                )

            cursor.execute(
                """
                INSERT INTO owner_sessions
                (
                    owner_id
                )
                VALUES (%s)
                RETURNING
                    id,
                    login_time,
                    logout_time
                """,
                (owner["id"],)
            )

            session = cursor.fetchone()

            owner.pop("password_hash", None)

        conn.commit()

    except HTTPException:

        conn.rollback()
        raise

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Owner login failed."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Owner login successful.",
        "owner": owner,
        "session": session
    }


# =========================================================
# OWNER LOGOUT
# =========================================================

@app.post("/api/v1/owner/logout")
def owner_logout(request: OwnerLogoutRequest):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE owner_sessions
                SET logout_time = CURRENT_TIMESTAMP
                WHERE id = %s
                AND logout_time IS NULL
                RETURNING
                    id,
                    login_time,
                    logout_time
                """,
                (request.session_id,)
            )

            session = cursor.fetchone()

        conn.commit()

    except Exception:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not record owner logout."
        )

    finally:

        conn.close()

    return {
        "success": True,
        "message": "Owner logout recorded.",
        "session": session
    }


# =========================================================
# OWNER DASHBOARD
# =========================================================

@app.get("/api/v1/owner/dashboard")
def owner_dashboard(owner_id: int):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # -------------------------------------------------
            # VERIFY OWNER
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    role
                FROM users
                WHERE id = %s
                AND role = 'owner'
                """,
                (owner_id,)
            )

            owner = cursor.fetchone()

            if not owner:

                raise HTTPException(
                    status_code=403,
                    detail="Owner access required."
                )

            # -------------------------------------------------
            # TOTAL USERS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*) AS total_users
                FROM users
                """
            )

            total_users = cursor.fetchone()["total_users"]

            # -------------------------------------------------
            # CAREER SEEKERS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'career_seeker'
                """
            )

            career_seekers = cursor.fetchone()["count"]

            # -------------------------------------------------
            # RECRUITERS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'recruiter'
                """
            )

            recruiters = cursor.fetchone()["count"]

            # -------------------------------------------------
            # JOBS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM jobs
                """
            )

            jobs = cursor.fetchone()["count"]

            # -------------------------------------------------
            # APPLICATIONS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                """
            )

            applications = cursor.fetchone()["count"]

            # -------------------------------------------------
            # RECENT USERS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    email,
                    role,
                    created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 20
                """
            )

            recent_users = cursor.fetchall()

            # -------------------------------------------------
            # RECENT JOBS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    jobs.id,
                    jobs.title,
                    jobs.description,
                    jobs.created_at,
                    users.username AS recruiter_username
                FROM jobs
                JOIN users
                    ON users.id = jobs.recruiter_id
                ORDER BY jobs.created_at DESC
                LIMIT 20
                """
            )

            recent_jobs = cursor.fetchall()

            # -------------------------------------------------
            # RECENT APPLICATIONS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    applications.id,
                    applications.status,
                    applications.applied_at,
                    jobs.title AS job_title,
                    users.username AS candidate_username,
                    users.name AS candidate_name
                FROM applications
                JOIN jobs
                    ON jobs.id = applications.job_id
                JOIN users
                    ON users.id = applications.candidate_id
                ORDER BY applications.applied_at DESC
                LIMIT 20
                """
            )

            recent_applications = cursor.fetchall()

            # -------------------------------------------------
            # OWNER SESSION HISTORY
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT
                    owner_sessions.id,
                    owner_sessions.login_time,
                    owner_sessions.logout_time,
                    users.username AS owner_username
                FROM owner_sessions
                JOIN users
                    ON users.id = owner_sessions.owner_id
                WHERE owner_sessions.owner_id = %s
                ORDER BY owner_sessions.login_time DESC
                LIMIT 20
                """,
                (owner_id,)
            )

            sessions = cursor.fetchall()

    finally:

        conn.close()

    return {
        "success": True,

        "owner": owner,

        "statistics": {
            "total_users": total_users,
            "career_seekers": career_seekers,
            "recruiters": recruiters,
            "jobs": jobs,
            "applications": applications
        },

        "recent_users": recent_users,

        "recent_jobs": recent_jobs,

        "recent_applications": recent_applications,

        "sessions": sessions
    }


# =========================================================
# DATABASE TEST
# =========================================================

@app.get("/api/v1/database-test")
def database_test():

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT COUNT(*) AS user_count
                FROM users
                """
            )

            result = cursor.fetchone()

    finally:

        conn.close()

    return {
        "success": True,
        "database": "PostgreSQL",
        "users": result["user_count"]
    }


# =========================================================
# SERVER
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000"
        )
    )

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port
    )
