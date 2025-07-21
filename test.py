""" Testing our matching algorithm with a knowledge base and a user query."""

text = """Here is the retrieved knowledge base:

Q1: What is our company's vacation policy?
A1: Full-time employees are entitled to 20 paid vacation days per year. Vacation days can be taken after completing 6 months of employment. Unused vacation days can be carried over to the next year up to a maximum of 5 days. Vacation requests should be submitted at least 2 weeks in advance through the HR portal.

Q2: How do I request a new software license?
A2: To request a new software license, please submit a ticket through the IT Service Desk portal. Include the software name, version, and business justification. Standard software licenses are typically approved within 2 business days. For specialized software, approval may take up to 5 business days and may require department head approval.

Q3: What is our remote work policy?
A3: Our company follows a hybrid work model. Employees can work remotely up to 3 days per week. Remote work days must be coordinated with your team and approved by your direct manager. All remote work requires a stable internet connection and a dedicated workspace. Core collaboration hours are 10:00 AM to 3:00 PM EST.

Q4: How do I submit an expense report?
A4: Expense reports should be submitted through the company's expense management system. Include all receipts, categorize expenses appropriately, and add a brief description for each entry. Reports must be submitted within 30 days of the expense. For expenses over $100, additional documentation may be required. All reports require manager approval.

Q5: What is our process for reporting a security incident?
A5: If you discover a security incident, immediately contact the Security Team at security@company.com or call the 24/7 security hotline. Do not attempt to investigate or resolve the incident yourself. Document what you observed, including timestamps and affected systems. The Security Team will guide you through the incident response process and may need your assistance for investigation."""

import re

# Knowledge base text
kb_text = text

def get_question(kb_text, q_num=1):
    """Extract a specific question from the knowledge base text."""
    pattern = rf'Q{q_num}:\s*(.*?)(?=\n[A-Z]\d+:|$)'
    match = re.search(pattern, kb_text, re.DOTALL)
    return match.group(1).strip() if match else None

def score_question(query, question_text):
    """Score a question with punctuation handling."""
    # Remove punctuation and normalize
    clean_query = re.sub(r'[^\w\s]', '', query.lower())
    clean_question = re.sub(r'[^\w\s]', '', question_text.lower())
    
    # Split into words
    user_words = set(clean_query.split())
    q_words = set(clean_question.split())
    
    # Find matching words
    matching_words = user_words.intersection(q_words)
    return len(matching_words), matching_words

def debug_matching_algorithm():
    """Debug the matching algorithm with detailed output."""
    query = "How can I submit a report on expenses?"
    print(f"Query: '{query}'\n")
    print(f"Query words: {set(query.lower().split())}\n")
    
    all_scores = []
    
    # Test each question
    for i in range(1, 6):  # Questions 1-5
        question = get_question(kb_text, i)
        score, matching = score_question(query, question)
        all_scores.append((i, score, question, matching))
    
    # Print results sorted by score (highest first)
    print("MATCHING RESULTS (SORTED BY SCORE):")
    print("=" * 80)
    for q_num, score, question, matching in sorted(all_scores, key=lambda x: x[1], reverse=True):
        print(f"Q{q_num}: {question}")
        print(f"   Score: {score}")
        print(f"   Matching words: {matching}")
        print("-" * 80)

# Run the analysis
debug_matching_algorithm()

# Also test our original algorithm for verification
def find_matching_question(kb_text, user_query):
    """Original matching algorithm."""
    all_questions = {}
    for i in range(1, 10):
        q_text = get_question(kb_text, i)
        if q_text:
            all_questions[i] = q_text
        else:
            break
    
    # clean user query
    user_query = re.sub(r'[^\w\s]', '', user_query.lower())
    user_words = set(user_query.split())

    best_match = 1
    highest_score = 0
    
    for q_num, q_text in all_questions.items():
        # clean question text
        q_text = re.sub(r'[^\w\s]', '', q_text.lower())
        q_words = set(q_text.split())

        score = len(user_words.intersection(q_words)) # intersectionreturns set of matching words
        if score > highest_score:
            highest_score = score
            best_match = q_num
            
    return best_match, all_questions[best_match]

# Test the original algorithm
best_q, best_text = find_matching_question(kb_text, "How can I submit a report on expenses?")
print("\nORIGINAL ALGORITHM RESULT:")
print(f"Best match: Q{best_q}: {best_text}")