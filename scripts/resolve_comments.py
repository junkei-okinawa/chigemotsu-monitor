import subprocess
import json

def run_gh_query(query):
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.stdout

def resolve_thread(thread_id, message):
    # 1. Add reply
    reply_query = f'''
    mutation {{
      addPullRequestReviewThreadReply(input: {{pullRequestReviewThreadId: "{thread_id}", body: "{message}"}}) {{
        clientMutationId
      }}
    }}
    '''
    run_gh_query(reply_query)
    
    # 2. Resolve thread
    resolve_query = f'''
    mutation {{
      resolveReviewThread(input: {{threadId: "{thread_id}"}}) {{
        thread {{
          isResolved
        }}
      }}
    }}
    '''
    run_gh_query(resolve_query)
    print(f"Resolved thread {thread_id}")

fixed_threads = [
    "PRRT_kwDOQ8LyDc5p4_uH", "PRRT_kwDOQ8LyDc5p4_uR", "PRRT_kwDOQ8LyDc5p4_uU", 
    "PRRT_kwDOQ8LyDc5p4_uV", "PRRT_kwDOQ8LyDc5p4_uX", "PRRT_kwDOQ8LyDc5p4_uY", 
    "PRRT_kwDOQ8LyDc5p4_ua", "PRRT_kwDOQ8LyDc5p4_ud", "PRRT_kwDOQ8LyDc5p4_ue", 
    "PRRT_kwDOQ8LyDc5p4_uh", "PRRT_kwDOQ8LyDc5p4_ul", "PRRT_kwDOQ8LyDc5p4_up", 
    "PRRT_kwDOQ8LyDc5p4_ut", "PRRT_kwDOQ8LyDc5p4_uv"
]

for thread_id in fixed_threads:
    resolve_thread(thread_id, "Fixed as suggested.")

# Ignored thread
resolve_thread("PRRT_kwDOQ8LyDc5p4_ux", "This print statement is intentional to provide immediate feedback to the user if dependencies are missing, before any logging configuration is loaded.")
