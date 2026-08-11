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
                        NOT NULL,

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Allow 3 roles:
            # career_seeker
            # recruiter
            # owner

            cursor.execute("""
                ALTER TABLE users
                DROP CONSTRAINT IF EXISTS users_role_check
            """)

            cursor.execute("""
                ALTER TABLE users
                ADD CONSTRAINT users_role_check
                CHECK (
                    role IN (
                        'career_seeker',
                        'recruiter'
                        
                    )
                )
            """)


            # -------------------------------------------------
            # JOBS
            # -------------------------------------------------

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,

                    recruiter_id INTEGER
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    title VARCHAR(200)
                        NOT NULL,

                    description TEXT
                        NOT NULL,

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
                        REFERENCES jobs(id)
                        ON DELETE CASCADE,

                    candidate_id INTEGER
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
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    resume_text TEXT
                        NOT NULL,

                    created_at TIMESTAMP
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)


        conn.commit()

    finally:

        conn.close()


# Create database tables
init_db()


# =========================================================
# OWNER ACCOUNT
# =========================================================

def create_owner_account():

    owner_username = os.getenv("OWNER_USERNAME")
    owner_password = os.getenv("OWNER_PASSWORD")
    owner_name = os.getenv("OWNER_NAME")
    owner_email = os.getenv("OWNER_EMAIL")


    if not all([
        owner_username,
        owner_password,
        owner_name,
        owner_email
    ]):
        return


    owner_username = owner_username.strip().lower()
    owner_name = owner_name.strip()
    owner_email = owner_email.strip().lower()


    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # Check username

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE username = %s
                """,
                (owner_username,)
            )

            existing_user = cursor.fetchone()


            if existing_user:

                if existing_user["role"] != "owner":

                    raise RuntimeError(
                        "OWNER_USERNAME already belongs "
                        "to a non-owner account."
                    )

                # Update owner details/password
                cursor.execute(
                    """
                    UPDATE users
                    SET
                        name = %s,
                        email = %s,
                        password_hash = %s,
                        role = 'owner'
                    WHERE username = %s
                    """,
                    (
                        owner_name,
                        owner_email,
                        hash_password(owner_password),
                        owner_username
                    )
                )

            else:

                # Check email

                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    """,
                    (owner_email,)
                )

                existing_email = cursor.fetchone()


                if existing_email:

                    raise RuntimeError(
                        "OWNER_EMAIL is already being "
                        "used by another account."
                    )


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
                        hash_password(owner_password)
                    )
                )


        conn.commit()

    finally:

        conn.close()


# =========================================================
# PASSWORD SECURITY
# =========================================================

def hash_password(password: str) -> str:

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000
    )

    return (
        salt.hex()
        + ":"
        + password_hash.hex()
    )


def verify_password(
    password: str,
    stored_password: str
) -> bool:

    try:

        salt_hex, hash_hex = stored_password.split(":")

        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        )

        return secrets.compare_digest(
            new_hash.hex(),
            hash_hex
        )

    except Exception:

        return False


# Create owner account after password functions exist
create_owner_account()


# =========================================================
# BASIC ENDPOINTS
# =========================================================

@app.get("/")
def home():

    return {
        "message": "Placement AI Platform API is running",
        "status": "success",
        "version": "4.0.0"
    }


@app.get("/health")
def health():

    try:

        conn = get_db()

        with conn.cursor() as cursor:

            cursor.execute("SELECT 1")


        conn.close()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as error:

        return {
            "status": "unhealthy",
            "database": "error",
            "message": str(error)
        }


# =========================================================
# USERNAME VALIDATION
# =========================================================

def validate_username(username: str):

    username = username.strip().lower()


    if not username:

        raise HTTPException(
            status_code=400,
            detail="Username is required."
        )


    if len(username) < 3:

        raise HTTPException(
            status_code=400,
            detail="Username must contain at least 3 characters."
        )


    if len(username) > 30:

        raise HTTPException(
            status_code=400,
            detail="Username cannot exceed 30 characters."
        )


    if not re.match(
        r"^[a-z0-9_]+$",
        username
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Username can contain only "
                "letters, numbers and underscores."
            )
        )


    return username


# =========================================================
# AUTHENTICATION MODELS
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
    role: str


# =========================================================
# REGISTER
# =========================================================

