import os
from groq import Groq
from dotenv import load_dotenv
import fitz  # PyMuPDF

load_dotenv()

# Initialize Groq client
client = Groq(
    api_key=os.getenv("Groq_API_KEY")
)

def extract_text_from_pdf(path):
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def match_resume(job_path, resume_path):
    job_text = extract_text_from_pdf(job_path)
    resume_text = extract_text_from_pdf(resume_path)

    prompt = f"""
Compare the following job description and resume. Analyze how well the resume matches the job requirements.

Your analysis MUST include:
1. A clear compatibility score from 0 to 100 (format it as 'Compatibility Score: XX/100' or 'Score: XX%').
2. A detailed explanation of why you assigned this score.
3. A list of matching skills found in the resume that align with the job description.
4. A list of missing or partial skills that would improve the candidate's fit for the position.

Job Description:
{job_text}

Resume:
{resume_text}
"""

    response = client.chat.completions.create(
        model="llama3-8b-8192",  # or "mixtral-8x7b-32768" for better performance
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000,
        temperature=0.7
    )

    reply = response.choices[0].message.content
    return reply
