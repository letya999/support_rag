import asyncio
import aiohttp
import time
import statistics
import uuid
import random
import json

URL = "http://localhost:8000/api/v1/chat/completions"
CONCURRENT_REQUESTS = 100

# Hardcoded list of 100 unique questions to ensure high variance
QUESTIONS_LIST = [
    "Where is the section to see my past orders?",
    "I need to call your support team, what is the number?",
    "Do you ship products to Japan?",
    "How can I trace the location of my package?",
    "Is American Express accepted here?",
    "Can you give me the address of your headquarters?",
    "Show me my purchase history please.",
    "I want to send an email to customer service.",
    "Do you guys deliver to Canada?",
    "Where do I input my tracking number?",
    "Can I pay using Google Pay?",
    "What city are your main offices in?",
    "I'm looking for a list of things I bought previously.",
    "How do I get in touch with a human agent?",
    "Is shipping to Germany available?",
    "My tracking link isn't showing up, how do I track?",
    "Do you take cryptocurrency?",
    "Where is your physical office located?",
    "Where can I download my order invoices?",
    "What are your customer support operating hours?",
    "Do you ship to P.O. boxes internationally?",
    "Help me track my shipment status.",
    "Is it possible to pay with a debit card?",
    "Are you based in the US or Europe?",
    "I lost my order history, where is it?",
    "I need help, how do I reach the helpdesk?",
    "Do you offer delivery to Australia?",
    "What is the status of my delivery?",
    "Do you accept Discover cards?",
    "Where can I visit your corporate office?",
    "How do I view old orders?",
    "Is there a live chat for support?",
    "Can I order if I live in Brazil?",
    "I haven't received a tracking ID.",
    "Can I split payment between two cards?",
    "What is the zip code of your headquarters?",
    "Access my buying history.",
    "Who do I contact for a complaint?",
    "Do you ship to remote islands?",
    "Where is my package right now?",
    "Do you accept cash on delivery?",
    "Are you a remote company or do you have an office?",
    "Where is the 'Orders' tab?",
    "I need the support email address.",
    "Is shipping available for France?",
    "Track order #12345.",
    "Do you take Apple Pay?",
    "Tell me your office street address.",
    "Can I see orders from last year?",
    "I need to speak to a representative.",
    "Do you ship to Mexico?",
    "How long does tracking take to update?",
    "Is PayPal an option for payment?",
    "Where are you guys established?",
    "I can't find my previous purchases.",
    "Give me the toll-free support number.",
    "Do you deliver to South Africa?",
    "Check the location of my parcel.",
    "Do you accept prepaid visa cards?",
    "In which state is your company registered?",
    "Show me a log of my transactions.",
    "How do I open a support ticket?",
    "Do you ship to the UK?",
    "My package is late, how do I track it?",
    "Can I pay via bank transfer?",
    "Where is your main branch?",
    "I want to see what I ordered last month.",
    "Is there a phone number for enquiries?",
    "Do you send packages to India?",
    "The tracking system is confusing.",
    "Do you take Venmo?",
    "What is the exact location of your HQ?",
    "My account doesn't show my orders.",
    "How to contact the tech support team?",
    "Do you ship to Russia?",
    "Where do I go to track my delivery?",
    "Do you accept personal checks?",
    "Are you located in California?",
    "Retrieve my shopping history.",
    "I have a question, who do I call?",
    "Is delivery to New Zealand possible?",
    "How do I know where my stuff is?",
    "Can I use a gift card to pay?",
    "Where does the management team work?",
    "Where is the archive of my orders?",
    "I need immediate assistance.",
    "Do you ship to China?",
    "Tracking info says delivered but it's not here.",
    "Do you accept Klarna?",
    "What region is your head office in?",
    "I need to print a receipt from a past order.",
    "How do I reach out for help?",
    "Do you ship to Alaska and Hawaii?",
    "Is my order still in transit?",
    "Do you take Mastercard?",
    "Where on the map are you?",
    "I want to check my order status.",
    "What is the support hotline?",
    "Do you deliver to Antarctica?",
    (
        "Is it possible to pay with a credit card?"
    ),  # Parantheses to avoid linter issues with long strings? No, just string.
]

def generate_questions(count):
    # Return the exact list, slicing if count < 100, or repeating if count > 100 (though we expect 100)
    if count <= len(QUESTIONS_LIST):
        return QUESTIONS_LIST[:count]
    else:
        # Repeat list if more requested
        return (QUESTIONS_LIST * (count // len(QUESTIONS_LIST) + 1))[:count]

async def send_request(session, req_id, question):
    start = time.time()
    
    # Unique user and session for each request to avoid caching/state overlap
    payload = {
        "question": question,
        "user_id": f"load_user_{uuid.uuid4()}",
        "session_id": f"load_session_{uuid.uuid4()}"
    }
    
    try:
        async with session.post(URL, json=payload) as response:
            # We must read the response to ensure the request completes
            resp_text = await response.text()
            elapsed = time.time() - start
            status = response.status
            return status, elapsed, resp_text
    except Exception as e:
        return 0, time.time() - start, str(e)

async def main():
    questions = generate_questions(CONCURRENT_REQUESTS)
    print(f"Generated {len(questions)} unique questions.")
    print(f"Starting load test on {URL} with {CONCURRENT_REQUESTS} concurrent requests...")
    
    async with aiohttp.ClientSession() as session:
        # Create all tasks
        tasks = [send_request(session, i, questions[i]) for i in range(CONCURRENT_REQUESTS)]
        
        start_global = time.time()
        # Run them concurrently
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_global

    # Analysis
    successes = []
    errors = []
    
    for status, elapsed, text in results:
        if status == 200:
            successes.append(elapsed)
        else:
            errors.append((status, text))
    
    print(f"\n--- Load Test Results ---")
    print(f"Total time for batch: {total_time:.2f}s")
    print(f"Concurrent Users: {CONCURRENT_REQUESTS}")
    print(f"Successful requests: {len(successes)}/{CONCURRENT_REQUESTS}")
    print(f"Failed requests: {len(errors)}")
    
    if successes:
        print(f"Avg latency: {statistics.mean(successes):.4f}s")
        print(f"Min latency: {min(successes):.4f}s")
        print(f"Max latency: {max(successes):.4f}s")
        print(f"Median latency: {statistics.median(successes):.4f}s")
        print(f"Throughput: {len(successes) / total_time:.2f} req/s")
    
    if errors:
        print("\nSample Errors:")
        for status, msg in errors[:5]:
            print(f"[{status}] {msg[:100]}...")

if __name__ == "__main__":
    # Windows specific event loop policy
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