@app.post("/api/v1/auth/register")
@app.post("/api/v1/register")
def register(request: RegisterRequest):

    username = validate_username(
        request.username
    )

    name = request.name.strip()

    email = request.email.strip().lower()

    password = request.password

    role = request.role.strip().lower()


    # Owner CANNOT register through website

    if role == "owner":

        raise HTTPException(
            status_code=403,
            detail=(
                "Owner accounts cannot be created "
                "through public registration."
            )
        )


    if not name:

        raise HTTPException(
            status_code=400,
            detail="Name is required."
        )


    if not re.match(
        r"^[^@]+@[^@]+\.[^@]+$",
        email
    ):

        raise HTTPException(
            status_code=400,
            detail="Please enter a valid email address."
        )


    if len(password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters."
        )


    if len(password) > 128:

        raise HTTPException(
            status_code=400,
            detail="Password is too long."
        )


    if role not in [
        "career_seeker",
        "recruiter"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Invalid account type."
        )


    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # Check username

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE username = %s
                """,
                (username,)
            )

            if cursor.fetchone():

                raise HTTPException(
                    status_code=409,
                    detail="Username already taken."
                )


            # Check email

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            if cursor.fetchone():

                raise HTTPException(
                    status_code=409,
                    detail="An account with this email already exists."
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
                    role
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
@app.post("/api/v1/login")
def login(request: LoginRequest):

    username = validate_username(
        request.username
    )

    password = request.password

    role = request.role.strip().lower()


    if role not in [
        "career_seeker",
        "recruiter",
        "owner"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Invalid account type."
        )


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

    finally:

        conn.close()


    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )


    if user["role"] != role:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )


    if not verify_password(
        password,
        user["password_hash"]
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password."
        )


    return {
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }


# =========================================================
# SKILLS
# =========================================================

SKILLS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "node.js",
    "fastapi",
    "django",
    "flask",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "git",
    "github",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "html",
    "css",
    "machine learning",
    "deep learning",
    "tensorflow",
    "pytorch",
    "pandas",
    "numpy",
    "data analysis",
    "rest api",
    "api",
    "linux",
    "excel"
}


def extract_skills(text: str):

    text = text.lower()

    found = set()

    for skill in SKILLS:

        if skill in text:

            found.add(skill)

    return found


# =========================================================
# JOB MATCH
# =========================================================

class JobMatchRequest(BaseModel):

    resume_text: str
    job_description: str


@app.post("/api/v1/job-match")
def job_match(request: JobMatchRequest):

    resume_skills = extract_skills(
        request.resume_text
    )

    job_skills = extract_skills(
        request.job_description
    )


    if not job_skills:

        return {
            "match_score": 0,
            "matching_skills": [],
            "missing_skills": [],
            "recommendation": (
                "The job description does not contain "
                "recognizable technical skills."
            )
        }


    matching_skills = sorted(
        resume_skills.intersection(
            job_skills
        )
    )


    missing_skills = sorted(
        job_skills.difference(
            resume_skills
        )
    )


    match_score = round(
        (
            len(matching_skills)
            /
            len(job_skills)
        )
        * 100
    )


    if match_score >= 80:

        recommendation = (
            "Excellent match. You are strongly aligned with this job."
        )

    elif match_score >= 60:

        recommendation = (
            "Good match. Improve the missing skills before applying."
        )

    elif match_score >= 40:

        recommendation = (
            "Moderate match. Focus on the missing skills."
        )

    else:

        recommendation = (
            "Low match. Consider improving your technical skill alignment."
        )


    return {
        "match_score": match_score,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "resume_skills_detected": sorted(resume_skills),
        "job_skills_detected": sorted(job_skills),
        "recommendation": recommendation
    }


# =========================================================
# RESUME ANALYZER
# =========================================================

class ResumeRequest(BaseModel):

    resume_text: str


@app.post("/api/v1/resume-analyze")
def resume_analyze(request: ResumeRequest):

    resume_skills = extract_skills(
        request.resume_text
    )

    total_skills = len(SKILLS)

    detected_skills = sorted(
        resume_skills
    )


    if total_skills > 0:

        skill_score = round(
            (
                len(resume_skills)
                /
                total_skills
            )
            * 100
        )

    else:

        skill_score = 0


    recommendations = []


    if "python" not in resume_skills:

        recommendations.append(
            "Consider adding Python skills."
        )


    if "sql" not in resume_skills:

        recommendations.append(
            "Consider adding SQL/database experience."
        )


    if "git" not in resume_skills:

        recommendations.append(
            "Consider adding Git/version control experience."
        )


    if (
        "rest api" not in resume_skills
        and
        "api" not in resume_skills
    ):

        recommendations.append(
            "Consider adding REST API experience."
        )


    if "docker" not in resume_skills:

        recommendations.append(
            "Consider learning Docker."
        )


    if not recommendations:

        recommendations.append(
            "Your resume contains a strong set of technical skills."
        )


    return {
        "skill_score": skill_score,
        "skills_detected": detected_skills,
        "total_skills_detected": len(detected_skills),
        "recommendations": recommendations
    }


# =========================================================
# JOB RECOMMENDATION ENGINE
# =========================================================

class JobRecommendationRequest(BaseModel):

    resume_text: str


JOB_PROFILES = {

    "Python Backend Developer": {

        "skills": [
            "python",
            "fastapi",
            "django",
            "sql",
            "git",
            "rest api",
            "docker"
        ]

    },

    "Data Analyst": {

        "skills": [
            "python",
            "sql",
            "pandas",
            "numpy",
            "data analysis",
            "excel"
        ]

    },

    "Frontend Developer": {

        "skills": [
            "html",
            "css",
            "javascript",
            "typescript",
            "react",
            "git"
        ]

    },

    "Full Stack Developer": {

        "skills": [
            "html",
            "css",
            "javascript",
            "react",
            "node.js",
            "sql",
            "git",
            "docker"
        ]

    },

    "Machine Learning Engineer": {

        "skills": [
            "python",
            "machine learning",
            "deep learning",
            "tensorflow",
            "pytorch",
            "pandas",
            "numpy"
        ]

    }

}


@app.post("/api/v1/job-recommendations")
def job_recommendations(
    request: JobRecommendationRequest
):

    resume_skills = extract_skills(
        request.resume_text
    )

    recommendations = []


    for job_title, job_data in JOB_PROFILES.items():

        job_skills = set(
            job_data["skills"]
        )


        matching_skills = sorted(
            resume_skills.intersection(
                job_skills
            )
        )


        missing_skills = sorted(
            job_skills.difference(
                resume_skills
            )
        )


        match_score = round(
            (
                len(matching_skills)
                /
                len(job_skills)
            )
            * 100
        )


        recommendations.append({

            "job_title": job_title,

            "match_score": match_score,

            "matching_skills": matching_skills,

            "missing_skills": missing_skills

        })


    recommendations.sort(
        key=lambda x: x["match_score"],
        reverse=True
    )


    return {

        "resume_skills_detected":
            sorted(resume_skills),

        "recommended_jobs":
            recommendations

    }


# =========================================================
# RECRUITER JOB POSTING
# =========================================================

class JobCreateRequest(BaseModel):

    recruiter_id: int
    title: str
    description: str


@app.post("/api/v1/jobs")
def create_job(
    request: JobCreateRequest
):

    title = request.title.strip()

    description = request.description.strip()


    if not title:

        raise HTTPException(
            status_code=400,
            detail="Job title is required."
        )


    if not description:

        raise HTTPException(
            status_code=400,
            detail="Job description is required."
        )


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
                    detail="Only recruiters can post jobs."
                )


            cursor.execute(
                """
                INSERT INTO jobs
                (
                    recruiter_id,
                    title,
                    description
                )
                VALUES (%s, %s, %s)
                RETURNING
                    id,
                    recruiter_id,
                    title,
                    description,
                    created_at
                """,
                (
                    request.recruiter_id,
                    title,
                    description
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

        "message": "Job posted successfully.",

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
                    jobs.created_at,
                    users.username AS recruiter_username
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
# APPLY FOR JOB
# =========================================================

class JobApplicationRequest(BaseModel):

    job_id: int
    candidate_id: int


@app.post("/api/v1/jobs/apply")
def apply_for_job(
    request: JobApplicationRequest
):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # Verify candidate

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
                    detail="Only career seekers can apply for jobs."
                )


            # Verify job

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
# OWNER - DASHBOARD DATA
# =========================================================

@app.get("/api/v1/owner/dashboard")
def owner_dashboard(owner_id: int):

    conn = get_db()

    try:

        with conn.cursor() as cursor:

            # Verify owner

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


            # Total users

            cursor.execute(
                """
                SELECT COUNT(*) AS total_users
                FROM users
                """
            )

            total_users = cursor.fetchone()["total_users"]


            # Career seekers

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'career_seeker'
                """
            )

            career_seekers = cursor.fetchone()["count"]


            # Recruiters

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM users
                WHERE role = 'recruiter'
                """
            )

            recruiters = cursor.fetchone()["count"]


            # Jobs

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM jobs
                """
            )

            jobs = cursor.fetchone()["count"]


            # Applications

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                """
            )

            applications = cursor.fetchone()["count"]


            # Recent users

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


            # Recent jobs

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

        "recent_jobs": recent_jobs

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
                "SELECT COUNT(*) AS user_count FROM users"
            )

            result = cursor.fetchone()

    finally:

        conn.close()


    return {

        "success": True,

        "database": "PostgreSQL",

        "users": result["user_count"]

    }
