import os
from crewai import Agent, Task, Crew
from crewai_tools import TavilySearchTool
from langchain_google_genai import ChatGoogleGenerativeAI
from models import JobMatch, MarketResearch, CareerEvaluation, SalaryEstimation

search = TavilySearchTool()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    verbose=True,
    temperature=0.5,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)


job_agent = Agent(
    role="Technical Recruiter",
    goal="Evaluate candidate fit for a role",
    backstory="Skeptical and realistic senior recruiter specialized in software engineering hiring.",
    llm=llm
)

market_agent = Agent(
    role="Market Analyst",
    goal="Research company background and company culture",
    backstory="Industry analyst specialized in tech hiring trends.",
    tools=[search],
    llm=llm
)

salary_agent = Agent(
    role="Compensation Analyst",
    goal="Estimate realistic salary ranges for the job using multiple sources.",
    backstory="Expert in tech compensation analysis using public salary data sources like Glassdoor, Levels.fyi, LinkedIn and market reports. Your are very realistic and skeptical.",
    tools=[search],
    llm=llm
)

career_agent = Agent(
    role="Career Advisor",
    goal="Evaluate career upside and risks",
    backstory="Career advisor helping engineers evaluate job opportunities. Your are very realistic and skeptical.",
    llm=llm
)


def run_agents(cv: str, jd: str):

    task1 = Task(
        description="""
Evaluate how well the following CV matches the job description.

CANDIDATE CV:
{cv}

JOB DESCRIPTION:
{job_description}

Return JSON with:
match_score
key_matches
skill_gaps
seniority_estimate

Return ONLY valid JSON.
""",
        expected_output="JSON job match analysis",
        output_pydantic=JobMatch,
        agent=job_agent
    )

    task2 = Task(
        description="""
Research the company and job market.

JOB DESCRIPTION:
{job_description}

Determine:
- company summary
- likely company name
- company financial health
- company culture

Return ONLY valid JSON.
""",
        expected_output="JSON market research",
        output_pydantic=MarketResearch,
        agent=market_agent,
        context=[task1]
    )

    task3 = Task(
        description="""
Estimate a realistic salary range for this job.

JOB DESCRIPTION:
{job_description}

Use web search to find compensation data from sources such as:
- Glassdoor
- Levels.fyi
- LinkedIn salary insights
- industry salary reports

Adjust salary range based on location, years of experience, company size, industry, etc. Applicant is Budapest based.

Return ONLY valid JSON.
""",
        expected_output="Salary estimation",
        output_pydantic=SalaryEstimation,
        agent=salary_agent,
        context=[task1, task2]
    )

    task4 = Task(
        description="""
Using the job match analysis, market research, and salary estimation from previous tasks, evaluate the career opportunity.

CV:
{cv}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON with exactly these fields:
- "offer_probability": a string estimating the realistic chance of getting an offer (e.g. "50%")
- "career_value": a string describing the career growth potential
- "risks": a list of strings, each describing a risk (e.g. ["risk 1", "risk 2"])
- "recommendation": a string with your overall recommendation

Do NOT include any text, explanation, or markdown outside the JSON object.
Return ONLY a raw JSON object.
""",
        expected_output="JSON career evaluation with offer_probability, career_value, risks, and recommendation",
        output_pydantic=CareerEvaluation,
        agent=career_agent,
        context=[task1, task2, task3]
    )

    crew = Crew(
        agents=[job_agent, market_agent, salary_agent, career_agent], 
        tasks=[task1, task2, task3, task4]
    )

    result = crew.kickoff(inputs={
        "cv": cv,
        "job_description": jd
    })

    combined = {}
    for task_output in result.tasks_output:
        if task_output.pydantic:
            combined.update(task_output.pydantic.model_dump())

    return combined