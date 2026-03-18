"""
Seed projects into MongoDB from portfolio data.
This script imports sample project data and adds it to the database.
"""

import asyncio
import json
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.project import Project
import os
from dotenv import load_dotenv

load_dotenv()


# Sample projects data (matching the structure from portfolioData.js)
SAMPLE_PROJECTS = [
    {
        "title": "Sentiment Analysis with BERT",
        "category": "Deep Learning",
        "description": "Fine-tuning transformer models to classify sentiment in financial news with 94% accuracy.",
        "fullDescription": "This project demonstrates advanced NLP techniques using state-of-the-art transformer models. Achieved 94% accuracy on financial sentiment classification, enabling better market analysis.",
        "technologies": ["PyTorch", "Hugging Face", "NLP", "Transformers"],
        "techStack": ["PyTorch", "Hugging Face", "NLP", "Transformers"],
        "image": "https://placehold.co/600x400/001f3f/FFF?text=NLP+Model",
        "links": {
            "github": "https://github.com/mobadara/sentiment-analysis",
            "demo": "https://sentiment-demo.example.com",
            "paper": None,
            "youtube": "https://youtube.com/watch?v=sentiment-analysis-demo"
        },
        "githubUrl": "https://github.com/mobadara/sentiment-analysis",
        "liveUrl": "https://sentiment-demo.example.com",
        "metrics": {
            "accuracy": 94,
            "datasets": 50000,
            "models_trained": 3
        },
        "order": 1,
        "featured": True
    },
    {
        "title": "Credit Risk Prediction",
        "category": "Data Science",
        "description": "Classical ML pipeline using Random Forest and XGBoost to predict loan defaults for a fintech client.",
        "fullDescription": "Enterprise-grade machine learning solution for financial risk assessment. Implemented comprehensive feature engineering, model selection, and cross-validation strategies.",
        "technologies": ["Scikit-Learn", "Pandas", "XGBoost", "SQL"],
        "techStack": ["Scikit-Learn", "Pandas", "XGBoost", "SQL"],
        "image": "https://placehold.co/600x400/e0e0e0/333?text=Risk+Model",
        "links": {
            "github": "https://github.com/mobadara/credit-risk",
            "demo": None,
            "paper": None,
            "youtube": None
        },
        "githubUrl": "https://github.com/mobadara/credit-risk",
        "liveUrl": None,
        "metrics": {
            "precision": 0.91,
            "recall": 0.88,
            "auc_score": 0.94
        },
        "order": 2,
        "featured": False
    },
    {
        "title": "AI-Powered REST API",
        "category": "AI Engineering",
        "description": "Scalable REST API built with FastAPI to serve real-time predictions from trained PyTorch models.",
        "fullDescription": "Production-ready API serving ML models at scale. Includes authentication, rate limiting, comprehensive logging, and containerization for cloud deployment.",
        "technologies": ["FastAPI", "Docker", "Azure", "PostgreSQL"],
        "techStack": ["FastAPI", "Docker", "Azure", "PostgreSQL"],
        "image": "https://placehold.co/600x400/003366/FFF?text=FastAPI+Backend",
        "links": {
            "github": "https://github.com/mobadara/ml-api",
            "demo": "https://api.example.com/docs",
            "paper": None,
            "youtube": "https://youtube.com/watch?v=ml-api-tutorial"
        },
        "githubUrl": "https://github.com/mobadara/ml-api",
        "liveUrl": "https://api.example.com/docs",
        "metrics": {
            "requests_per_second": 1000,
            "uptime": 99.9,
            "response_time_ms": 150
        },
        "order": 3,
        "featured": True
    },
    {
        "title": "Computer Vision for Medical Imaging",
        "category": "Deep Learning",
        "description": "CNN-based system trained on X-ray datasets to detect pneumonia with clinical-grade accuracy.",
        "fullDescription": "Deep learning system achieving 96% sensitivity in pneumonia detection. Deployed in healthcare settings with HIPAA compliance and interpretability features.",
        "technologies": ["TensorFlow", "CNN", "OpenCV", "Grad-CAM"],
        "techStack": ["TensorFlow", "CNN", "OpenCV", "Grad-CAM"],
        "image": "https://placehold.co/600x400/555/FFF?text=Computer+Vision",
        "links": {
            "github": "https://github.com/mobadara/medical-imaging",
            "demo": None,
            "paper": "https://arxiv.example.com/pneumonia",
            "youtube": "https://youtube.com/watch?v=medical-imaging-demo"
        },
        "githubUrl": "https://github.com/mobadara/medical-imaging",
        "liveUrl": None,
        "metrics": {
            "sensitivity": 96,
            "specificity": 94,
            "patients_tested": 5000
        },
        "order": 4,
        "featured": True
    }
]


async def seed_projects():
    """Seed the database with sample projects."""
    # Connect to MongoDB
    mongodb_url = os.getenv(
        "MONGODB_URL",
        "mongodb://localhost:27017"
    )
    client = AsyncIOMotorClient(mongodb_url)
    db = client.portfolio_db

    # Initialize Beanie
    await init_beanie(database=db, models=[Project])

    # Check if projects already exist
    existing_count = await Project.find_all().count()
    if existing_count > 0:
        print(f"Database already contains {existing_count} projects. Skipping seeding.")
        return

    # Insert projects
    projects_to_insert = []
    for project_data in SAMPLE_PROJECTS:
        project = Project(
            **project_data,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        projects_to_insert.append(project)

    # Bulk insert
    result = await Project.insert_many(projects_to_insert)
    print(f"Successfully seeded {len(result)} projects into the database!")

    # Close connection
    client.close()


async def main():
    """Main entry point."""
    try:
        await seed_projects()
        print("✓ Project seeding completed successfully!")
    except Exception as e:
        print(f"✗ Error seeding projects: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
