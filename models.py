from pydantic import BaseModel
from typing import List


class JobMatch(BaseModel):
    match_score: int
    key_matches: List[str]
    skill_gaps: List[str]
    seniority_estimate: str


class MarketResearch(BaseModel):
    company_summary: str
    company_health: str
    company_culture: str


class CareerEvaluation(BaseModel):
    offer_probability: str
    career_value: str
    risks: List[str]
    recommendation: str

class SalaryEstimation(BaseModel):
    salary_low: int
    salary_high: int
    currency: str
    confidence: str
    sources: List[str]
    