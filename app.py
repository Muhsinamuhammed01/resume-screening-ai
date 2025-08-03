from flask import Flask, render_template, request
import os
from werkzeug.utils import secure_filename
from ai_utils.match_engine import match_resume

app = Flask(__name__)

# Get absolute path for uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/screen')
def screen():
    return render_template('index.html')

@app.route('/create-resume')
def create_resume():
    return render_template('create_resume.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    job_file = request.files['job_description']
    resume_file = request.files['resume']
    
    job_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(job_file.filename))
    resume_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(resume_file.filename))
    
    job_file.save(job_path)
    resume_file.save(resume_path)

    result = match_resume(job_path, resume_path)
    
    # Extract score from result (assuming the LLM includes a score in its response)
    import re
    
    # Add debug information to the result
    debug_info = "\n\n<!-- Debug Info: Score extraction attempt -->"
    
    # Try multiple regex patterns to find the score
    # Pattern 1: Look for compatibility score format (e.g., "Compatibility Score: 85/100")
    score_match = re.search(r'compatibility\s+score:?\s*([0-9]{1,3})\s*(?:\/|out\s+of)\s*100', result, re.IGNORECASE)
    if score_match:
        debug_info += "\n<!-- Pattern 1 (Compatibility Score) matched -->"
    
    # Pattern 2: Look for score format (e.g., "Score: 85/100" or "Score: 85%")
    if not score_match:
        score_match = re.search(r'score:?\s*([0-9]{1,3})\s*(?:\/|out\s+of)\s*100|score:?\s*([0-9]{1,3})\s*%', result, re.IGNORECASE)
        if score_match:
            debug_info += "\n<!-- Pattern 2 (Score format) matched -->"
    
    # Pattern 3: Look for percentage (e.g., "85%")
    if not score_match:
        score_match = re.search(r'\b([0-9]{1,3})\s*%', result)
        if score_match:
            debug_info += "\n<!-- Pattern 3 (Percentage) matched -->"
    
    # Pattern 4: Look for score mentioned with the word "score" (e.g., "The score is 85")
    if not score_match:
        score_match = re.search(r'(?:score|rating|match)\s*(?:is|:)\s*([0-9]{1,3})\b', result, re.IGNORECASE)
        if score_match:
            debug_info += "\n<!-- Pattern 4 (Score is/: format) matched -->"
    
    # Pattern 5: Look for X/100 format anywhere in the text
    if not score_match:
        score_match = re.search(r'\b([0-9]{1,3})\s*\/\s*100\b', result)
        if score_match:
            debug_info += "\n<!-- Pattern 5 (X/100 format) matched -->"
    
    # Pattern 6: Look for any number between 0 and 100 that might be a score
    if not score_match:
        score_match = re.search(r'\b([0-9]{1,2}|100)\b', result)
        if score_match:
            debug_info += "\n<!-- Pattern 6 (Any number) matched -->"
    
    # Default score if no match is found
    score = 75  # Default to a moderate score if none is found
    
    if score_match:
        try:
            # Handle both group(1) and group(2) for patterns that have multiple capture groups
            score_str = None
            for i in range(1, 3):
                try:
                    if score_match.group(i) and score_match.group(i).strip():
                        score_str = score_match.group(i)
                        break
                except (IndexError, AttributeError):
                    continue
            
            if score_str:
                score = int(score_str)
                debug_info += f"\n<!-- Extracted score: {score} -->"
                # Ensure score is within valid range
                if score < 0 or score > 100:
                    debug_info += f"\n<!-- Score out of range, using default -->"
                    score = 75  # Default to a moderate score if out of range
            else:
                debug_info += "\n<!-- No valid score group found, using default -->"
        except (ValueError, IndexError):
            debug_info += "\n<!-- Error converting score, using default -->"
            score = 75  # Default to a moderate score if conversion fails
    else:
        debug_info += "\n<!-- No score pattern matched, using default -->"
    
    # Append debug info to result
    result += debug_info
    
    # Determine match category based on score
    match_category = "Needs Improvement"
    score_class = "score-needs-improvement"
    if score >= 80:
        match_category = "Excellent Match"
        score_class = "score-excellent"
    elif score >= 60:
        match_category = "Good Match"
        score_class = "score-good"
    
    # Extract skills information
    # Look for matching skills in the result
    matching_skills = []
    missing_skills = []
    
    # Try to find a section about matching skills
    skills_section = re.search(r'(?:matching|matched|present|existing|found)\s+skills[:\s]+(.*?)(?:\n\n|\n[A-Z]|$)', 
                              result, re.IGNORECASE | re.DOTALL)
    if skills_section:
        skills_text = skills_section.group(1).strip()
        # Extract skills from bullet points, commas, or other separators
        skills = re.findall(r'[-•*]\s*([^,\n]+)|([^,\n:]+)', skills_text)
        matching_skills = [s[0].strip() if s[0] else s[1].strip() for s in skills if s[0].strip() or s[1].strip()]
    
    # Try to find a section about missing skills
    missing_section = re.search(r'(?:missing|absent|lacking|needed|required)\s+skills[:\s]+(.*?)(?:\n\n|\n[A-Z]|$)', 
                              result, re.IGNORECASE | re.DOTALL)
    if missing_section:
        missing_text = missing_section.group(1).strip()
        # Extract skills from bullet points, commas, or other separators
        skills = re.findall(r'[-•*]\s*([^,\n]+)|([^,\n:]+)', missing_text)
        missing_skills = [s[0].strip() if s[0] else s[1].strip() for s in skills if s[0].strip() or s[1].strip()]
    
    # If no skills were found with the specific sections, try a more general approach
    if not matching_skills and not missing_skills:
        # Look for any mentions of skills in the text
        skills_mentions = re.findall(r'(?:has|possesses|demonstrates|shows)\s+(?:skills?|experience|knowledge)\s+(?:in|with)\s+([^.\n]+)', 
                                    result, re.IGNORECASE)
        for mention in skills_mentions:
            skills = re.split(r',|and', mention)
            matching_skills.extend([s.strip() for s in skills if s.strip()])
        
        # Look for missing skills mentions
        missing_mentions = re.findall(r'(?:lacks|missing|needs|should improve)\s+(?:skills?|experience|knowledge)\s+(?:in|with)\s+([^.\n]+)', 
                                    result, re.IGNORECASE)
        for mention in missing_mentions:
            skills = re.split(r',|and', mention)
            missing_skills.extend([s.strip() for s in skills if s.strip()])
    
    # Clean up skills lists to remove duplicates and empty entries
    matching_skills = list(set([skill for skill in matching_skills if skill and len(skill) > 2]))
    missing_skills = list(set([skill for skill in missing_skills if skill and len(skill) > 2]))
    
    # If we still don't have any skills, provide some defaults based on common technical skills
    if not matching_skills:
        matching_skills = ["Technical Skills", "Communication", "Problem Solving"]
    if not missing_skills:
        missing_skills = ["Additional Experience Needed"]

    return render_template('result.html', result=result, score=score, match_category=match_category, 
                          score_class=score_class, matching_skills=matching_skills, missing_skills=missing_skills)

@app.route('/generate-resume', methods=['POST'])
def generate_resume():
    # Get form data
    data = request.form.to_dict()
    
    # Process the resume data and generate a PDF
    # You can implement the resume generation logic here
    
    return "Resume generation feature coming soon!"

if __name__ == '__main__':
    app.run(debug=True)
