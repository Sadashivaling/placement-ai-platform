from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import hashlib
import secrets
import re

app = FastAPI(
    title="Placement AI Platform",
    description="AI-powered placement and job readiness platform",
    version="2.0.0"
)

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

DATABASE = "placement.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


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


def verify_password(password: str, stored_password: str) -> bool:
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


# =========================================================
# BASIC ENDPOINTS
# =========================================================

@app.get("/")
def home():
    return {
        "message": "Placement AI Platform API is running",
        "status": "success"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# =========================================================
# AUTHENTICATION
# =========================================================

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str


@app.post("/api/v1/register")
def register(request: RegisterRequest):

    name = request.name.strip()
    email = request.email.strip().lower()
    password = request.password
    role = request.role.strip().lower()

    if not name:
        return {
            "success": False,
            "message": "Name is required."
        }

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {
            "success": False,
            "message": "Please enter a valid email address."
        }

    if len(password) < 6:
        return {
            "success": False,
            "message": "Password must contain at least 6 characters."
        }

    if role not in ["career_seeker", "recruiter"]:
        return {
            "success": False,
            "message": "Invalid account type."
        }

    conn = get_db()

    existing_user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if existing_user:
        conn.close()

        return {
            "success": False,
            "message": "An account with this email already exists."
        }

    password_hash = hash_password(password)

    conn.execute(
        """
        INSERT INTO users
        (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            email,
            password_hash,
            role
        )
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": "Account created successfully. You can now log in."
    }


@app.post("/api/v1/login")
def login(request: LoginRequest):

    email = request.email.strip().lower()
    password = request.password
    role = request.role.strip().lower()

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()

    if not user:
        return {
            "success": False,
            "message": "Invalid email or password."
        }

    if user["role"] != role:
        return {
            "success": False,
            "message": "Invalid email or password for this account type."
        }

    if not verify_password(
        password,
        user["password_hash"]
    ):
        return {
            "success": False,
            "message": "Invalid email or password."
        }

    return {
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }


# =========================================================
# JOB MATCH ANALYZER
# =========================================================

class JobMatchRequest(BaseModel):
    resume_text: str
    job_description: str


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
}


def extract_skills(text: str):
    text = text.lower()
    found = set()

    for skill in SKILLS:
        if skill in text:
            found.add(skill)

    return found


@app.post("/api/v1/job-match")
def job_match(request: JobMatchRequest):

    resume_skills = extract_skills(request.resume_text)
    job_skills = extract_skills(request.job_description)

    if not job_skills:
        return {
            "match_score": 0,
            "matching_skills": [],
            "missing_skills": [],
            "recommendation":
                "The job description does not contain recognizable technical skills."
        }

    matching_skills = sorted(
        resume_skills.intersection(job_skills)
    )

    missing_skills = sorted(
        job_skills.difference(resume_skills)
    )

    match_score = round(
        (len(matching_skills) / len(job_skills)) * 100
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

    resume_skills = extract_skills(request.resume_text)

    total_skills = len(SKILLS)

    detected_skills = sorted(resume_skills)

    if total_skills > 0:
        skill_score = round(
            (len(resume_skills) / total_skills) * 100
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
        and "api" not in resume_skills
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

        if job_skills:
            match_score = round(
                (
                    len(matching_skills)
                    / len(job_skills)
                ) * 100
            )
        else:
            match_score = 0

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
