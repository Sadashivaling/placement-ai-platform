from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re


app = FastAPI(
    title="Placement AI Platform",
    description="AI-powered placement and job readiness platform",
    version="1.1.0"
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

# -------------------------
# Basic endpoints
# -------------------------

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


# -------------------------
# Job Match Analyzer
# -------------------------

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
    "excel",
    "power bi",
    "tableau",
    "scikit-learn",
    "seaborn",
    "matplotlib",
    "spring boot",
    "c++",
    "c",
    "php",
    "gitlab",
    "bitbucket",
    "redis",
    "graphql",
    "jenkins",
    "terraform",

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
            "recommendation": "The job description does not contain recognizable technical skills."
        }

    matching_skills = sorted(resume_skills.intersection(job_skills))
    missing_skills = sorted(job_skills.difference(resume_skills))

    match_score = round(
        (len(matching_skills) / len(job_skills)) * 100
    )

    if match_score >= 80:
        recommendation = "Excellent match. You are strongly aligned with this job."
    elif match_score >= 60:
        recommendation = "Good match. Improve the missing skills before applying."
    elif match_score >= 40:
        recommendation = "Moderate match. Focus on the missing skills."
    else:
        recommendation = "Low match. Consider improving your technical skill alignment."

    return {
        "match_score": match_score,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "resume_skills_detected": sorted(resume_skills),
        "job_skills_detected": sorted(job_skills),
        "recommendation": recommendation
    }
    # -------------------------
# Resume Analyzer
# -------------------------

class ResumeRequest(BaseModel):
    resume_text: str


@app.post("/api/v1/resume-analyze")
def resume_analyze(request: ResumeRequest):

    resume_skills = extract_skills(request.resume_text)

    total_skills = len(SKILLS)
    detected_skills = sorted(resume_skills)

    if total_skills > 0:
        skill_score = round((len(resume_skills) / total_skills) * 100)
    else:
        skill_score = 0

    recommendations = []

    if "python" not in resume_skills:
        recommendations.append("Consider adding Python skills.")

    if "sql" not in resume_skills:
        recommendations.append("Consider adding SQL/database experience.")

    if "git" not in resume_skills:
        recommendations.append("Consider adding Git/version control experience.")

    if "rest api" not in resume_skills and "api" not in resume_skills:
        recommendations.append("Consider adding REST API experience.")

    if "docker" not in resume_skills:
        recommendations.append("Consider learning Docker.")

    if not recommendations:
        recommendations.append("Your resume contains a strong set of technical skills.")

    return {
        "skill_score": skill_score,
        "skills_detected": detected_skills,
        "total_skills_detected": len(detected_skills),
        "recommendations": recommendations
    }
    # -------------------------
# Job Recommendation Engine
# -------------------------

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
def job_recommendations(request: JobRecommendationRequest):

    resume_skills = extract_skills(request.resume_text)

    recommendations = []

    for job_title, job_data in JOB_PROFILES.items():

        job_skills = set(job_data["skills"])

        matching_skills = sorted(
            resume_skills.intersection(job_skills)
        )

        missing_skills = sorted(
            job_skills.difference(resume_skills)
        )

        if job_skills:
            match_score = round(
                (len(matching_skills) / len(job_skills)) * 100
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
        "resume_skills_detected": sorted(resume_skills),
        "recommended_jobs": recommendations
    }
